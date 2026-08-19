"""Mathematically grounded Automation Potential Score (APS) Engine.

Computes a calibrated opportunity score from Graph Entropy, Actor Handoff Dispersion,
Step-Level Risk Analysis, and Empirical Trace Consistency.
"""

from backend.models.schema import (
    APScore,
    Process,
    SafetyStatus,
    StepActionType,
    StepFeasibility,
)


class APSEngine:
    """Calculates APS score, step-by-step feasibility, and financial ROI models."""

    # Action risk classifications for enterprise safety
    STEP_CLASSIFIERS: dict[str, tuple[StepActionType, float, bool, list[str]]] = {
        # DevOps
        "Alert triggered": (StepActionType.READ_ONLY, 0.98, False, ["Automated ingestion & normalization"]),
        "Incident triaged": (StepActionType.READ_ONLY, 0.90, False, ["Log parsing & telemetry correlation"]),
        "Engineer assigned": (StepActionType.INTERNAL_ACTION, 0.85, False, ["On-call schedule lookup & Jira assignment"]),
        "Mitigation deployed": (StepActionType.CRITICAL_TRANSACTION, 0.20, True, ["High risk: Production rollback requires SRE signoff"]),
        "Post-mortem scheduled": (StepActionType.DRAFT_ONLY, 0.92, False, ["Summary generation & calendar dispatch"]),

        # Support
        "Customer escalation received": (StepActionType.READ_ONLY, 0.98, False, ["Ingestion & priority tagging"]),
        "Issue triaged": (StepActionType.READ_ONLY, 0.92, False, ["Error reproduction & diagnostic lookup"]),
        "Specialist assigned": (StepActionType.INTERNAL_ACTION, 0.88, False, ["Team queue assignment"]),
        "Customer update drafted": (StepActionType.DRAFT_ONLY, 0.90, True, ["Drafts response for CSM review"]),
        "Resolution confirmed": (StepActionType.INTERNAL_ACTION, 0.75, True, ["Verification against customer metrics"]),

        # Sales Deal Desk
        "Discount request submitted": (StepActionType.READ_ONLY, 0.95, False, ["CRM request intake"]),
        "Margin analysis completed": (StepActionType.READ_ONLY, 0.92, False, ["Margin calculator & unit economics"]),
        "Executive approval requested": (StepActionType.INTERNAL_ACTION, 0.80, True, ["VP Sales approval routing"]),
        "Quote schedule drafted": (StepActionType.DRAFT_ONLY, 0.88, True, ["DocuSign quote generation"]),
        "Contract sent for execution": (StepActionType.EXTERNAL_WRITE, 0.40, True, ["Legal dispatch approval required"]),

        # Inbound SDR
        "Lead captured": (StepActionType.READ_ONLY, 0.98, False, ["Form intake & enrich via Clearbit"]),
        "Lead qualified": (StepActionType.READ_ONLY, 0.94, False, ["ICP matrix matching"]),
        "Demo scheduled": (StepActionType.INTERNAL_ACTION, 0.92, False, ["ChiliPiper/Calendly routing"]),
        "Briefing prepared": (StepActionType.DRAFT_ONLY, 0.95, False, ["1-page briefing notes for AE"]),

        # Finance
        "Invoice exception received": (StepActionType.READ_ONLY, 0.95, False, ["OCR parsing & PO matching"]),
        "Invoice reconciled": (StepActionType.INTERNAL_ACTION, 0.85, False, ["ERP line item cross-checking"]),
        "Payment approval requested": (StepActionType.INTERNAL_ACTION, 0.65, True, ["Controller approval gate"]),
        "Payment confirmed": (StepActionType.CRITICAL_TRANSACTION, 0.15, True, ["Direct wire transfer: Zero automation"]),

        # HR
        "Offer accepted": (StepActionType.READ_ONLY, 0.98, False, ["Applicant tracking event sync"]),
        "Background check initiated": (StepActionType.INTERNAL_ACTION, 0.90, False, ["Checkr API trigger"]),
        "Hardware provisioning requested": (StepActionType.INTERNAL_ACTION, 0.88, False, ["IT asset ticket creation"]),
        "Onboarding scheduled": (StepActionType.DRAFT_ONLY, 0.92, False, ["Welcome email & calendar series"]),

        # Legal
        "Contract received for review": (StepActionType.READ_ONLY, 0.98, False, ["PDF parsing & NDA classification"]),
        "Contract redlined": (StepActionType.DRAFT_ONLY, 0.82, True, ["Clause diffing against company standard playbook"]),
        "Revised terms drafted": (StepActionType.DRAFT_ONLY, 0.85, True, ["Redline summary for General Counsel"]),
        "Execution copy finalized": (StepActionType.INTERNAL_ACTION, 0.70, True, ["DocuSign package assembly"]),

        # CS
        "Renewal risk alerted": (StepActionType.READ_ONLY, 0.98, False, ["Gainsight telemetry trigger"]),
        "EBR briefing prepared": (StepActionType.DRAFT_ONLY, 0.92, False, ["Telemetry deck compilation"]),
        "Expansion proposal drafted": (StepActionType.DRAFT_ONLY, 0.85, True, ["Pricing proposal generator"]),
        "Renewal confirmed": (StepActionType.INTERNAL_ACTION, 0.60, True, ["Contract renewal booking in Salesforce"]),
    }

    def score(self, process: Process) -> APScore:
        metrics = process.metrics
        
        # 1. Step-Level Feasibilities
        step_feasibilities = self._evaluate_steps(process)
        eligible_steps = [s.step_name for s in step_feasibilities if s.is_automatable]
        blocked_steps = [s.step_name for s in step_feasibilities if not s.is_automatable]
        
        avg_step_feasibility = (
            sum(s.feasibility_score for s in step_feasibilities) / len(step_feasibilities)
            if step_feasibilities else 0.5
        )

        # 2. Mathematical Factors
        # Repeatability from trace pattern consistency
        repeatability = metrics.pattern_consistency
        
        # Structuredness from step count and data completeness
        structuredness = min(1.0, len(process.activities) / 5.0) * 0.60 + 0.40
        
        # Volume factor normalized against enterprise baseline (e.g. 40 runs/month)
        volume_norm = min(1.0, metrics.volume_per_month / 40.0)
        
        # Data availability
        data_availability = 0.95
        
        # Mathematical Graph Complexity C(p)
        complexity = self._compute_graph_complexity(process, step_feasibilities)
        
        # Evidence confidence dampening
        evidence = min(0.98, 0.40 + 0.10 * metrics.trace_count + 0.02 * metrics.evidence_count)

        # 3. Value & Feasibility Components
        # Value = Volume (45%) + Time Duration (35%) + Repeatability (20%)
        duration_factor = min(1.0, metrics.avg_completion_minutes / 180.0)
        value = 0.45 * volume_norm + 0.35 * duration_factor + 0.20 * repeatability
        
        # Feasibility = Step Feasibility (50%) + Data (30%) + Low Complexity (20%)
        feasibility = 0.50 * avg_step_feasibility + 0.30 * data_availability + 0.20 * (1.0 - complexity)

        # Final APS composite score (0 - 100)
        raw_opportunity = 100.0 * value * feasibility * evidence
        opportunity = round(min(98.5, max(15.0, raw_opportunity)), 1)

        # 4. Economic ROI Modeling ($65/hr knowledge worker baseline, $0.000003 per token)
        deployable_pct = round((len(eligible_steps) / len(process.activities)) * 100.0 if process.activities else 0.0, 1)
        hours_saved_monthly = round(
            metrics.volume_per_month * (metrics.avg_completion_minutes / 60.0) * (deployable_pct / 100.0) * 0.45, 1
        )
        token_cost_monthly = metrics.volume_per_month * 3500 * 0.000003  # ~3.5k tokens per run
        monthly_roi_dollars = round((hours_saved_monthly * 65.0) - token_cost_monthly, 2)

        # 5. Recommendation Policy
        recommendation = self._generate_recommendation(opportunity, evidence, eligible_steps, blocked_steps)
        recommended_mode = (
            SafetyStatus.AUTONOMOUS if (opportunity > 80 and not blocked_steps)
            else SafetyStatus.ASSISTED if opportunity > 60
            else SafetyStatus.DRAFT_ONLY if opportunity > 40
            else SafetyStatus.OBSERVATION_ONLY
        )

        return APScore(
            process_id=process.id,
            score=opportunity,
            value_score=round(value * 100.0, 1),
            feasibility_score=round(feasibility * 100.0, 1),
            evidence_confidence=round(evidence * 100.0, 1),
            factors={
                "Repeatability": round(repeatability * 100.0, 1),
                "Structuredness": round(structuredness * 100.0, 1),
                "Volume Velocity": round(volume_norm * 100.0, 1),
                "Digital Evidence": round(data_availability * 100.0, 1),
                "Graph Complexity (Inverse)": round((1.0 - complexity) * 100.0, 1),
            },
            recommendation=recommendation,
            recommended_mode=recommended_mode,
            eligible_steps=eligible_steps,
            blocked_steps=blocked_steps,
            step_feasibilities=step_feasibilities,
            deployable_pct=deployable_pct,
            estimated_hours_saved_monthly=hours_saved_monthly,
            estimated_monthly_roi_dollars=monthly_roi_dollars,
        )

    def _evaluate_steps(self, process: Process) -> list[StepFeasibility]:
        """Classifies each step's action type and calculates automatable confidence."""
        results: list[StepFeasibility] = []
        for act in process.activities:
            if act.name in self.STEP_CLASSIFIERS:
                action_type, score, req_approval, risks = self.STEP_CLASSIFIERS[act.name]
            else:
                # Fallback heuristic for open-domain steps
                name_lower = act.name.lower()
                if any(w in name_lower for w in ("pay", "wire", "transfer", "delete", "destroy", "sign")):
                    action_type = StepActionType.CRITICAL_TRANSACTION
                    score = 0.15
                    req_approval = True
                    risks = ["Critical transaction requires human signoff"]
                elif any(w in name_lower for w in ("draft", "summary", "brief", "email")):
                    action_type = StepActionType.DRAFT_ONLY
                    score = 0.88
                    req_approval = True
                    risks = ["Draft mode enabled with human review"]
                elif any(w in name_lower for w in ("fetch", "get", "read", "parse", "alert", "triage")):
                    action_type = StepActionType.READ_ONLY
                    score = 0.95
                    req_approval = False
                    risks = ["Safe read-only step"]
                else:
                    action_type = StepActionType.INTERNAL_ACTION
                    score = 0.70
                    req_approval = True
                    risks = ["Internal action requiring review gate"]

            is_auto = score >= 0.70 and action_type != StepActionType.CRITICAL_TRANSACTION
            results.append(StepFeasibility(
                step_name=act.name,
                action_type=action_type,
                feasibility_score=score,
                is_automatable=is_auto,
                requires_approval=req_approval,
                risk_factors=risks,
            ))
        return results

    @staticmethod
    def _compute_graph_complexity(process: Process, step_feasibilities: list[StepFeasibility]) -> float:
        """Graph complexity derived from transition entropy, actor dispersion, and critical step penalty."""
        # Graph Shannon Entropy (normalized 0 - 1)
        entropy_norm = min(1.0, process.metrics.entropy_score / 3.0)
        
        # Actor handoff dispersion (more unique actors = higher cross-team friction)
        actor_count = max(1, process.metrics.unique_actors_count)
        step_count = max(1, len(process.activities))
        actor_friction = min(1.0, (actor_count - 1) / step_count)
        
        # Critical action penalty
        critical_count = sum(1 for s in step_feasibilities if s.action_type == StepActionType.CRITICAL_TRANSACTION)
        critical_penalty = min(1.0, critical_count / step_count)

        complexity = 0.35 * entropy_norm + 0.35 * actor_friction + 0.30 * critical_penalty
        return round(min(0.95, max(0.10, complexity)), 3)

    @staticmethod
    def _generate_recommendation(score: float, evidence: float, eligible: list[str], blocked: list[str]) -> str:
        if evidence < 0.70:
            return "Continue observing: evidence volume is accumulating before production authorization."
        if not eligible:
            return "All steps involve critical or legally binding actions. Maintain workflow in 100% human-operated mode."
        if not blocked:
            return f"High-confidence automation candidate ({score:.1f}/100). All {len(eligible)} step(s) are eligible for deployment."
        return f"Deploy staged agent for {len(eligible)} eligible step(s) with HITL checkpoints. {len(blocked)} step(s) remain human-owned."
