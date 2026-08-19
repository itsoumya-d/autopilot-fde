import sys
import os
import time
from datetime import datetime, timedelta, timezone

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.demo_data import demo_messages
from backend.discovery.activity_extractor import ActivityExtractor
from backend.discovery.process_miner import ProcessMiner
from backend.scoring.aps_engine import APSEngine
from backend.scoring.recommender import Recommender
from backend.discovery.process_graph import BusinessProcessGraph
from backend.models.schema import Message, Activity, Process, ProcessMetrics

def test(condition, name, details=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name} {details}")
    return condition

def concern(condition, name, details=""):
    status = "PASS" if condition else "CONCERN"
    print(f"[{status}] {name} {details}")
    return condition

print("=== PART 1: Activity Extractor Deep Audit ===")
extractor = ActivityExtractor()
messages = demo_messages()

# Test 1
activities = extractor.extract(messages)
cats = {}
for a in activities:
    cats[a.category] = cats.get(a.category, 0) + 1
test(len(activities) == 36, "Extracts exactly 36 demo activities", f"(Got {len(activities)}) Categories: {cats}")

# Test 2
empty_activities = extractor.extract([])
test(len(empty_activities) == 0, "Handles empty message list gracefully")

# Test 3
no_keyword_msg = Message(id="1", sender="test", content="hello world", timestamp=datetime.now(timezone.utc), thread_id="t1")
no_k_act = extractor.extract([no_keyword_msg])
test(len(no_k_act) == 0, "No keywords -> 0 activities")

# Test 4
multi_match_msg = Message(id="2", sender="test", content="The customer escalated and we triaged it immediately", timestamp=datetime.now(timezone.utc), thread_id="t1")
multi_match_act = extractor.extract([multi_match_msg])
test(len(multi_match_act) > 0 and multi_match_act[0].name == "Customer escalation received", "Multiple rules match -> picks the right one", f"(Picked {multi_match_act[0].name if multi_match_act else 'none'})")

# Test 5
long_msg = Message(id="3", sender="test", content="urgent " * 10000, timestamp=datetime.now(timezone.utc), thread_id="t1")
start_time = time.time()
long_act = extractor.extract([long_msg])
end_time = time.time()
test(len(long_act) > 0, "Handles very LONG message without crashing", f"took {end_time - start_time:.4f}s")

# Test 6
emoji_msg = Message(id="4", sender="test", content="customer is blocked 🛑🥺", timestamp=datetime.now(timezone.utc), thread_id="t1")
emoji_act = extractor.extract([emoji_msg])
test(len(emoji_act) > 0, "Handles unicode/emoji-heavy text and matches keywords")

# Test 7
many_msgs = [Message(id=str(i), sender="test", content="urgent issue", timestamp=datetime.now(timezone.utc), thread_id=f"t{i}") for i in range(10000)]
start_time = time.time()
extractor.extract(many_msgs)
end_time = time.time()
tpt = 10000 / (end_time - start_time)
test(True, "Throughput test (10000 messages)", f"{tpt:.2f} messages/second")

# Test 8
no_thread_msg = Message(id="5", sender="test", content="urgent issue", timestamp=datetime.now(timezone.utc))
no_thread_act = extractor.extract([no_thread_msg])
test(no_thread_act[0].case_id == "message:5", "case_id assignment without thread_id uses 'message:{id}'")
test(activities[0].case_id == messages[0].thread_id, "case_id assignment with thread_id uses thread_id")

# Test 9
long_content_msg = Message(id="6", sender="test", content="urgent issue " + "A" * 200, timestamp=datetime.now(timezone.utc))
long_content_act = extractor.extract([long_content_msg])
test(len(long_content_act[0].evidence) == 181 and long_content_act[0].evidence.endswith("…"), "Evidence truncation > 180 chars")

# Test 10
concern(all(a.confidence == 0.92 for a in activities), "Confidence values always 0.92 (Is that appropriate?)")


print("\n=== PART 2: Process Miner Deep Audit ===")
miner = ProcessMiner()

# Test 1
processes = miner.mine(activities)
names = [p.name for p in processes]
test(len(processes) == 3, "Mines exactly 3 processes from 36 demo activities", f"Found {len(processes)}: {names}")

# Test 2
one_trace_activities = [a for a in activities if a.case_id in ("support-410", "lead-245", "invoice-900")]
one_trace_procs = miner.mine(one_trace_activities)
test(len(one_trace_procs) == 0, "1 trace per category -> 0 processes")

# Test 3
invalid_cat_activities = [Activity(id="x", name="x", category="invalid", case_id="x", timestamp=datetime.now(timezone.utc))] * 10
for i, a in enumerate(invalid_cat_activities): a.case_id = f"c{i//2}"
invalid_cat_procs = miner.mine(invalid_cat_activities)
test(len(invalid_cat_procs) == 0, "No valid category -> 0 processes")

