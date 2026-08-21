"""Unified schema for AutoPilot FDE — satisfies backend API, ML engine, simulation, and code generation."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ── Channel types ──────────────────────────────────────────────────────────

class ChannelType(str, Enum):
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    CALL = "call"


class ChannelStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Channel(BaseModel):
    id: str
    type: ChannelType
    name: str = "Unnamed channel"
    # Server-side only. Never serialized through ChannelPublic responses.
    credentials: dict[str, str] = Field(default_factory=dict, exclude=True)
    status: ChannelStatus = ChannelStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message_count: int = 0


class ChannelPublic(BaseModel):
    """Wire representation of a channel -- deliberately credential-free."""

    id: str
    type: ChannelType
    name: str = "Unnamed channel"
    status: ChannelStatus = ChannelStatus.ACTIVE
    created_at: datetime
    message_count: int = 0

    @classmethod
    def from_channel(cls, channel: Channel) -> "ChannelPublic":
        return cls(
            id=channel.id, type=channel.type, name=channel.name,
            status=channel.status, created_at=channel.created_at,
            message_count=channel.message_count,
        )


# ── Message ────────────────────────────────────────────────────────────────

class Message(BaseModel):
    id: str
    channel_id: str = ""
    sender: str
    content: str
    timestamp: datetime
    thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Activity ───────────────────────────────────────────────────────────────

class Activity(BaseModel):
    id: str
    name: str
    category: str
    case_id: str = ""
    actors: list[str] = Field(default_factory=list)
    timestamp: datetime
    source_messages: list[str] = Field(default_factory=list)
    evidence: str = ""
    confidence: float = 1.0


# ── Process ────────────────────────────────────────────────────────────────

class ProcessEdge(BaseModel):
    source: str
    target: str
    frequency: int = 1
    probability: float = 1.0
    avg_duration_minutes: float = 0.0


class ProcessMetrics(BaseModel):
    volume_per_month: int = 0
    avg_completion_minutes: float = 0.0
    trace_count: int = 0
    pattern_consistency: float = 0.0
    evidence_count: int = 0
    error_rate: float = 0.0
    entropy_score: float = 0.0
    unique_actors_count: int = 0


class Process(BaseModel):
    id: str
    name: str
    description: str = ""
    category: str = "general"
    activities: list[Activity] = Field(default_factory=list)
    edges: list[ProcessEdge] = Field(default_factory=list)
    metrics: ProcessMetrics = Field(default_factory=ProcessMetrics)
    volume: int = 0
    avg_duration: float = 0.0
    evidence_case_ids: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


# ── Step Feasibility & Safety ──────────────────────────────────────────────

class StepActionType(str, Enum):
    READ_ONLY = "read_only"         # Safe: data extraction, triage, lookup
    DRAFT_ONLY = "draft_only"       # Safe: response drafting, summary generation
    INTERNAL_ACTION = "internal"    # Moderate: Jira update, CRM status update
    EXTERNAL_WRITE = "external"     # High: Send email, post message
    CRITICAL_TRANSACTION = "critical" # Blocked: Payment, credential grant, delete


class StepFeasibility(BaseModel):
    step_name: str
    action_type: StepActionType
    feasibility_score: float        # 0.0 to 1.0
    is_automatable: bool
    requires_approval: bool
    risk_factors: list[str] = Field(default_factory=list)


# ── Scoring ────────────────────────────────────────────────────────────────

class SafetyStatus(str, Enum):
    OBSERVATION_ONLY = "observation_only"
    DRAFT_ONLY = "draft_only"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"


class APScore(BaseModel):
    process_id: str
    score: float
    value_score: float = 0.0
    feasibility_score: float = 0.0
    evidence_confidence: float = 0.0
    factors: dict[str, float] = Field(default_factory=dict)
    recommendation: str = ""
    recommended_mode: SafetyStatus = SafetyStatus.OBSERVATION_ONLY
    eligible_steps: list[str] = Field(default_factory=list)
    blocked_steps: list[str] = Field(default_factory=list)
    step_feasibilities: list[StepFeasibility] = Field(default_factory=list)
    deployable_pct: float = 0.0
    estimated_hours_saved_monthly: float = 0.0
    estimated_monthly_roi_dollars: float = 0.0


class Recommendation(BaseModel):
    process_id: str
    process_name: str
    priority: int
    wave: str = "Later"
    estimated_hours_saved: float = 0.0
    estimated_annual_roi_dollars: float = 0.0
    risk_level: str = "Low"
    missing_capabilities: list[str] = Field(default_factory=list)


# ── Simulation ─────────────────────────────────────────────────────────────

class SimulationResult(BaseModel):
    process_id: str
    simulated_runs: int = 1000
    confidence_threshold: float = 0.8
    straight_through_rate: float        # % automated without human intervention
    human_escalation_rate: float        # % routed to human review
    estimated_monthly_hours_saved: float
    estimated_monthly_token_cost: float
    net_monthly_savings_dollars: float
    simulated_bottleneck_step: str
    time_to_resolve_minutes_before: float
    time_to_resolve_minutes_after: float
    safety_violations_caught: int = 0


# ── Deployment & Code Generation ───────────────────────────────────────────

class DeploymentMode(str, Enum):
    DRAFT = "draft"            # Everything lands in a review queue; zero external side effects
    ASSISTED = "assisted"      # Internal read/staging actions automated, writes gated
    AUTONOMOUS = "autonomous"  # Eligible steps run straight-through; criticals still gated


class DeploymentConfig(BaseModel):
    mode: DeploymentMode = DeploymentMode.DRAFT
    traffic_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    enabled_steps: list[str] = Field(default_factory=list)
    approval_required: bool = True
    confidence_threshold: float = Field(default=0.8, ge=0.5, le=0.99)


class AgentStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    DEPLOYING = "deploying"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"


class GeneratedAgentCode(BaseModel):
    process_id: str
    agent_name: str
    python_code: str
    tools: list[str]
    entrypoint: str
    langgraph_spec: dict[str, Any] = Field(default_factory=dict)


class AgentBranch(BaseModel):
    id: str
    process_id: str
    name: str
    status: AgentStatus = AgentStatus.PENDING_APPROVAL
    config: DeploymentConfig = Field(default_factory=DeploymentConfig)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metrics: dict[str, Any] = Field(default_factory=dict)
    generated_code: GeneratedAgentCode | None = None


class DashboardSummary(BaseModel):
    processes_discovered: int = 0
    average_opportunity_score: float = 0.0
    evidence_backed_hours: float = 0.0
    active_agents: int = 0
    pending_approvals: int = 0
