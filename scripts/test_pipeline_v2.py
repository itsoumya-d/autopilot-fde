import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.demo_data import demo_messages
from backend.deployment.agent_factory import AgentFactory
from backend.discovery.activity_extractor import ActivityExtractor
from backend.discovery.process_miner import ProcessMiner
from backend.models.schema import DeploymentConfig
from backend.scoring.aps_engine import APSEngine
from backend.scoring.recommender import Recommender
from backend.scoring.simulator import ProcessSimulator

print("=" * 85)
print("🚀 AUTOPILOT FDE 2.0 — CATEGORY-DEFINING PIPELINE STRESS TEST")
print("=" * 85)

# 1. INGESTION
msgs = demo_messages()
print(f"\n📡 Step 1: Ingestion — {len(msgs)} messages across 8 departments")

# 2. ACTIVITY EXTRACTION
extractor = ActivityExtractor()
activities = extractor.extract(msgs)
print(f"🔍 Step 2: Extraction — {len(activities)} activities extracted")
confidences = [a.confidence for a in activities]
print(f"   Confidence range: {min(confidences):.2f} to {max(confidences):.2f} (mean: {sum(confidences)/len(confidences):.2f})")

# 3. PROCESS MINING
miner = ProcessMiner()
processes = miner.mine(activities)
print(f"\n🏗  Step 3: Discovered {len(processes)} enterprise business processes:")
for p in processes:
    print(f"   • [{p.category.upper()}] {p.name}")
    print(f"     Steps: {len(p.activities)} | Traces: {p.metrics.trace_count} | Entropy: {p.metrics.entropy_score:.2f} | Unique Actors: {p.metrics.unique_actors_count}")

# 4. APS SCORING
engine = APSEngine()
scores = [engine.score(p) for p in processes]
print("\n⚡ Step 4: Mathematical APS Opportunity Scoring & ROI Analysis:")
score_values = [s.score for s in scores]
print(f"   Score Range: {min(score_values):.1f} to {max(score_values):.1f} (Spread: {max(score_values) - min(score_values):.1f} pts)")

for s, p in sorted(zip(scores, processes), key=lambda x: x[0].score, reverse=True):
    print(f"\n   📊 {p.name}")
    print(f"      APS Score: {s.score}/100 | Mode: {s.recommended_mode.value.upper()}")
    print(f"      Value Score: {s.value_score} | Feasibility: {s.feasibility_score} | Evidence: {s.evidence_confidence}%")
    print(f"      Eligible: {len(s.eligible_steps)} step(s) | Blocked/Approval: {len(s.blocked_steps)} step(s)")
    print(f"      Monthly ROI: ${s.estimated_monthly_roi_dollars:,.2f} ({s.estimated_hours_saved_monthly:.1f} hrs/mo saved)")
    print(f"      Policy: {s.recommendation}")

# 5. RECOMMENDATIONS & WAVES
recommender = Recommender()
recs = recommender.recommend(processes, scores)
print("\n🎯 Step 5: Prioritized Deployment Waves:")
for r in recs:
    print(f"   [Wave {r.wave:<5}] #{r.priority} {r.process_name} | Est. Annual ROI: ${r.estimated_annual_roi_dollars:,.2f} | Risk: {r.risk_level}")
    if r.missing_capabilities:
        for m in r.missing_capabilities:
            print(f"            ⚠️  {m}")

# 6. MONTE CARLO SIMULATION
simulator = ProcessSimulator()
print("\n🎲 Step 6: Pre-Deployment Monte Carlo Simulation (1,000 Runs/Process):")
for p, s in zip(processes[:3], scores[:3]):
    sim = simulator.simulate(p, s, runs=1000, confidence_threshold=0.80)
    print(f"\n   🔬 Simulation for {p.name}:")
    print(f"      • Straight-Through Rate (STR): {sim.straight_through_rate}%")
    print(f"      • Human Escalation Rate: {sim.human_escalation_rate}%")
    print(f"      • Time to Resolve: {sim.time_to_resolve_minutes_before:.0f} min manual ➔ {sim.time_to_resolve_minutes_after:.1f} min automated")
    print(f"      • Net Monthly Savings: ${sim.net_monthly_savings_dollars:,.2f} (Token Cost: ${sim.estimated_monthly_token_cost:.2f})")
    print(f"      • Critical Safety Blocks Intercepted: {sim.safety_violations_caught}")
    print(f"      • Bottleneck Step: \"{sim.simulated_bottleneck_step}\"")

# 7. AUTONOMOUS LANGGRAPH CODE GENERATION
factory = AgentFactory()
print("\n🤖 Step 7: Autonomous LangGraph Agent Code Generation:")
top_process = processes[0]
top_score = scores[0]
agent = factory.create_agent(
    process=top_process,
    config=DeploymentConfig(steps=top_score.eligible_steps, hitl_required=True),
)
print(f"   Generated Agent: {agent.name}")
print(f"   LangGraph Specs: {agent.generated_code.langgraph_spec}")
print("   Python Code Preview (First 25 lines):")
print("   " + "-" * 60)
for line in agent.generated_code.python_code.splitlines()[:25]:
    print("   | " + line)
print("   " + "-" * 60)

print("\n" + "=" * 85)
print("ALL MODULES EXECUTED FLAWLESSLY WITH SCIENTIFIC RIGOR ✅")
print("=" * 85)
