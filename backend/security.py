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
    nothing to verify against. Set AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS=1 to
    invert that default in shared deployments: unverified payloads are then
    rejected with 503 instead of accepted with a warning, so a misconfigured
    secret fails loudly rather than silently opening an injection vector.
    """
    secret = os.getenv("WHATSAPP_APP_SECRET")
    if not secret:
        if webhook_verification_required():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS is set but WHATSAPP_APP_SECRET "
                    "is not configured; refusing unverified webhook payloads."
                ),
            )
        logger.warning(
            "WHATSAPP_APP_SECRET is not set; accepting unverified webhook payload. "
            "Configure it to enable signature verification, or set "
            "AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS=1 to refuse unsigned payloads."
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


def verify_slack_signature(request: Request, raw_body: bytes) -> None:
    """Verify Slack's v0 signature (X-Slack-Signature) when configured.

    Enforced only when SLACK_SIGNING_SECRET is set; without it interactive
    payloads are accepted with a warning (local demo). Shared deployments must
    configure the secret — the route refuses unsigned traffic otherwise.
    """
    secret = os.getenv("SLACK_SIGNING_SECRET")
    if not secret:
        logger.warning(
            "SLACK_SIGNING_SECRET is not set; accepting unverified Slack "
            "interactive payload. Configure it for anything internet-reachable."
        )
        return
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not timestamp or not signature.startswith("v0="):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Slack signature missing or malformed.",
        )
    basename = f"v0:{timestamp}:".encode() + raw_body
    expected = "v0=" + hmac.new(secret.encode(), basename, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Slack signature verification failed.",
        )


def webhook_verification_required() -> bool:
    """True when unsigned webhook payloads must be refused outright."""
    return os.getenv("AUTOPILOT_REQUIRE_SIGNED_WEBHOOKS", "").strip() == "1"


def cors_origins_from_env() -> list[str]:
    """Browser origins allowed by CORS, from AUTOPILOT_CORS_ORIGINS.

    Comma-separated; defaults to the local Next.js dev server. In production
    set this to your dashboard origin explicitly -- the default exists for
    first-run ergonomics, not as a deployment recommendation.
    """
    raw = os.getenv("AUTOPILOT_CORS_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]


class RateLimiter:
    """In-process sliding-window limiter for expensive endpoints.

    Keyed by client IP, no external dependencies, sized for a single-process
    demo service -- the honest scope of this backend. Set
    AUTOPILOT_RATE_LIMIT_PER_MIN=0 to disable (tests, benchmarks).
    """

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def check(self, key: str, limit_per_min: int | None = None) -> None:
        import time

        if limit_per_min is None:
            limit_per_min = int(os.getenv("AUTOPILOT_RATE_LIMIT_PER_MIN", "60"))
        if limit_per_min <= 0:
            return
        now = time.monotonic()
        window = self._hits.setdefault(key, [])
        cutoff = now - 60.0
        while window and window[0] < cutoff:
            window.pop(0)
        if len(window) >= limit_per_min:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit_per_min}/min). "
                       "Retry shortly or raise AUTOPILOT_RATE_LIMIT_PER_MIN.",
            )
        window.append(now)


rate_limiter = RateLimiter()


def client_key(request: Request) -> str:
    """Best-effort client identity for rate limiting behind no proxy."""
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# ── Per-agent workload identity (v0.6 Governed Autonomy) ────────────────────
#
# The 2026 enterprise posture is explicit: an agent must carry a verifiable
# workload identity, not just an API key in a config file. AutoPilot FDE
# issues each deployed branch an HMAC-SHA256 token derived from the server
# secret and the agent id; mutating surfaces can require it and attribute the
# action to that exact branch in the audit trail.
#
# Threat model, honestly: HMAC proves possession of a shared secret, not
# uniqueness of the requester — the right strength for a self-hosted control
# plane that already trusts AUTOPILOT_API_KEY. Rotation = redeploy (stop +
# fresh deploy), which keeps the story simple and auditable.

AGENT_TOKEN_HEADER = "X-Autopilot-Agent-Token"


def _identity_secret() -> str:
    """Server-side signing secret; falls back to AUTOPILOT_API_KEY."""
    return (os.getenv("AUTOPILOT_AGENT_SECRET")
            or os.getenv("AUTOPILOT_API_KEY")
            or "")


def issue_agent_token(agent_id: str, secret: str | None = None) -> str | None:
    """Token for one deployed branch; None when no server secret is set.

    A deployment without any secret is explicitly local-demo mode: tokens are
    not issued rather than forged from a public constant.
    """
    key = secret if secret is not None else _identity_secret()
    if not key:
        return None
    return hmac.new(key.encode(), f"agent:{agent_id}".encode(),
                    hashlib.sha256).hexdigest()


def verify_agent_token(agent_id: str, provided: str | None,
                       secret: str | None = None) -> bool:
    """Constant-time verification; False when anything is missing."""
    expected = issue_agent_token(agent_id, secret)
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected, provided)
