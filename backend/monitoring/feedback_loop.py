"""Feedback is recorded for review; it never expands an agent’s permissions automatically."""

from dataclasses import dataclass, field

from backend.models.schema import APScore, Process
from backend.scoring.aps_engine import APSEngine


@dataclass
class FeedbackLoop:
    scorer: APSEngine = field(default_factory=APSEngine)
    reviews: list[dict[str, object]] = field(default_factory=list)

    def record_review(self, *, process_id: str, accepted: bool, reason: str = "") -> None:
        self.reviews.append({"process_id": process_id, "accepted": accepted, "reason": reason})

    def rescore_process(self, process: Process) -> APScore:
        """Recompute only from observable process evidence.

        Human review outcomes are available to operators, but increasing traffic or
        changing draft-only policy always requires a separate approval decision.
        """
        return self.scorer.score(process)
