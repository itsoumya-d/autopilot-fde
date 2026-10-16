'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Play } from 'lucide-react';
import { PageHeader, SectionHeader, SourceLabel, StatusBadge } from '@/components/Workspace';

const mockProcesses = [
  { id: 'p1', name: 'Enterprise Deal Desk', dept: 'Sales', steps: 4, score: 74.4, roi: '$36,499', str: 68.4, safety: 'Assisted' },
  { id: 'p2', name: 'Support Escalation Resolution', dept: 'Support', steps: 5, score: 69.0, roi: '$31,587', str: 62.1, safety: 'Assisted' },
  { id: 'p3', name: 'Employee Onboarding & IT', dept: 'HR', steps: 4, score: 65.1, roi: '$44,926', str: 56.2, safety: 'Assisted' },
  { id: 'p4', name: 'Legal Contract NDA Review', dept: 'Legal', steps: 4, score: 63.2, roi: '$56,158', str: 51.5, safety: 'Assisted' },
  { id: 'p5', name: 'Customer Success Renewal', dept: 'CS', steps: 4, score: 63.2, roi: '$29,482', str: 42.0, safety: 'Assisted' },
  { id: 'p6', name: 'Invoice Exception & Variance', dept: 'Finance', steps: 4, score: 59.1, roi: '$19,341', str: 28.4, safety: 'Draft-Only' },
  { id: 'p7', name: 'DevOps Incident Triage', dept: 'DevOps', steps: 5, score: 58.3, roi: '$14,037', str: 34.0, safety: 'Draft-Only' },
];

const checkedFeatures = [
  { name: 'HostShift CI Engine', count: '142 / 142 Passed', desc: 'Deterministic oracle grading across Web, Android, Desktop, CLI in 1.01s' },
  { name: 'Task Reference Suite', count: '100 / 100 Parsed', desc: 'Multi-host UI specifications validated across 8 category suites' },
  { name: 'AutoPilot FDE Test Suite', count: '8 / 8 Passed', desc: 'Bayesian extraction, graph entropy, and LangGraph compiler tests in 0.27s' },
  { name: 'Bayesian Activity Extraction', count: '158 / 158 Events', desc: 'Dynamic confidence scoring (0.85-0.98) across 8 enterprise departments' },
  { name: 'Graph Shannon Entropy', count: 'H_trans Metric', desc: 'Mathematical decision unpredictability and cycle rework variance' },
  { name: 'Step Risk Action Classifier', count: '5 Risk Tiers', desc: 'READ_ONLY, DRAFT_ONLY, INTERNAL, EXTERNAL, and CRITICAL_TRANSACTION' },
  { name: 'Monte Carlo Event Simulator', count: '1,000 Runs/Proc', desc: 'Simulates failure injections, queue latencies, and straight-through rate' },
  { name: 'LangGraph Code Synthesis', count: 'Type-Safe Output', desc: 'Compiles executable Python state machines with HITL interrupt gates' },
];

const upcomingRoadmap = [
  { name: 'Multi-Modal Voice & Video Stream Mining', desc: 'Ingestion of recorded Zoom/Teams meeting recordings via Whisper & Vision LLMs', tag: 'Q4 2026' },
  { name: 'Decentralized Multi-Tenant Cloud Mesh', desc: 'Encrypted peer-to-peer agent coordination across isolated enterprise VPCs', tag: 'Q1 2027' },
  { name: 'Live Slack Interactive Blocks Gateway', desc: 'Socket-mode two-way approval buttons directly embedded inside Slack threads', tag: 'Q1 2027' },
];