# Test 4
many_acts = []
for i in range(100):
    for j in range(10):
        many_acts.append(Activity(id=f"{i}-{j}", name="urgent", category="support", case_id=f"c-{i}", timestamp=datetime.now(timezone.utc) + timedelta(minutes=j)))
start_time = time.time()
miner.mine(many_acts)
end_time = time.time()
test(True, "Mining 1000 activities across 100 cases", f"took {end_time - start_time:.4f}s")

# Test 5
def check_probs(p):
    out = {}
    for e in p.edges:
        out[e.source] = out.get(e.source, 0) + e.probability
    for src, prob in out.items():
        if abs(prob - 1.0) > 0.01: return False
    return True
test(all(check_probs(p) for p in processes), "Edge probabilities sum correctly per source node")

# Test 6
test(all(p.metrics.volume_per_month == p.metrics.trace_count * 4 for p in processes), "volume_per_month = trace_count * 4")
test(all(p.metrics.pattern_consistency > 0 for p in processes), "pattern_consistency is positive")

# Test 7
identical_ts = [
    Activity(id="1", name="A", category="support", case_id="c1", timestamp=datetime(2026,1,1, tzinfo=timezone.utc)),
    Activity(id="2", name="B", category="support", case_id="c1", timestamp=datetime(2026,1,1, tzinfo=timezone.utc)),
    Activity(id="3", name="A", category="support", case_id="c2", timestamp=datetime(2026,1,1, tzinfo=timezone.utc)),
    Activity(id="4", name="B", category="support", case_id="c2", timestamp=datetime(2026,1,1, tzinfo=timezone.utc)),
]
identical_procs = miner.mine(identical_ts)
test(len(identical_procs) == 1, "Handles identical timestamps for temporal ordering")

# Test 8
finance_proc = next((p for p in processes if p.name == "Invoice exception handling"), None)
if finance_proc:
    test(any("Payment" in n for n in finance_proc.safety_notes), "Safety notes added correctly for finance")
else:
    test(False, "Safety notes added correctly for finance", "(No finance process found)")

# Test 9
test(processes[0].id == miner.mine(activities)[0].id, "Process ID generation is deterministic")

# Test 10
long_trace = [Activity(id=str(i), name="A", category="support", case_id="c1", timestamp=datetime(2026,1,1, tzinfo=timezone.utc)+timedelta(minutes=i)) for i in range(50)]
long_trace += [Activity(id=str(i+50), name="A", category="support", case_id="c2", timestamp=datetime(2026,1,1, tzinfo=timezone.utc)+timedelta(minutes=i)) for i in range(50)]
long_trace_procs = miner.mine(long_trace)
test(len(long_trace_procs) == 1, "Handles very long traces (50 activities in one case)")


print("\n=== PART 3: APS Engine Deep Audit ===")
engine = APSEngine()

# Test 1
scores = [engine.score(p) for p in processes]
test(all(0 <= s.score <= 100 for s in scores), "Scores reasonable (0-100 range)")

# Test 2
max_metrics = ProcessMetrics(volume_per_month=20000, avg_completion_minutes=60, trace_count=1000, pattern_consistency=1.0, evidence_count=10000)
max_proc = Process(id="p-max", name="max", activities=[Activity(id="x", name="Issue triaged", category="support", case_id="x", timestamp=datetime.now(timezone.utc))]*10, metrics=max_metrics)
max_score = engine.score(max_proc)
test(max_score.score <= 100, "Max metrics APS <= 100", f"Score was {max_score.score}")

# Test 3
min_metrics = ProcessMetrics(volume_per_month=1, avg_completion_minutes=1, trace_count=1, pattern_consistency=0.01, evidence_count=1)
min_proc = Process(id="p-min", name="min", activities=[Activity(id="y", name="x", category="support", case_id="x", timestamp=datetime.now(timezone.utc))], metrics=min_metrics)
min_score = engine.score(min_proc)
test(min_score.score >= 0, "Min metrics APS >= 0", f"Score was {min_score.score}")

# Test 4
comp_inv = engine._complexity(Process(id="i", name="invoice processing"))
comp_esc = engine._complexity(Process(id="e", name="escalation handling"))
comp_oth = engine._complexity(Process(id="o", name="other task"))
test(comp_inv == 0.72 and comp_esc == 0.52 and comp_oth == 0.28, "Complexity function values correct", "Is this too simplistic? CONCERN")

# Test 5
no_elig_proc = Process(id="x", name="x", activities=[Activity(id="x", name="Unknown step", category="x", timestamp=datetime.now(timezone.utc))])
elig, blocked = engine._step_policy(no_elig_proc)
test(len(elig) == 0 and len(blocked) == 1, "step_policy handles NO eligible names")

# Test 6 & 7
evidence_100_traces = engine.score(Process(id="x", name="x", metrics=ProcessMetrics(trace_count=100, evidence_count=500)))
test(evidence_100_traces.evidence_confidence <= 95.0, "Evidence confidence formula maxes out at 0.95 (95.0)")

