"""Security primitives: API-key gate for mutating endpoints and Meta webhook
signature verification.

Threat model, stated plainly:

- This service reads communication channels and can create deployment records.
  In production it must never be publicly writable without a key.
- Meta's Cloud API signs every webhook delivery with HMAC-SHA256
  (X-Hub-Signature-256). Verifying it is the only way to know a POST actually
  came from Meta and not from anyone who found the URL.

Both controls activate when their environment variable is configured and stay
open in local development otherwise -- with a startup warning so an open
configuration is always visible, never silent.
"""

import hashlib
import hmac
import logging
import os

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"
SIGNATURE_HEADER = "X-Hub-Signature-256"


def api_key_configured() -> bool:
    return bool(os.getenv("AUTOPILOT_API_KEY"))


def require_api_key(request: Request) -> None:
    """FastAPI dependency for mutating endpoints.

    When AUTOPILOT_API_KEY is unset (local development) requests pass through;
    main.py logs a warning at startup so the open state is explicit.
    """
    expected = os.getenv("AUTOPILOT_API_KEY")
    if not expected:
        return
    provided = request.headers.get(API_KEY_HEADER)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )


def verify_whatsapp_signature(request: Request, raw_body: bytes) -> None:
    """Verify Meta's X-Hub-Signature-256 against WHATSAPP_APP_SECRET.

    Enforced only when the app secret is configured; without it there is
    nothing to verify against, which is a configuration gap rather than a
    pass. Callers should prefer configuring the secret in any shared deploy.
    """
    secret = os.getenv("WHATSAPP_APP_SECRET")
    if not secret:
        logger.warning(
            "WHATSAPP_APP_SECRET is not set; accepting unverified webhook payload. "
            "Configure it to enable signature verification."
        )
        return
    header = request.headers.get(SIGNATURE_HEADER, "")
    if not header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook signature missing or malformed.",
        )
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = header[len("sha256="):]
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook signature verification failed.",
        )
