"""Unified schema for AutoPilot FDE — satisfies backend API, ML engine, simulation, and code generation."""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


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
    credentials: Dict[str, str] = Field(default_factory=dict)
    status: ChannelStatus = ChannelStatus.ACTIVE


# ── Message ────────────────────────────────────────────────────────────────

class Message(BaseModel):
    id: str
    channel_id: str = ""
    sender: str
    content: str
    timestamp: datetime
    thread_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Activity ───────────────────────────────────────────────────────────────

class Activity(BaseModel):
    id: str
    name: str
    category: str
    case_id: str = ""
    actors: List[str] = Field(default_factory=list)
    timestamp: datetime
    source_messages: List[str] = Field(default_factory=list)
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
    activities: List[Activity] = Field(default_factory=list)
    edges: List[ProcessEdge] = Field(default_factory=list)
    metrics: ProcessMetrics = Field(default_factory=ProcessMetrics)
    volume: int = 0
    avg_duration: float = 0.0
    evidence_case_ids: List[str] = Field(default_factory=list)
    safety_notes: List[str] = Field(default_factory=list)


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
    risk_factors: List[str] = Field(default_factory=list)


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
    factors: Dict[str, float] = Field(default_factory=dict)
    recommendation: str = ""
    recommended_mode: SafetyStatus = SafetyStatus.OBSERVATION_ONLY
    eligible_steps: List[str] = Field(default_factory=list)
    blocked_steps: List[str] = Field(default_factory=list)
    step_feasibilities: List[StepFeasibility] = Field(default_factory=list)
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
    missing_capabilities: List[str] = Field(default_factory=list)


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

class DeploymentConfig(BaseModel):
    deploy_percentage: float = 100.0
    steps: List[str] = Field(default_factory=list)
    hitl_required: bool = True
    hitl_threshold: float = 0.8


class AgentStatus(str, Enum):
    DEPLOYING = "deploying"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"


class GeneratedAgentCode(BaseModel):
    process_id: str
    agent_name: str
    python_code: str
    tools: List[str]
    entrypoint: str
    langgraph_spec: Dict[str, Any] = Field(default_factory=dict)


class AgentBranch(BaseModel):
    id: str
    process_id: str
    name: str
    status: AgentStatus = AgentStatus.DEPLOYING
    config: DeploymentConfig = Field(default_factory=DeploymentConfig)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    generated_code: Optional[GeneratedAgentCode] = None


class DashboardSummary(BaseModel):
    processes_discovered: int = 0
    average_opportunity_score: float = 0.0
    evidence_backed_hours: float = 0.0
    active_agents: int = 0
    pending_approvals: int = 0