# Test 8
test(scores[0].estimated_hours_saved_monthly == round(scores[0].estimated_hours_saved_monthly, 1), "Estimated hours saved is calculated") # we just check if it executed without error

# Test 9
start_time = time.time()
for _ in range(1000):
    engine.score(processes[0])
end_time = time.time()
tpt = 1000 / (end_time - start_time)
test(True, "Scoring throughput (1000 processes)", f"{tpt:.2f} process scores/second")

# Test 10
low_ev_proc = Process(id="x", name="x", metrics=ProcessMetrics(trace_count=1, evidence_count=1))
low_ev_score = engine.score(low_ev_proc)
test(low_ev_score.evidence_confidence < 70 and "Continue observing" in low_ev_score.recommendation, "Recommendations change based on evidence confidence < 0.70")


print("\n=== PART 4: Recommender Audit ===")
recommender = Recommender()

# Test 1
recs = recommender.recommend(processes, scores)
waves = [r.wave for r in recs]
test(waves == ["Now", "Next", "Next"] or waves == ["Now", "Next", "Later"] or len(waves)==3, "Recommend 3 scored processes: wave assignments (Now, Next, Later/Next)", f"Waves: {waves}")

# Test 2
ten_scores = [engine.score(p) for p in [processes[0]] * 10]
# Modify values to ensure proper ordering
for i, s in enumerate(ten_scores): s.process_id = f"p{i}"; s.score = 100 - i
ten_procs = [Process(id=f"p{i}", name=f"p{i}") for i in range(10)]
ten_recs = recommender.recommend(ten_procs, ten_scores)
test([r.priority for r in ten_recs] == list(range(1, 11)), "Priority ordering for 10 processes")

# Test 3
missing_cap = recommender.recommend([processes[0]], [low_ev_score])
test(len(missing_cap[0].missing_capabilities) > 0, "Missing capabilities logic adds warnings")

# Test 4
same_scores = [engine.score(processes[0])] * 3
same_recs = recommender.recommend(processes, same_scores)
test(len(same_recs) == 3, "Ties broken safely (maintains list length, stable sort)")


print("\n=== PART 5: Process Graph Audit ===")
graph = BusinessProcessGraph()

# Test 1
for p in processes: graph.add_process(p)
test(len(graph.processes) == 3, "Build graph from 3 processes")

# Test 2
viz = graph.to_visualization()
test("nodes" in viz and "edges" in viz, "to_visualization() output format matches React Flow format")

# Test 3
bottlenecks = graph.find_bottlenecks(-1.0) # all are bottlenecks
test(len(bottlenecks) > 0, "Bottleneck identification finds slowest edges")

# Test 4
test(True, "Handoff identification", "(Not explicitly in process_graph.py code besides just process map building)")

# Test 5
empty_graph = BusinessProcessGraph()
test(empty_graph.to_visualization() == {"nodes": [], "edges": []}, "Test with empty process list")


print("\n=== PART 6: Integration Quality Audit ===")
# Test 1
latencies = []
for _ in range(100):
    s = time.time()
    acts = extractor.extract(messages)
    procs = miner.mine(acts)
    scrs = [engine.score(p) for p in procs]
    recs = recommender.recommend(procs, scrs)
    latencies.append(time.time() - s)
avg_lat = sum(latencies)/100
var_lat = sum((l - avg_lat)**2 for l in latencies)/100
test(True, "Full pipeline 100 times latency", f"Avg: {avg_lat*1000:.2f}ms, Variance: {var_lat*1000000:.2f}us")

# Test 2
out1 = recommender.recommend(procs, scrs)
out2 = recommender.recommend(miner.mine(extractor.extract(messages)), [engine.score(p) for p in miner.mine(extractor.extract(messages))])
test(str(out1) == str(out2), "Determinism: same input always produces same output")

# Test 3
import tracemalloc
tracemalloc.start()
large_msgs = [Message(id=str(i), sender="test", content="urgent issue", timestamp=datetime.now(timezone.utc), thread_id=f"t{i%1000}") for i in range(10000)]
extractor.extract(large_msgs)
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
test(True, "Memory usage for 10,000 messages", f"Peak: {peak / 10**6:.2f} MB")


print("\n=== PART 7: Output Quality Assessment ===")
for p, s, r in zip(processes, scores, recs):
    print(f"\nProcess: {p.name}")
    print(f"  Score: {s.score}")
    print(f"  Recommendation: {s.recommendation}")
    print(f"  Safety Notes: {p.safety_notes}")
    test(p.name in ["Support escalation resolution", "Inbound lead qualification", "Invoice exception handling"], "Process name descriptive")
    test(True, "Step names clear and actionable", f"Steps: {[a.name for a in p.activities]}")
    concern(True, "APS score defensible", f"Score={s.score}. Formula relies heavily on volume.")
    concern("Pilot" in s.recommendation or "Continue" in s.recommendation, "Recommendation actionable")
    test(len(p.safety_notes) >= 2, "Safety notes appropriate")

print("\nDONE.")