export default function ShowcasePage() {
  const [selectedProcess, setSelectedProcess] = useState(mockProcesses[0]);
  const [confidenceThreshold, setConfidenceThreshold] = useState(80);
  const [simulating, setSimulating] = useState(false);
  const [activeTab, setActiveTab] = useState<'simulator' | 'code' | 'verification'>('simulator');
  const simulationTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (simulationTimeout.current !== null) clearTimeout(simulationTimeout.current);
  }, []);

  // Local illustrative formulas, independent of the backend simulator.
  const dynamicSTR = Math.max(10, Math.min(95, Math.round(selectedProcess.str * (1.2 - (confidenceThreshold - 50) / 100))));
  const hoursSaved = Math.round((selectedProcess.score / 100) * 60 * (confidenceThreshold / 80));
  const netDollars = Math.round(hoursSaved * 65 - 12.50);

  const runSimulationPulse = () => {
    if (simulationTimeout.current !== null) clearTimeout(simulationTimeout.current);
    setSimulating(true);
    simulationTimeout.current = setTimeout(() => {
      setSimulating(false);
      simulationTimeout.current = null;
    }, 600);
  };

  return (
    <div className="page-stack">
      <PageHeader title="Simulation" description="Explore how a confidence threshold changes a local example. No workflow is executed." />
      <div className="flex flex-col gap-2 border-y border-[var(--border)] py-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="muted text-sm">Demo showcase: the numbers and code samples below are illustrative fixtures, not live backend results.</p>
        <SourceLabel>Local sandbox</SourceLabel>
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Simulation views">
        {([
          { id: 'simulator', label: 'Simulation inputs' },
          { id: 'code', label: 'Example code' },
          { id: 'verification', label: 'Historical matrix' },
        ] as const).map(tab => <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} aria-pressed={activeTab === tab.id} className={activeTab === tab.id ? 'button-primary' : 'button-secondary'}>{tab.label}</button>)}
      </div>

      {activeTab === 'simulator' && <div className="grid items-start gap-6 xl:grid-cols-[minmax(250px,0.85fr)_minmax(0,1.65fr)]">
        <section className="surface overflow-hidden" aria-labelledby="sample-workflows-heading">
          <div className="p-5"><h2 id="sample-workflows-heading">Sample workflows</h2><p className="metadata mt-1">Seven static scenarios. Select one to explore.</p></div>
          <div className="border-t border-[var(--border)]">
            {mockProcesses.map(proc => <button type="button" key={proc.id} onClick={() => { setSelectedProcess(proc); runSimulationPulse(); }} aria-pressed={selectedProcess.id === proc.id} className={`block w-full border-b border-[var(--border)] p-4 text-left last:border-b-0 ${selectedProcess.id === proc.id ? 'border-l-2 border-l-[var(--accent)] bg-[var(--accent-soft)]' : 'hover:bg-[var(--surface-subtle)]'}`}>
              <span className="mb-2 flex justify-between gap-2 text-xs text-[var(--text-muted)]"><span>{proc.dept}</span><span className="mono">APS {proc.score}</span></span>
              <span className="block text-sm font-semibold">{proc.name}</span>
              <span className="mt-2 block text-xs text-[var(--text-muted)]">{proc.steps} steps · Example ROI {proc.roi}/yr</span>
            </button>)}
          </div>
        </section>
        <div className="min-w-0 space-y-6">
          <section className="surface surface-pad">
            <SectionHeader title={selectedProcess.name} description={`${selectedProcess.dept} / ${selectedProcess.steps} example steps`} actions={<StatusBadge>{selectedProcess.safety} example</StatusBadge>} />
            <div className="border-y border-[var(--border)] py-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><label htmlFor="confidence-threshold" className="font-medium">Confidence Gate Threshold (τ)</label><output htmlFor="confidence-threshold" className="mono">{confidenceThreshold}%</output></div>
              <input id="confidence-threshold" type="range" min="50" max="95" value={confidenceThreshold} onChange={(e) => { setConfidenceThreshold(Number(e.target.value)); runSimulationPulse(); }} className="w-full accent-[var(--accent)]" />
              <div className="metadata mt-2 flex justify-between gap-4"><span>50% / Permissive</span><span className="text-right">95% / Conservative</span></div>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-4"><button type="button" onClick={runSimulationPulse} disabled={simulating} className="button-primary"><Play size={14} aria-hidden="true" />Run illustrative simulation</button><p role="status" aria-label="Simulation feedback" className="metadata">{simulating ? 'Local example updated.' : 'Ready to explore.'}</p></div>
            <p className="metadata mt-3">Values update using local formulas. The 600 ms feedback interval does not run 1,000 backend trials or validate a safety policy.</p>
          </section>
          <section className="surface surface-pad" aria-labelledby="example-results-heading">
            <SectionHeader title="Illustrative result" actions={<SourceLabel>Computed from static inputs</SourceLabel>} />
            <h3 id="example-results-heading" className="sr-only">Example result values</h3>
            <dl className="grid grid-cols-1 gap-5 min-[480px]:grid-cols-2">
              <Result label="Straight-through rate" value={`${dynamicSTR}%`} note="Illustrative unsupervised share" />
              <Result label="Monthly hours saved" value={`${hoursSaved} hrs`} note="Local estimate, not measured labor" />
              <Result label="Net monthly savings" value={`$${netDollars.toLocaleString()}`} note="Hours × $65, less $12.50" />
              <Result label="Safety intercepts" value="100%" note="Fixed example value, not a verified outcome" />
            </dl>
          </section>
          <section className="border-t border-[var(--border)] pt-5">
            <h2 className="mb-3">Example step layout</h2>
            <p className="muted mb-4 text-sm">Step counts come from the selected fixture. These labels are placeholders, not discovered activities or a running pipeline.</p>
            <ol className="flex flex-wrap gap-2">{Array.from({ length: selectedProcess.steps }).map((_, idx) => <li key={idx} className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs">Step {idx + 1} / Example</li>)}<li className="rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-2 text-xs">Human review / Example gate</li></ol>
            <details className="mt-5 text-sm"><summary className="cursor-pointer font-medium">Calculation assumptions</summary><ul className="muted mt-3 space-y-2"><li>Straight-through rate uses the scenario baseline and selected threshold, rounded and clamped between 10% and 95%.</li><li>Hours = opportunity score ÷ 100 × 60 × threshold ÷ 80.</li><li>Savings = rounded hours × $65 − $12.50. Quality, deployment cost, and real safety outcomes are not evaluated.</li></ul></details>
          </section>
        </div>
      </div>}

      {activeTab === 'code' && <section className="surface surface-pad">
        <SectionHeader title="Example Python LangGraph state machine" description={`Static teaching example for ${selectedProcess.name}. This is not generated output or a deployable review policy.`} actions={<SourceLabel>Example code</SourceLabel>} />
        <p className="muted mb-5 text-sm">The approval node is a placeholder. It does not pause execution, verify a reviewer, or connect to Slack or WhatsApp.</p>
        <pre tabIndex={0} aria-label="Illustrative Python code" className="mono overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--surface-subtle)] p-4 text-xs leading-relaxed">
{`"""Illustrative LangGraph skeleton for ${selectedProcess.name}."""

from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
import operator

class WorkflowState(TypedDict):
    case_id: str
    payload: Dict[str, Any]
    current_step: str
    step_history: Annotated[List[Dict[str, Any]], operator.add]
    is_escalated: bool

def node_step_intake(state: WorkflowState) -> dict:
    """Example intake placeholder"""
    return {"step_history": [{"step": "intake", "status": "automated"}]}

def node_step_reasoning(state: WorkflowState) -> dict:
    """Example reasoning placeholder"""
    return {"step_history": [{"step": "reasoning", "status": "automated"}]}

def node_step_approval_gate(state: WorkflowState) -> dict:
    """Human-in-the-Loop Review Checkpoint"""
    # Placeholder only: this example does not implement an approval interrupt.
    return {"step_history": [{"step": "approval_gate", "status": "requires_review"}]}

def build_agent_graph() -> StateGraph:
    workflow = StateGraph(WorkflowState)
    workflow.add_node("node_intake", node_step_intake)
    workflow.add_node("node_reasoning", node_step_reasoning)
    workflow.add_node("node_approval_gate", node_step_approval_gate)
    
    workflow.set_entry_point("node_intake")
    workflow.add_edge("node_intake", "node_reasoning")
    workflow.add_edge("node_reasoning", "node_approval_gate")
    workflow.add_edge("node_approval_gate", END)
    
    return workflow.compile()

app = build_agent_graph()`}
        </pre>
      </section>}

      {activeTab === 'verification' && <div className="space-y-6">
        <section className="surface overflow-hidden">
          <div className="surface-pad"><SectionHeader title="Historical verification examples" description="Static claims retained from the original showcase. No current run, source artifact, or CI result is connected here." actions={<SourceLabel>Historical / unverified here</SourceLabel>} /></div>
          <div className="divide-y divide-[var(--border)]">{checkedFeatures.map(feat => <div key={feat.name} className="grid gap-3 px-5 py-4 md:grid-cols-[minmax(0,1fr)_auto]"><div><h3>{feat.name}</h3><p className="muted mt-1 text-sm">{feat.desc}</p></div><span className="mono text-xs">{feat.count}</span></div>)}</div>
        </section>
        <section className="surface surface-pad"><SectionHeader title="Original roadmap examples" description="Static showcase planning notes. Dates are unverified targets, not delivery commitments." /><ul className="divide-y divide-[var(--border)]">{upcomingRoadmap.map(item => <li key={item.name} className="py-4 first:pt-0"><div className="flex flex-wrap justify-between gap-3"><h3>{item.name}</h3><span className="mono metadata">{item.tag} / example target</span></div><p className="muted mt-2 text-sm">{item.desc}</p></li>)}</ul></section>
      </div>}
      <div className="border-t border-[var(--border)] pt-5"><Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-[var(--accent)]">Back to workspace overview<ArrowRight size={15} aria-hidden="true" /></Link></div>
    </div>
  );
}

function Result({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="border-t border-[var(--border)] pt-4"><dt className="muted text-sm">{label}</dt><dd className="mt-2 text-3xl font-semibold tabular-nums">{value}</dd><p className="metadata mt-2">{note}</p></div>;
}
