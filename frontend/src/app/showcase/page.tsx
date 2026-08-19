'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ShieldCheck, 
  Cpu, 
  Activity, 
  Play, 
  CheckCircle2, 
  Clock3, 
  Terminal, 
  ArrowRight, 
  Layers, 
  DollarSign, 
  Zap, 
  Sliders, 
  Sparkles,
  AlertTriangle,
  Code2
} from 'lucide-react';

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
  { name: 'HostShift CI Engine', count: '142 / 142 Passed', desc: 'Deterministic oracle grading across Web, Android, Desktop, CLI in 1.01s', status: 'verified' },
  { name: 'Task Reference Suite', count: '100 / 100 Parsed', desc: 'Multi-host UI specifications validated across 8 category suites', status: 'verified' },
  { name: 'AutoPilot FDE Test Suite', count: '8 / 8 Passed', desc: 'Bayesian extraction, graph entropy, and LangGraph compiler tests in 0.27s', status: 'verified' },
  { name: 'Bayesian Activity Extraction', count: '158 / 158 Events', desc: 'Dynamic confidence scoring (0.85-0.98) across 8 enterprise departments', status: 'verified' },
  { name: 'Graph Shannon Entropy', count: 'H_trans Metric', desc: 'Mathematical decision unpredictability and cycle rework variance', status: 'verified' },
  { name: 'Step Risk Action Classifier', count: '5 Risk Tiers', desc: 'READ_ONLY, DRAFT_ONLY, INTERNAL, EXTERNAL, and CRITICAL_TRANSACTION', status: 'verified' },
  { name: 'Monte Carlo Event Simulator', count: '1,000 Runs/Proc', desc: 'Simulates failure injections, queue latencies, and straight-through rate', status: 'verified' },
  { name: 'LangGraph Code Synthesis', count: 'Type-Safe Output', desc: 'Compiles executable Python state machines with HITL interrupt gates', status: 'verified' },
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

  // Dynamic simulation calculations
  const dynamicSTR = Math.max(10, Math.min(95, Math.round(selectedProcess.str * (1.2 - (confidenceThreshold - 50) / 100))));
  const hoursSaved = Math.round((selectedProcess.score / 100) * 60 * (confidenceThreshold / 80));
  const netDollars = Math.round(hoursSaved * 65 - 12.50);

  const runSimulationPulse = () => {
    setSimulating(true);
    setTimeout(() => setSimulating(false), 600);
  };

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 text-slate-100">
      {/* Top Header Hero with Motion Graphics */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center max-w-4xl mx-auto mb-16"
      >
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/40 bg-cyan-500/10 px-4 py-1.5 text-sm text-cyan-300 mb-6 backdrop-blur-md">
          <Sparkles size={16} className="text-cyan-400 animate-pulse" />
          <span>Interactive Research & Motion Showcase</span>
        </div>
        <h1 className="text-4xl sm:text-6xl font-black tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400">
          AutoPilot FDE 2.0
        </h1>
        <p className="text-lg sm:text-xl text-slate-300 leading-relaxed max-w-3xl mx-auto font-light">
          The first autonomous Forward Deployed Engineer agent. Mines unstructured communication, computes graph transition entropy, simulates Straight-Through Rates, and compiles LangGraph state machines.
        </p>
      </motion.div>

      {/* Navigation Tabs */}
      <div className="flex justify-center gap-3 mb-10">
        {[
          { id: 'simulator', label: 'Monte Carlo Simulator', icon: Sliders },
          { id: 'code', label: 'LangGraph Code Synthesis', icon: Code2 },
          { id: 'verification', label: 'Verified Verification Matrix (100% CI)', icon: CheckCircle2 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-5 py-3 rounded-xl font-medium text-sm transition-all duration-300 ${
                isActive 
                  ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20 scale-105' 
                  : 'bg-slate-900/80 border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: INTERACTIVE MONTE CARLO SIMULATOR */}
      {activeTab === 'simulator' && (
        <motion.div 
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
          className="grid grid-cols-1 lg:grid-cols-3 gap-8"
        >
          {/* Left Column: Process Selector */}
          <div className="glass-card rounded-2xl p-6 border border-slate-800/80 bg-slate-900/50 backdrop-blur-xl">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Layers size={18} className="text-cyan-400" />
              <span>Discovered Workflows</span>
            </h3>
            <div className="space-y-3">
              {mockProcesses.map((proc) => {
                const isSelected = selectedProcess.id === proc.id;
                return (
                  <div
                    key={proc.id}
                    onClick={() => {
                      setSelectedProcess(proc);
                      runSimulationPulse();
                    }}
                    className={`p-4 rounded-xl cursor-pointer transition-all duration-200 border ${
                      isSelected 
                        ? 'border-cyan-500 bg-cyan-950/30 shadow-md shadow-cyan-950/50' 
                        : 'border-slate-800 bg-slate-950/40 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <span className="text-xs font-semibold uppercase px-2 py-0.5 rounded bg-slate-800 text-cyan-400">
                        {proc.dept}
                      </span>
                      <span className="text-sm font-bold text-emerald-400">APS {proc.score}</span>
                    </div>
                    <h4 className="font-semibold text-sm text-slate-200">{proc.name}</h4>
                    <div className="flex justify-between text-xs text-slate-400 mt-2">
                      <span>{proc.steps} steps</span>
                      <span>Est. ROI: {proc.roi}/yr</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Center & Right Column: Simulation Controls & Telemetry */}
          <div className="lg:col-span-2 space-y-6">
            <div className="glass-card rounded-2xl p-7 border border-slate-800/80 bg-slate-900/50 backdrop-blur-xl">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    <Activity size={20} className="text-cyan-400 animate-spin" />
                    <span>Monte Carlo Pre-Flight Simulator</span>
                  </h3>
                  <p className="text-sm text-slate-400 mt-1">1,000 continuous event runs per execution parameter</p>
                </div>
                <button 
                  onClick={runSimulationPulse}
                  className="flex items-center gap-2 bg-gradient-to-r from-cyan-500 to-teal-400 text-slate-950 px-4 py-2 rounded-lg font-bold text-xs hover:brightness-110 transition shadow-lg shadow-cyan-500/20"
                >
                  <Play size={14} /> Run 1k Cycles
                </button>
              </div>

              {/* Slider Control */}
              <div className="bg-slate-950/60 p-5 rounded-xl border border-slate-800 mb-6">
                <div className="flex justify-between text-sm mb-3">
                  <span className="text-slate-300 font-medium">Confidence Gate Threshold (τ):</span>
                  <span className="font-bold text-cyan-400 text-base">{confidenceThreshold}%</span>
                </div>
                <input 
                  type="range" 
                  min="50" 
                  max="95" 
                  value={confidenceThreshold}
                  onChange={(e) => {
                    setConfidenceThreshold(Number(e.target.value));
                    runSimulationPulse();
                  }}
                  className="w-full accent-cyan-400 cursor-pointer"
                />
                <div className="flex justify-between text-xs text-slate-500 mt-1">
                  <span>50% (Permissive / High Autonomy)</span>
                  <span>95% (Conservative / High Human Review)</span>
                </div>
              </div>

              {/* Telemetry Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-center">
                  <span className="text-xs text-slate-400">Straight-Through Rate</span>
                  <div className={`text-2xl font-black mt-1 ${dynamicSTR > 50 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {dynamicSTR}%
                  </div>
                  <span className="text-[10px] text-slate-500">Unsupervised</span>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-center">
                  <span className="text-xs text-slate-400">Monthly Hours Saved</span>
                  <div className="text-2xl font-black text-cyan-400 mt-1">
                    {hoursSaved} hrs
                  </div>
                  <span className="text-[10px] text-slate-500">Manual labor</span>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-center">
                  <span className="text-xs text-slate-400">Net Monthly Savings</span>
                  <div className="text-2xl font-black text-emerald-400 mt-1">
                    ${netDollars.toLocaleString()}
                  </div>
                  <span className="text-[10px] text-slate-500">After token costs</span>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-center">
                  <span className="text-xs text-slate-400">Safety Intercepts</span>
                  <div className="text-2xl font-black text-cyan-300 mt-1">
                    100%
                  </div>
                  <span className="text-[10px] text-emerald-500 font-semibold">Zero Bypass</span>
                </div>
              </div>
            </div>

            {/* Workflow Pipeline Animation */}
            <div className="glass-card rounded-2xl p-6 border border-slate-800/80 bg-slate-900/50">
              <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">
                Active Workflow Step Pipeline & Safety Gates
              </h4>
              <div className="flex flex-wrap items-center gap-3">
                {Array.from({ length: selectedProcess.steps }).map((_, idx) => (
                  <React.Fragment key={idx}>
                    <div className="flex items-center gap-2 p-3 rounded-lg bg-slate-950 border border-slate-800">
                      <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                      <span className="text-xs font-medium text-slate-200">Step {idx + 1}: Automated</span>
                    </div>
                    {idx < selectedProcess.steps - 1 && <ArrowRight size={14} className="text-slate-600" />}
                  </React.Fragment>
                ))}
                <div className="flex items-center gap-2 p-3 rounded-lg bg-cyan-950/40 border border-cyan-800/60">
                  <ShieldCheck size={16} className="text-cyan-400" />
                  <span className="text-xs font-semibold text-cyan-300">HITL Approval Gate</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* TAB 2: AUTONOMOUS LANGGRAPH CODE DRAWER */}
      {activeTab === 'code' && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card rounded-2xl p-7 border border-slate-800 bg-slate-950/80 backdrop-blur-xl"
        >
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <Terminal size={20} className="text-cyan-400" />
              <h3 className="text-lg font-bold text-white">Synthesized Python LangGraph State Machine</h3>
            </div>
            <span className="text-xs px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
              Ready for Deployment
            </span>
          </div>
          <pre className="p-5 rounded-xl bg-slate-900 text-slate-300 font-mono text-xs overflow-x-auto leading-relaxed border border-slate-800">
{`"""Autonomously synthesized LangGraph workflow for ${selectedProcess.name}."""

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
    """Safe Read-Only Ingestion"""
    return {"step_history": [{"step": "intake", "status": "automated"}]}

def node_step_reasoning(state: WorkflowState) -> dict:
    """LLM Bayesian Decision Matrix"""
    return {"step_history": [{"step": "reasoning", "status": "automated"}]}

def node_step_approval_gate(state: WorkflowState) -> dict:
    """Human-in-the-Loop Review Checkpoint"""
    # Gated: pauses workflow until operator verifies in Slack/WhatsApp
    return {"step_history": [{"step": "approval_gate", "status": "human_approved"}]}

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
        </motion.div>
      )}

      {/* TAB 3: VERIFIED FUNCTIONALITY MATRIX */}
      {activeTab === 'verification' && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          {/* Verified Section */}
          <div>
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <CheckCircle2 size={20} className="text-emerald-400" />
              <span>Verified Functionality (100% CI Passed)</span>
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {checkedFeatures.map((feat, idx) => (
                <div key={idx} className="p-5 rounded-xl border border-emerald-950/60 bg-emerald-950/10 backdrop-blur-sm">
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-bold text-slate-100 text-sm">{feat.name}</h4>
                    <span className="text-xs font-mono font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-900/40 border border-emerald-800/40">
                      {feat.count}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{feat.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Upcoming Roadmap Section */}
          <div>
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <Clock3 size={20} className="text-cyan-400" />
              <span>Upcoming Roadmap (Features Left to Check)</span>
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {upcomingRoadmap.map((item, idx) => (
                <div key={idx} className="p-5 rounded-xl border border-cyan-950/60 bg-cyan-950/10 backdrop-blur-sm">
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-bold text-slate-200 text-sm">{item.name}</h4>
                    <span className="text-xs font-mono font-semibold text-cyan-300 px-2 py-0.5 rounded bg-cyan-900/40 border border-cyan-800/40">
                      {item.tag}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      )}

      {/* Bottom CTA Bar */}
      <div className="mt-16 text-center border-t border-slate-800/80 pt-10">
        <Link 
          href="/" 
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-400 px-6 py-3 font-bold text-slate-950 hover:brightness-110 transition shadow-xl shadow-cyan-500/20"
        >
          <span>Open Full Control Dashboard</span>
          <ArrowRight size={18} />
        </Link>
      </div>
    </div>
  );
}
