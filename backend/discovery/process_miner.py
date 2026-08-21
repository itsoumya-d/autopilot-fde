"""Production-grade evidence-preserving process discovery from multi-channel streams."""

import math
from collections import Counter, defaultdict
from hashlib import sha1
from typing import Optional

from backend.models.schema import Activity, Process, ProcessEdge, ProcessMetrics


PROCESS_CATALOG: dict[str, tuple[str, str, list[str]]] = {
    "devops": (
        "DevOps Incident Response & Triage",
        "Orchestrates high-priority telemetry alerts from triage and engineer assignment to production rollback, verification, and post-mortem.",
        [
            "Production deployments and rollbacks require verified SRE command execution.",
            "Post-mortem scheduling and status updates are draft-enabled with human review.",
        ],
    ),
    "support": (
        "Support Escalation Resolution",
        "Turns critical customer bug reports and system blockers into triaged tickets, engineering handoffs, and verified resolutions.",
        [
            "Source tickets and Slack messages are strictly read-only with evidence attribution.",
            "Customer-facing communication remains draft-only until approved by CSM.",
        ],
    ),
    "sales": (
        "Enterprise Deal Desk & Inbound Lead Routing",
        "Discovers the sales pipeline from inbound demo requests to discount approvals, margin reviews, and DocuSign contract dispatches.",
        [
            "Discount authority and custom terms require designated VP/CFO approval gates.",
            "CRM updates and calendar invites are eligible for automated staging.",
        ],
    ),
    "finance": (
        "Invoice Exception & Variance Reconciliation",
        "Tracks vendor invoice mismatches against PO usage logs, approval routing, and remittance generation.",
        [
            "Direct monetary transfers and ledger mutations are strictly blocked from unsupervised execution.",
            "Variance reconciliation and line-item audits operate in verified assistant mode.",
        ],
    ),
    "hr": (
        "Employee Onboarding & IT Provisioning",
        "Manages new hire offer acceptance, background checks, hardware provisioning requests, and calendar onboarding setup.",
        [
            "Sensitive PII and background check records are masked from LLM context windows.",
            "Okta profile creation and welcome emails can be safely staged for HR approval.",
        ],
    ),
    "legal": (
        "Legal Contract Review & NDA Redlining",
        "Analyzes inbound third-party NDAs, cross-checks standard fallback clauses, redlines liability caps, and prepares execution copies.",
        [
            "Legal advice and binding contract signatures are strictly reserved for General Counsel.",
            "Clause diffing and fallback clause insertion can be 90% automated in draft mode.",
        ],
    ),
    "cs": (
        "Customer Success Renewal Triage",
        "Identifies 90-day expiring enterprise accounts, aggregates product usage telemetry, and drafts expansion proposals.",
        [
            "Client negotiation meetings and commercial commitments require CSM leadership signoff.",
            "Telemetry compilation and proposal deck drafting are high-value automation targets.",
        ],
    ),
}


class ProcessMiner:
    """Discovers repeating business workflows, computes graph topology entropy, and constructs state machine edges."""

    MINIMUM_TRACES = 2
    # Observed traces are a sample of a month of stream history; scale the raw
    # trace count to an approximate monthly volume.
    TRACES_TO_MONTHLY_VOLUME = 4.33

    def mine(self, activities: list[Activity]) -> list[Process]:
        cases: dict[str, list[Activity]] = defaultdict(list)
        for activity in activities:
            cases[activity.case_id].append(activity)

        category_cases: dict[str, list[tuple[str, list[Activity]]]] = defaultdict(list)
        for case_id, trace in cases.items():
            ordered = sorted(trace, key=lambda item: item.timestamp)
            if ordered:
                category_cases[ordered[0].category].append((case_id, ordered))

        discovered: list[Process] = []
        for category, traces in category_cases.items():
            if len(traces) < self.MINIMUM_TRACES:
                continue
            discovered.append(self._build_process(category, traces))
            
        return sorted(discovered, key=lambda process: process.name)

    def _build_process(self, category: str, traces: list[tuple[str, list[Activity]]]) -> Process:
        if category in PROCESS_CATALOG:
            title, description, custom_safety = PROCESS_CATALOG[category]
        else:
            title = f"{category.capitalize()} Automated Workflow"
            description = f"Autonomously discovered business process for {category} operations."
            custom_safety = ["Automated steps require verified human-in-the-loop review."]

        signatures = Counter(tuple(activity.name for activity in trace) for _, trace in traces)
        dominant_signature, dominant_count = signatures.most_common(1)[0]
        
        # Select representative trace matching dominant signature
        representative = next(
            trace for _, trace in traces if tuple(activity.name for activity in trace) == dominant_signature
        )

        all_edges: dict[tuple[str, str], list[float]] = defaultdict(list)
        outgoing: Counter[str] = Counter()
        all_actors: set[str] = set()

        for _, trace in traces:
            for current, following in zip(trace, trace[1:]):
                minutes = max(0, (following.timestamp - current.timestamp).total_seconds() / 60)
                all_edges[(current.name, following.name)].append(minutes)
                outgoing[current.name] += 1
            for act in trace:
                all_actors.update(act.actors)

        edges = [
            ProcessEdge(
                source=source,
                target=target,
                frequency=len(durations),
                probability=round(len(durations) / outgoing[source], 2),
                avg_duration_minutes=round(sum(durations) / len(durations), 1),
            )
            for (source, target), durations in all_edges.items()
        ]

        # Shannon Graph Transition Entropy. Computed on UNROUNDED probabilities —
        # rounding first can make them sum to something other than 1 and skew H.
        # Edges are grouped by source once (O(V+E)) instead of rescanned per node.
        edges_by_source: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for (source, target), durations in all_edges.items():
            edges_by_source[source].append((target, len(durations) / outgoing[source]))

        entropy = 0.0
        for source_edges in edges_by_source.values():
            for _, probability in source_edges:
                if probability > 0:
                    entropy -= probability * math.log2(probability)

        durations = [
            (trace[-1].timestamp - trace[0].timestamp).total_seconds() / 60
            for _, trace in traces if len(trace) > 1
        ]
        count = len(traces)

        base_safety_notes = [
            "Source messages and telemetry are read-only; all activity nodes link to verifiable evidence.",
            "Customer-facing communication and write mutations remain gated behind Human-in-the-Loop review.",
        ]
        safety_notes = base_safety_notes + custom_safety

        return Process(
            id=f"process-{sha1(category.encode()).hexdigest()[:10]}",
            name=title,
            description=description,
            category=category,
            activities=representative,
            edges=edges,
            metrics=ProcessMetrics(
                volume_per_month=int(count * self.TRACES_TO_MONTHLY_VOLUME),
                avg_completion_minutes=round(sum(durations) / len(durations), 1) if durations else 0.0,
                trace_count=count,
                pattern_consistency=round(dominant_count / count, 2),
                evidence_count=sum(len(trace) for _, trace in traces),
                entropy_score=round(entropy, 3),
                unique_actors_count=len(all_actors),
            ),
            evidence_case_ids=[case_id for case_id, _ in traces],
            safety_notes=safety_notes,
        )
