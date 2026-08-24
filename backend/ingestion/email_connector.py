"""IMAP email ingestion: poll a mailbox into the read-only message store.

Email is the third channel type in the schema; this connector makes it real.
Uses stdlib :mod:`imaplib` executed off the event loop (it is synchronous),
normalizes to the shared ``Message`` shape, and never mutates the mailbox —
read-only observation, same contract as Slack/WhatsApp intake.

Configuration (env): IMAP_HOST, IMAP_USER, IMAP_PASSWORD, IMAP_FOLDER
(default INBOX). No credentials configured = connector disabled and the sync
endpoint reports 503, mirroring the Slack flow.
"""

from __future__ import annotations

import email as email_lib
import logging
import os
import re
from datetime import UTC, datetime
from uuid import uuid4

from ..models.schema import Message

logger = logging.getLogger(__name__)

_SINCE_FMT = "%d-%b-%Y"
_MSG_ID_RE = re.compile(r"<[^>]+>")


class EmailConfigurationError(RuntimeError):
    pass


def _credentials() -> tuple[str, str, str, str]:
    host = os.getenv("IMAP_HOST", "").strip()
    user = os.getenv("IMAP_USER", "").strip()
    password = os.getenv("IMAP_PASSWORD", "")
    folder = os.getenv("IMAP_FOLDER", "INBOX").strip() or "INBOX"
    if not (host and user and password):
        raise EmailConfigurationError(
            "Set IMAP_HOST, IMAP_USER and IMAP_PASSWORD before syncing email.")
    return host, user, password, folder


def _decode_header(value) -> str:
    if not value:
        return "unknown"
    parts = email_lib.header.decode_header(str(value))
    decoded = []
    for text, charset in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return " ".join(decoded) or "unknown"


def parse_email_message(raw_bytes: bytes, fallback_channel: str,
                        uid: str | None = None) -> Message | None:
    """One raw RFC-8322 email -> Message (text body only; attachments skipped)."""
    msg = email_lib.message_from_bytes(raw_bytes)
    subject = _decode_header(msg.get("Subject"))
    sender = _decode_header(msg.get("From"))
    message_id = msg.get("Message-ID")
    stable_id = f"email:{_MSG_ID_RE.search(message_id).group(0)}" if (
        message_id and _MSG_ID_RE.search(message_id)) else f"email:{uid or uuid4().hex}"

    body_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
                break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="replace"))

    content = f"Re: {subject}\n{body_parts[0].strip()}" if body_parts else f"Re: {subject}"
    if len(content) > 8000:
        content = content[:8000]
    date_hdr = msg.get("Date")
    try:
        from email.utils import parsedate_to_datetime

        timestamp = parsedate_to_datetime(date_hdr) if date_hdr else datetime.now(UTC)
    except (TypeError, ValueError):
        timestamp = datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)

    return Message(
        id=stable_id,
        channel_id=fallback_channel,
        sender=sender,
        content=content,
        timestamp=timestamp,
        thread_id=message_id,
        metadata={"email_subject": subject, "read_only": True},
    )


def fetch_recent_messages(limit: int = 200) -> list[Message]:
    """Poll the mailbox for recent messages (executed in a worker thread)."""
    import imaplib

    host, user, password, folder = _credentials()
    channel_id = f"email:{user}"
    conn = imaplib.IMAP4_SSL(host)
    try:
        conn.login(user, password)
        conn.select(folder, readonly=True)
        status_code, data = conn.search(None, "ALL")
        if status_code != "OK":
            return []
        ids = data[0].split()[-limit:]
        messages: list[Message] = []
        for mail_uid in ids:
            status_code, msg_data = conn.fetch(mail_uid, "(RFC822)")
            if status_code != "OK" or not msg_data or msg_data[0] is None:
                continue
            raw = msg_data[0][1]
            parsed = parse_email_message(raw, channel_id, uid=mail_uid.decode())
            if parsed:
                messages.append(parsed)
        return messages
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001 - logout best-effort
            logger.debug("IMAP logout failed", exc_info=True)


async def sync_email_messages(limit: int = 200) -> list[Message]:
    """Async wrapper so the API can offload blocking IMAP work."""
    import asyncio

    messages = await asyncio.to_thread(fetch_recent_messages, limit)
    if not messages:
        return messages
    from .. import database

    channel_id = messages[0].channel_id
    await database.upsert_message_channel(channel_id)
    await database.create_messages(messages)
    return messages
