'use client';

import React, { useState } from 'react';
import { Shield, GitBranch, FileText, Database, Radio, CheckCircle, AlertTriangle, ArrowRight, RotateCcw, Lock } from 'lucide-react';

export default function ArchetypesPage() {
  const [activeTab, setActiveTab] = useState<'project1' | 'project2' | 'project3' | 'project4' | 'project5'>('project1');

  // Project 1 State
  const [p1Role, setP1Role] = useState<'engineering' | 'hr' | 'finance' | 'guest'>('engineering');
  const [p1Query, setP1Query] = useState('Kubernetes architecture microservices');
  const [p1Result, setP1Result] = useState<any>(null);

  // Project 2 State
  const [p2Content, setP2Content] = useState('Urgent: need refund of $450 on corporate billing');
  const [p2Ticket, setP2Ticket] = useState<any>(null);
  const [p2Approved, setP2Approved] = useState(false);

  // Project 3 State
  const [p3Discrepancy, setP3Discrepancy] = useState(false);
  const [p3Report, setP3Report] = useState<any>(null);

  // Project 4 State
  const [p4Data, setP4Data] = useState<any>(null);

  // Project 5 State
  const [p5Incident, setP5Incident] = useState<any>(null);
  const [p5RollbackDone, setP5RollbackDone] = useState(false);

  // Handlers
  const handleP1Run = async () => {
    try {
      const res = await fetch('/api/archetypes/project1/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: p1Query, user_role: p1Role }),
      });
      const data = await res.json();
      setP1Result(data);
    } catch {
      // Fallback simulation for client preview
      const isAllowed = p1Role !== 'finance' && p1Role !== 'guest' || !p1Query.toLowerCase().includes('executive');
      setP1Result({
        allowed: isAllowed,
        answer: isAllowed
          ? `Based on Engineering Architecture: Core services run on Kubernetes clusters in us-east-1.`
          : `Access denied: Matching document 'Q3 Executive Compensation' requires elevated HR/Admin permissions.`,
        grounding_score: isAllowed ? 0.98 : 0.0,
        blocked_count: isAllowed ? 0 : 1,
        citations: isAllowed ? [{ doc_id: 'DOC-002', title: 'Engineering Architecture', department: 'Engineering', confidentiality: 'internal' }] : [],
      });
    }
  };

  const handleP2Submit = async () => {
    try {
      const res = await fetch('/api/archetypes/project2/ticket', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer: 'Acme Corp', content: p2Content }),
      });
      const data = await res.json();
      setP2Ticket(data);
      setP2Approved(false);
    } catch {
      const requiresApproval = p2Content.toLowerCase().includes('refund');
      setP2Ticket({
        id: 'TICK-9081',
        customer: 'Acme Corp',
        priority: 'high',
        status: requiresApproval ? 'pending_approval' : 'resolving',
        requires_approval: requiresApproval,
        approval_token: requiresApproval ? 'APP-77B901C2' : null,
        suggested_action: 'Escalate to billing manager for refund review.',
      });
      setP2Approved(false);
    }
  };

  const handleP2Approve = () => {
    setP2Approved(true);
    if (p2Ticket) {
      setP2Ticket({ ...p2Ticket, status: 'resolved', requires_approval: false });
    }
  };

  const handleP3Validate = async () => {
    try {
      const res = await fetch('/api/archetypes/project3/validate-invoice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulate_discrepancy: p3Discrepancy }),
      });
      const data = await res.json();
      setP3Report(data);
    } catch {
      setP3Report({
        invoice_id: 'INV-2026-8891',
        is_valid: !p3Discrepancy,
        arithmetic_valid: !p3Discrepancy,
        discrepancy_details: p3Discrepancy
          ? ['Line items + tax ($3456.00) != total ($3466.00). Delta: $10.00']
          : [],
        action_recommended: p3Discrepancy
          ? 'MANUAL_AUDIT_REQUIRED: Mathematical discrepancies detected.'
          : 'AUTO_APPROVE: All arithmetic and business constraints verified.',
      });
    }
  };

  const handleP4Run = async () => {
    try {
      const res = await fetch('/api/archetypes/project4/onboard-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: 'client_messy_export.csv' }),
      });
      const data = await res.json();
      setP4Data(data);
    } catch {
      setP4Data({
        report: {
          total_rows: 5,
          accepted_rows: 3,
          quarantined_rows: 2,
          schema_match_pct: 100.0,
          mapped_headers: { Client_ID: 'customer_id', 'Full Name': 'full_name', 'Email Address': 'email', ARR: 'annual_spend' },
        },
      });
    }
  };

  const handleP5Trigger = async () => {
    try {
      const res = await fetch('/api/archetypes/project5/correlate-and-remediate?simulate_incident=true', { method: 'POST' });
      const data = await res.json();
      setP5Incident(data.incident);
      setP5RollbackDone(false);
    } catch {
      setP5Incident({
        incident_id: 'INC-77102',
        title: 'Cascading API Latency from Database Pool Exhaustion',
        severity: 'critical',
        probable_root_cause: 'PostgreSQL connection pool saturated during batch load.',
        remediation_action: 'Automated read replica pool expansion (dry-run passed).',
        state: 'remediated',
        rollback_token: 'RBK-9902A1',
      });
      setP5RollbackDone(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
          <span className="p-2 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-xl text-white shadow-lg shadow-cyan-500/20">
            5
          </span>
          Production-Grade Enterprise Archetypes
        </h1>
        <p className="text-slate-400 mt-2 text-sm max-w-3xl">
          Derived from Aishwarya Srinivasan&apos;s 2026 masterclass. AutoPilot FDE automatically discovers, classifies, generates, and deploys these 5 battle-tested enterprise architectures.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-4">
        {[
          { id: 'project1', label: '1. Knowledge RAG', icon: Shield },
          { id: 'project2', label: '2. Intake-to-Resolution', icon: GitBranch },
          { id: 'project3', label: '3. Document Intelligence', icon: FileText },
          { id: 'project4', label: '4. Data Onboarding', icon: Database },
          { id: 'project5', label: '5. Ops Command Center', icon: Radio },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active
                  ? 'bg-cyan-500 text-slate-950 font-semibold shadow-lg shadow-cyan-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content Area */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-xl">
        {/* PROJECT 1 */}
        {activeTab === 'project1' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Shield className="text-cyan-400" size={20} />
                Project 1: Permission-Aware Enterprise Knowledge System
              </h2>
              <p className="text-slate-400 text-sm mt-1">
                Enforces strict RBAC/ABAC clearance before vector retrieval. Eliminates internal HR/Finance data leaks and verifies grounded answers with citation lineage.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-3">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Your Simulated Role</label>
                <div className="grid grid-cols-4 gap-2">
                  {(['engineering', 'hr', 'finance', 'guest'] as const).map((r) => (
                    <button
                      key={r}
                      onClick={() => setP1Role(r)}
                      className={`px-3 py-2 rounded-lg text-xs font-medium capitalize border transition-all ${
                        p1Role === r ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300' : 'border-slate-800 text-slate-400 hover:bg-slate-800'
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>

                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block pt-2">Knowledge Query</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={p1Query}
                    onChange={(e) => setP1Query(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500"
                  />
                  <button onClick={handleP1Run} className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold rounded-lg text-sm">
                    Search
                  </button>
                </div>
                <div className="text-xs text-slate-500 flex gap-2">
                  <span>Quick Test:</span>
                  <button onClick={() => setP1Query('Executive compensation bonus')} className="underline hover:text-cyan-400">
                    Exec Compensation
                  </button>
                  <span>•</span>
                  <button onClick={() => setP1Query('Kubernetes architecture')} className="underline hover:text-cyan-400">
                    Infra Docs
                  </button>
                </div>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Retrieval & Grounding Output</h3>
                {p1Result ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${p1Result.allowed ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}`}>
                        {p1Result.allowed ? 'ACCESS GRANTED' : 'BLOCKED BY ACL GATE'}
                      </span>
                      <span className="text-xs text-slate-500">Grounding Score: {(p1Result.grounding_score * 100).toFixed(0)}%</span>
                    </div>
                    <p className="text-sm text-slate-200">{p1Result.answer}</p>
                    {p1Result.citations && p1Result.citations.length > 0 && (
                      <div className="border-t border-slate-800/80 pt-2 text-xs text-slate-400">
                        <span className="font-semibold text-slate-300">Verified Citation:</span> {p1Result.citations[0].title} ({p1Result.citations[0].department})
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 italic">Click Search to execute permission-aware retrieval.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* PROJECT 2 */}
        {activeTab === 'project2' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <GitBranch className="text-cyan-400" size={20} />
                Project 2: Intake-to-Resolution Orchestration Workflow
              </h2>
              <p className="text-slate-400 text-sm mt-1">
                Stateful LangGraph execution engine. Low-risk queries auto-resolve straight through; high-risk transactions pause in an interrupt gate for cryptographic human approval.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-3">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Incoming Ticket Payload</label>
                <textarea
                  value={p2Content}
                  onChange={(e) => setP2Content(e.target.value)}
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-cyan-500"
                />
                <button onClick={handleP2Submit} className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold rounded-lg text-sm">
                  Ingest Ticket
                </button>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">LangGraph State Machine</h3>
                {p2Ticket ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-400">Ticket: <strong className="text-white">{p2Ticket.id}</strong></span>
                      <span className="px-2 py-0.5 rounded uppercase font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        {p2Ticket.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300"><strong>Action:</strong> {p2Ticket.suggested_action}</p>
                    {p2Ticket.requires_approval && !p2Approved && (
                      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 space-y-2">
                        <div className="flex items-center gap-1.5 text-xs text-amber-300 font-semibold">
                          <AlertTriangle size={14} />
                          Human-in-the-Loop Approval Required
                        </div>
                        <button onClick={handleP2Approve} className="w-full py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded text-xs">
                          Approve Execution with Token ({p2Ticket.approval_token})
                        </button>
                      </div>
                    )}
                    {p2Approved && (
                      <div className="text-xs text-emerald-400 font-semibold flex items-center gap-1.5">
                        <CheckCircle size={14} /> State machine resumed: Action executed successfully!
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 italic">Ingest a ticket to observe state machine execution.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* PROJECT 3 */}
        {activeTab === 'project3' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <FileText className="text-cyan-400" size={20} />
                Project 3: Dual-Stage Document Intelligence & Approval
              </h2>
              <p className="text-slate-400 text-sm mt-1">
                Decoupled architecture: Stage 1 extracts candidate JSON via LLM; Stage 2 deterministically audits line-item multiplication, tax math, and reconciles totals.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="discrepancyToggle"
                    checked={p3Discrepancy}
                    onChange={(e) => setP3Discrepancy(e.target.checked)}
                    className="accent-cyan-500 rounded"
                  />
                  <label htmlFor="discrepancyToggle" className="text-sm text-slate-300">
                    Inject Simulated $10 Arithmetic Discrepancy
                  </label>
                </div>
                <button onClick={handleP3Validate} className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold rounded-lg text-sm">
                  Run Deterministic Audit
                </button>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Stage 2 Validation Report</h3>
                {p3Report ? (
                  <div className="space-y-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${p3Report.is_valid ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                      {p3Report.is_valid ? '100% MATHEMATICALLY VERIFIED' : 'ARITHMETIC ERROR CAUGHT'}
                    </span>
                    <p className="text-xs text-slate-300 mt-2">{p3Report.action_recommended}</p>
                    {p3Report.discrepancy_details && p3Report.discrepancy_details.length > 0 && (
                      <ul className="text-xs text-rose-400 list-disc pl-4 space-y-1">
                        {p3Report.discrepancy_details.map((d: string, i: number) => (
                          <li key={i}>{d}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600 italic">Click Run Deterministic Audit to verify extraction math.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* PROJECT 4 */}
        {activeTab === 'project4' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Database className="text-cyan-400" size={20} />
                Project 4: Customer Data Onboarding Pipeline
              </h2>
              <p className="text-slate-400 text-sm mt-1">
                Fuzzy schema reconciliation maps messy customer headers (e.g. &apos;Client_ID&apos;, &apos;ARR&apos;) to canonical schemas while routing corrupt rows to a Quarantine DLQ.
              </p>
            </div>

            <div className="space-y-4">
              <button onClick={handleP4Run} className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold rounded-lg text-sm">
                Process Sample Dirty CSV Batch
              </button>

              {p4Data && (
                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
                  <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    <div className="p-2 bg-slate-900 rounded">Total: <strong className="text-white block text-sm">{p4Data.report.total_rows}</strong></div>
                    <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded">Accepted: <strong className="block text-sm">{p4Data.report.accepted_rows}</strong></div>
                    <div className="p-2 bg-rose-500/10 text-rose-400 rounded">Quarantined: <strong className="block text-sm">{p4Data.report.quarantined_rows}</strong></div>
                    <div className="p-2 bg-cyan-500/10 text-cyan-400 rounded">Schema Match: <strong className="block text-sm">{p4Data.report.schema_match_pct}%</strong></div>
                  </div>
                  <div className="text-xs text-slate-400">
                    <strong>Mapped Headers:</strong> {JSON.stringify(p4Data.report.mapped_headers)}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* PROJECT 5 */}
        {activeTab === 'project5' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Radio className="text-cyan-400" size={20} />
                Project 5: Operations Command Center & Action Loop
              </h2>
              <p className="text-slate-400 text-sm mt-1">
                Topological alert correlation identifies root causes during telemetry storms, executes automated canary actions, and provides guaranteed 1-click transactional rollback.
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex gap-2">
                <button onClick={handleP5Trigger} className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold rounded-lg text-sm">
                  Correlate Telemetry & Remediate Incident
                </button>
              </div>

              {p5Incident && (
                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-rose-400 font-bold uppercase">{p5Incident.severity} Incident: {p5Incident.title}</span>
                    <span className="text-xs text-slate-400">ID: {p5Incident.incident_id}</span>
                  </div>
                  <p className="text-xs text-slate-300"><strong>Root Cause:</strong> {p5Incident.probable_root_cause}</p>
                  <p className="text-xs text-emerald-400"><strong>Remediation Executed:</strong> {p5Incident.remediation_action}</p>
                  {!p5RollbackDone ? (
                    <button
                      onClick={() => setP5RollbackDone(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded text-xs font-semibold"
                    >
                      <RotateCcw size={14} /> 1-Click Rollback State ({p5Incident.rollback_token})
                    </button>
                  ) : (
                    <div className="text-xs text-emerald-400 font-semibold">
                      ✓ System state transactionally rolled back to pre-incident baseline.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
