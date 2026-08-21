"""Production recommendation engine prioritizing automation deployment waves by Net Dollar ROI."""

from backend.models.schema import APScore, Process, Recommendation


class Recommender:
    """Prioritizes workflow automation waves and generates actionable capability gap analyses."""

    def recommend(self, processes: list[Process], scores: list[APScore]) -> list[Recommendation]:
        process_map = {process.id: process for process in processes}

        # Rank by Economic Impact: (APS Score / 100) * Estimated Monthly ROI Dollars
        ranked = sorted(
            scores,
            key=lambda s: (s.score / 100.0) * max(100.0, s.estimated_monthly_roi_dollars),
            reverse=True,
        )

        recommendations: list[Recommendation] = []
        for index, score in enumerate(ranked, start=1):
            process = process_map.get(score.process_id)
            process_name = process.name if process else "Discovered Workflow"

            missing: list[str] = []
            if score.evidence_confidence < 75.0:
                missing.append("Accumulate more thread observations to cross the 75% confidence threshold.")
            if score.blocked_steps:
                blocked_preview = ", ".join(score.blocked_steps[:2])
                missing.append(
                    f"Deploy approval gate for {len(score.blocked_steps)} high-risk step(s): {blocked_preview}.")
            if score.factors.get("Graph Complexity (Inverse)", 100.0) < 50.0:
                missing.append("Standardize input payloads to reduce graph branching entropy.")

            # Assign Waves
            if score.score >= 65.0 and len(score.eligible_steps) >= 2:
                wave = "Now"
                risk_level = "Low" if not score.blocked_steps else "Medium"
            elif score.score >= 45.0 and score.eligible_steps:
                wave = "Next"
                risk_level = "Medium" if len(score.blocked_steps) <= 2 else "High"
            else:
                wave = "Later"
                risk_level = "High"

            annual_roi = round(score.estimated_monthly_roi_dollars * 12.0, 2)

            recommendations.append(Recommendation(
                process_id=score.process_id,
                process_name=process_name,
                priority=index,
                wave=wave,
                estimated_hours_saved=score.estimated_hours_saved_monthly,
                estimated_annual_roi_dollars=annual_roi,
                risk_level=risk_level,
                missing_capabilities=missing,
            ))

        return recommendations
