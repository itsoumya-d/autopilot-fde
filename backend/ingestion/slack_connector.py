"""Read-only Slack history ingestion. Bot tokens are read from the environment only."""

from datetime import datetime, timedelta, timezone
import os

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from ..models.schema import Message


class SlackConfigurationError(RuntimeError):
    pass


async def sync_channel(slack_channel_id: str, channel_id: str | None = None) -> list[Message]:
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise SlackConfigurationError("Set SLACK_BOT_TOKEN in the server environment before syncing Slack.")
    client = AsyncWebClient(token=token)
    try:
        auth = await client.auth_test()
        if not auth.get("ok"):
            raise SlackConfigurationError("Slack authentication failed.")
        normalized_channel_id = channel_id or f"slack:{slack_channel_id}"
        # A full initial pull is intentionally capped; pagination lets an operator run
        # repeated syncs without creating unbounded one-shot ingestion jobs.
        oldest = str((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())
        response = await client.conversations_history(channel=slack_channel_id, oldest=oldest, limit=200)
        messages: list[Message] = []
        seen: set[str] = set()

        def normalize(raw: dict, parent_thread: str | None = None) -> None:
            timestamp = raw.get("ts")
            if not timestamp or raw.get("subtype") in {"bot_message", "channel_join", "channel_leave"}:
                return
            message_id = f"slack:{slack_channel_id}:{timestamp}"
            if message_id in seen:
                return
            seen.add(message_id)
            messages.append(Message(
                id=message_id,
                channel_id=normalized_channel_id,
                sender=raw.get("user", "unknown"),
                content=raw.get("text", ""),
                timestamp=datetime.fromtimestamp(float(timestamp), tz=timezone.utc),
                thread_id=raw.get("thread_ts") or parent_thread or timestamp,
                metadata={"slack_ts": timestamp, "reactions": raw.get("reactions", []), "read_only": True},
            ))

        for item in response.get("messages", []):
            normalize(item)
            root_thread = item.get("thread_ts") or item.get("ts")
            if item.get("reply_count", 0) > 0 and root_thread:
                replies = await client.conversations_replies(channel=slack_channel_id, ts=root_thread, oldest=oldest, limit=200)
                for reply in replies.get("messages", [])[1:]:
                    normalize(reply, root_thread)
        return messages
    except SlackApiError as error:
        raise SlackConfigurationError(f"Slack sync failed: {error.response.get('error', 'unknown_error')}") from error
