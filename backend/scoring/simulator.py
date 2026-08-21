"""Pre-deployment discrete-event Monte Carlo simulator for workflow automation forecasting.

Simulates 1,000 executions of a proposed agent branch across probabilistic failure modes,
estimating Straight-Through Rate (STR %), latency reductions, token consumption, and net ROI.
"""

import random
from backend.models.schema import (
    Process,
    APScore,
    SimulationResult,
    StepActionType,
)


class ProcessSimulator:
    """Simulates workflow execution to forecast operational metrics before production deployment."""

    def simulate(
        self,
        process: Process,
        score: APScore,
        runs: int = 1000,
        confidence_threshold: float = 0.80,
        seed: int = 42,
    ) -> SimulationResult:
        """Runs a Monte Carlo simulation of the process under agent automation."""
        # A dedicated Random instance keeps runs reproducible without mutating the
        # global RNG (which correlated results across concurrent requests).
        rng = random.Random(seed)

        straight_through_count = 0
        escalation_count = 0
        total_time_saved_minutes = 0.0
        total_tokens_consumed = 0
        safety_violations_intercepted = 0
        step_durations_after: dict[str, list[float]] = {act.name: [] for act in process.activities}

        manual_duration = max(10.0, process.metrics.avg_completion_minutes)

        for _ in range(runs):
            case_failed_or_escalated = False
            case_time_saved = 0.0

            for step_feasibility in score.step_feasibilities:
                step_name = step_feasibility.step_name
                action_type = step_feasibility.action_type
                is_auto = step_feasibility.is_automatable

                # Base automated execution latency (2 to 8 seconds = ~0.08 minutes)
                step_auto_duration = rng.uniform(0.05, 0.15)
                # Historical manual step duration
                step_manual_duration = manual_duration / max(1, len(process.activities))

                if not is_auto or action_type == StepActionType.CRITICAL_TRANSACTION:
                    # Step is blocked from automation -> Handled by human
                    safety_violations_intercepted += 1
                    case_failed_or_escalated = True
                    step_durations_after[step_name].append(step_manual_duration)
                else:
                    # Step is automated -> sample agent confidence
                    simulated_agent_confidence = rng.betavariate(
                        alpha=step_feasibility.feasibility_score * 10,
                        beta=(1.0 - step_feasibility.feasibility_score) * 10 + 0.1,
                    )

                    # Tokens consumed per automated reasoning step (~400-800 tokens)
                    total_tokens_consumed += rng.randint(400, 800)

                    if simulated_agent_confidence < confidence_threshold or step_feasibility.requires_approval:
                        # Escalated to human review queue
                        case_failed_or_escalated = True
                        # Human review takes ~20% of manual time (verification only)
                        review_duration = step_manual_duration * 0.25
                        step_durations_after[step_name].append(review_duration)
                        case_time_saved += (step_manual_duration - review_duration)
                    else:
                        # Successful straight-through automation
                        step_durations_after[step_name].append(step_auto_duration)
                        case_time_saved += (step_manual_duration - step_auto_duration)

            if not case_failed_or_escalated:
                straight_through_count += 1
            else:
                escalation_count += 1

            total_time_saved_minutes += case_time_saved

        # Aggregate Metrics
        str_pct = round((straight_through_count / runs) * 100.0, 1)
        escalation_pct = round((escalation_count / runs) * 100.0, 1)

        # Average duration after automation per run
        avg_after_minutes = round(
            sum(
                sum(durations) / len(durations) if durations else 0.0
                for durations in step_durations_after.values()
            ),
            1
        )

        # Identify bottleneck step (step with highest remaining duration)
        bottleneck_step = max(
            step_durations_after.keys(),
            key=lambda k: sum(step_durations_after[k]) / len(step_durations_after[k]) if step_durations_after[k] else 0.0,
            default="None",
        )

        # Monthly extrapolations
        monthly_volume = max(10, process.metrics.volume_per_month)
        avg_saved_per_run_hours = (total_time_saved_minutes / runs) / 60.0
        monthly_hours_saved = round(monthly_volume * avg_saved_per_run_hours, 1)

        # Pricing model: $0.000003 / token (Claude 3.5 / GPT-4o mini tier), $65/hr labor
        monthly_token_cost = round((total_tokens_consumed / runs) * monthly_volume * 0.000003, 2)
        net_monthly_savings = round((monthly_hours_saved * 65.0) - monthly_token_cost, 2)

        return SimulationResult(
            process_id=process.id,
            simulated_runs=runs,
            confidence_threshold=confidence_threshold,
            straight_through_rate=str_pct,
            human_escalation_rate=escalation_pct,
            estimated_monthly_hours_saved=monthly_hours_saved,
            estimated_monthly_token_cost=monthly_token_cost,
            net_monthly_savings_dollars=net_monthly_savings,
            simulated_bottleneck_step=bottleneck_step,
            time_to_resolve_minutes_before=round(manual_duration, 1),
            time_to_resolve_minutes_after=avg_after_minutes,
            safety_violations_caught=safety_violations_intercepted // runs,
        )
