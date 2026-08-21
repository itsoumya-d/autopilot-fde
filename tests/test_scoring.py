from backend.demo_data import demo_messages
from backend.deployment.agent_factory import AgentFactory
from backend.discovery.activity_extractor import ActivityExtractor
from backend.discovery.process_miner import ProcessMiner
from backend.models.schema import DeploymentConfig, SafetyStatus
from backend.scoring.aps_engine import APSEngine
from backend.scoring.recommender import Recommender
from backend.scoring.simulator import ProcessSimulator


def _scored_processes():
    processes = ProcessMiner().mine(ActivityExtractor().extract(demo_messages()))
    return processes, [APSEngine().score(process) for process in processes]


def test_score_is_bounded_and_explained():
    _, scores = _scored_processes()
    for score in scores:
        assert 0.0 <= score.score <= 100.0
        assert score.value_score > 0
        assert score.feasibility_score > 0
        assert score.evidence_confidence >= 70
        assert score.factors
        assert score.estimated_monthly_roi_dollars > 0


def test_safety_and_step_feasibility_policies():
    processes, scores = _scored_processes()
    for score in scores:
        assert score.recommended_mode in {SafetyStatus.DRAFT_ONLY, SafetyStatus.ASSISTED, SafetyStatus.AUTONOMOUS, SafetyStatus.OBSERVATION_ONLY}
        assert score.step_feasibilities
        assert len(score.eligible_steps) + len(score.blocked_steps) == len(score.step_feasibilities)


def test_recommender_preserves_safety_and_roi_ranking():
    processes, scores = _scored_processes()
    recommendations = Recommender().recommend(processes, scores)
    assert len(recommendations) == len(scores)
    assert all(recommendation.risk_level in {"Low", "Medium", "High"} for recommendation in recommendations)
    assert all(recommendation.estimated_annual_roi_dollars > 0 for recommendation in recommendations)


def test_monte_carlo_simulator():
    processes, scores = _scored_processes()
    simulator = ProcessSimulator()
    result = simulator.simulate(processes[0], scores[0], runs=500, confidence_threshold=0.80)
    assert result.simulated_runs == 500
    assert 0.0 <= result.straight_through_rate <= 100.0
    assert result.net_monthly_savings_dollars > 0
    assert result.time_to_resolve_minutes_after < result.time_to_resolve_minutes_before


def test_agent_factory_code_generation():
    processes, scores = _scored_processes()
    factory = AgentFactory()
    agent = factory.create_agent(
        process=processes[0],
        config=DeploymentConfig(steps=scores[0].eligible_steps, hitl_required=True),
    )
    assert agent.generated_code is not None
    assert "class WorkflowState(TypedDict):" in agent.generated_code.python_code
    assert "build_agent_graph" in agent.generated_code.python_code
