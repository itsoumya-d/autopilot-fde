"""Dead-letter queue: failed agent actions preserved for human review.

A failed INTERNAL_ACTION webhook lands here with full context instead of
vanishing into a stack trace. Review is a human decision — 'discard' or
'requeue' (requeue is an audited marker; actual retry re-runs through the
normal guarded path). When the deployment has a signing secret, the reviewer
must present the failed branch's identity token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..deployment import execution_guards as guards
from ..security import (
    AGENT_TOKEN_HEADER,
    require_api_key,
    verify_agent_token,
)

router = APIRouter()


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(discard|requeue)$")
    notes: str = Field(default="", max_length=2000)


@router.get("/")
async def list_dead_letters(status: str = "pending") -> dict:
    entries = guards.dead_letter_list(status=status)
    return {"count": len(entries), "entries": entries}


@router.post("/{entry_id}/review", dependencies=[Depends(require_api_key)])
async def review_dead_letter(entry_id: str, request: ReviewRequest,
                             http: Request) -> dict:
    entries = [e for e in guards.dead_letter_list(status="pending")
               if e["id"] == entry_id]
    if not entries:
        already = [e for e in
                   (guards.dead_letter_list("reviewed:discard")
                    + guards.dead_letter_list("reviewed:requeue"))
                   if e["id"] == entry_id]
        raise HTTPException(
            status_code=409 if already else 404,
            detail="Entry already reviewed" if already else "Dead-letter entry not found",
        )
    entry = entries[0]
    # Identity check only binds when the deployment issues tokens at all.
    secret_present = bool(__import__("os").getenv("AUTOPILOT_AGENT_SECRET")
                          or __import__("os").getenv("AUTOPILOT_API_KEY"))
    token = http.headers.get(AGENT_TOKEN_HEADER)
    if entry["agent_id"] and secret_present:
        if not verify_agent_token(entry["agent_id"], token):
            raise HTTPException(
                status_code=401,
                detail=f"Missing or invalid {AGENT_TOKEN_HEADER} for this branch.",
            )
    actor = http.headers.get("X-Acting-User", "").strip() or "anonymous"
    return guards.dead_letter_review(entry_id, reviewer=actor,
                                     decision=request.decision,
                                     notes=request.notes)
