from backend.demo_data import demo_messages
from backend.discovery.activity_extractor import ActivityExtractor
from backend.discovery.process_graph import BusinessProcessGraph
from backend.discovery.process_miner import ProcessMiner


def test_extraction_retains_message_evidence():
    activities = ActivityExtractor().extract(demo_messages())
    assert len(activities) > 50
    first = activities[0]
    assert first.source_messages
    assert first.evidence
    assert 0.75 <= first.confidence <= 1.0


def test_miner_discovers_repeated_workflows_from_threads():
    activities = ActivityExtractor().extract(demo_messages())
    processes = ProcessMiner().mine(activities)
    discovered_names = {process.name for process in processes}
    
    assert len(processes) >= 5
    assert "DevOps Incident Response & Triage" in discovered_names
    assert "Support Escalation Resolution" in discovered_names
    assert "Employee Onboarding & IT Provisioning" in discovered_names
    assert "Invoice Exception & Variance Reconciliation" in discovered_names
    assert all(process.metrics.trace_count >= 2 for process in processes)
    assert all(process.edges for process in processes)


def test_process_graph_contains_evidence_step_nodes():
    processes = ProcessMiner().mine(ActivityExtractor().extract(demo_messages()))
    graph = BusinessProcessGraph()
    for p in processes:
        graph.add_process(p)
    visualization = graph.to_visualization()
    assert len(visualization["nodes"]) > 10
    assert len(visualization["edges"]) > 5
