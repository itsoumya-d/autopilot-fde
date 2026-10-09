'use client';

import React, { useMemo, useRef, useState } from 'react';
import { Shield, GitBranch, FileText, Database, Radio, CheckCircle, AlertTriangle, RotateCcw } from 'lucide-react';
import {
  connectedWorkbench, createDemoWorkbench,
  type WorkbenchClient, type WorkbenchMode, type KnowledgeRole, type KnowledgeResult,
  type IntakeTicket, type InvoiceReport, type OnboardingResult, type IncidentResult, type RollbackResult,
} from '@/lib/workbench';
import { useWorkbenchAction } from './use-workbench-action';

const focus = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950';
const button = `px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors motion-reduce:transition-none ${focus}`;
const input = `w-full min-w-0 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white ${focus}`;
const tabs = [
  { id: 'project1', label: '1. Knowledge RAG', icon: Shield },
  { id: 'project2', label: '2. Intake-to-Resolution', icon: GitBranch },
  { id: 'project3', label: '3. Document Intelligence', icon: FileText },
  { id: 'project4', label: '4. Data Onboarding', icon: Database },
  { id: 'project5', label: '5. Ops Command Center', icon: Radio },
] as const;
type Tab = typeof tabs[number]['id'];
type PanelProps = { client: WorkbenchClient; mode: WorkbenchMode };

function ResultBox({ title, pending, error, mode, children }: {
  title: string; pending: boolean; error: string | null; mode: WorkbenchMode; children: React.ReactNode;
}) {
  return <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 min-w-0 space-y-3">
    <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">{title}</h3>
    <p className="text-xs text-slate-400">{mode === 'demo' ? 'Source: local synthetic example' : 'Source: connected API · synthetic sample workflow'}</p>
    {error && <p role="alert" className="text-sm text-rose-300 break-words">Request failed: {error}</p>}
    <div role="status" aria-live="polite" aria-atomic="true" aria-busy={pending} className="space-y-3">
      {pending && <p className="text-sm text-cyan-300">Waiting for {mode === 'demo' ? 'the local example' : 'the API'}…</p>}
      {children}
    </div>
  </div>;
}

function KnowledgePanel({ client, mode }: PanelProps) {
  const [role, setRole] = useState<KnowledgeRole>('engineering');
  const [query, setQuery] = useState('Engineering architecture microservices');
  const action = useWorkbenchAction<KnowledgeResult>();
  const changeQuery = (value: string) => { setQuery(value); action.reset(); };
  return <div className="space-y-6">
    <div>
      <h2 className="text-xl font-bold text-white">Permission-aware knowledge retrieval</h2>
      <p className="text-slate-400 text-sm mt-1">Try lexical retrieval and role filtering over a synthetic corpus. The selected role is a scenario input, not an authenticated identity or a production access-control guarantee.</p>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <form className="space-y-4 min-w-0" onSubmit={event => { event.preventDefault(); if (query.trim()) void action.run(signal => client.query(query.trim(), role, { signal })); }}>
        <fieldset>
          <legend className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Simulated role</legend>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">{(['engineering', 'hr', 'finance', 'guest'] as const).map(value => <label key={value} className={`flex items-center gap-2 px-2 py-2 rounded-lg text-xs capitalize border cursor-pointer ${role === value ? 'bg-cyan-500/20 border-cyan-500 text-cyan-200' : 'border-slate-700 text-slate-300'}`}>
            <input type="radio" name="knowledge-role" value={value} checked={role === value} onChange={() => { setRole(value); action.reset(); }} className="accent-cyan-400" />{value}
          </label>)}</div>
        </fieldset>
        <label htmlFor="knowledge-query" className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">Knowledge query</label>
        <div className="flex flex-wrap gap-2">
          <input id="knowledge-query" value={query} onChange={event => changeQuery(event.target.value)} className={`${input} flex-1 basis-48`} required maxLength={2000} />
          <button type="submit" disabled={action.pending || !query.trim()} className={button}>{action.pending ? 'Searching…' : 'Search'}</button>
        </div>
        <div className="text-xs text-slate-400 flex flex-wrap gap-3"><span>Try a sample:</span>
          <button type="button" onClick={() => changeQuery('Executive compensation bonus')} className={`underline hover:text-cyan-300 ${focus}`}>Executive compensation</button>
          <button type="button" onClick={() => changeQuery('Engineering architecture')} className={`underline hover:text-cyan-300 ${focus}`}>Architecture</button>
        </div>
      </form>
      <ResultBox title="Retrieval result" pending={action.pending} error={action.error} mode={mode}>
        {action.result ? <>
          <p className={`text-xs font-semibold ${action.result.allowed ? 'text-emerald-300' : 'text-rose-300'}`}>{action.result.allowed ? 'Role filter passed' : 'Blocked by sample role filter'}</p>
          <p className="text-sm text-slate-200 break-words">{action.result.answer}</p>
          <p className="text-xs text-slate-400">Heuristic grounding score: {(action.result.grounding_score * 100).toFixed(0)}% · Blocked matches: {action.result.blocked_count}</p>
          {action.result.citations.map(citation => <p key={citation.doc_id} className="text-xs text-slate-300 border-t border-slate-800 pt-2">Sample citation: {citation.title} ({citation.department})</p>)}
        </> : !action.pending && <p className="text-sm text-slate-400">Search the sample corpus to see a result.</p>}
      </ResultBox>
    </div>
  </div>;
}

function IntakePanel({ client, mode }: PanelProps) {
  const [content, setContent] = useState('Urgent: need refund of $450 on corporate billing');
  const action = useWorkbenchAction<IntakeTicket>();
  const ticket = action.result;
  const approved = ticket?.status === 'resolved' && !ticket.requires_approval;
  return <div className="space-y-6">
    <div>
      <h2 className="text-xl font-bold text-white">Intake-to-resolution workflow</h2>
      <p className="text-slate-400 text-sm mt-1">Heuristic triage pauses selected sample requests for approval. Approval changes an in-memory ticket record; it does not send a message, issue a refund, or change an account.</p>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <form className="space-y-3" onSubmit={event => { event.preventDefault(); if (content.trim()) void action.run(signal => client.ingest(content.trim(), { signal })); }}>
        <label htmlFor="ticket-content" className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Sample ticket content</label>
        <textarea id="ticket-content" value={content} disabled={action.pending} onChange={event => { setContent(event.target.value); action.reset(); }} rows={4} maxLength={5000} required className={input} />
        <button type="submit" disabled={action.pending || !content.trim()} className={button}>{action.pending && !ticket ? 'Ingesting…' : 'Ingest Ticket'}</button>
      </form>
      <ResultBox title="Ticket state" pending={action.pending} error={action.error} mode={mode}>
        {ticket ? <>
          <div className="flex flex-wrap justify-between gap-2 text-xs"><span className="text-slate-300">Ticket: <strong className="text-white">{ticket.id}</strong></span><span className="text-amber-200 font-semibold">{ticket.status}</span></div>
          <p className="text-xs text-slate-300">Step: {ticket.state_machine_step}</p>
          <p className="text-sm text-slate-300">Suggested action: {ticket.suggested_action}</p>
          {ticket.requires_approval && <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 space-y-3">
            <p className="flex items-center gap-2 text-xs text-amber-200"><AlertTriangle size={16} aria-hidden="true" /> Sample approval required</p>
            <button type="button" onClick={() => void action.run(signal => client.approve(ticket, { signal }), true)} disabled={action.pending || !ticket.approval_token} className={`${button} w-full bg-amber-400 hover:bg-amber-300`}>{action.pending ? 'Approving…' : 'Approve Sample Ticket'}</button>
          </div>}
          {approved && <p className="text-sm text-emerald-300 flex items-center gap-2"><CheckCircle size={16} aria-hidden="true" /> {mode === 'demo' ? 'Local demo' : 'API'} confirmed the ticket is resolved.</p>}
        </> : !action.pending && <p className="text-sm text-slate-400">Ingest a sample ticket to inspect its state.</p>}
      </ResultBox>
    </div>
  </div>;
}

function InvoicePanel({ client, mode }: PanelProps) {
  const [discrepancy, setDiscrepancy] = useState(false);
  const action = useWorkbenchAction<InvoiceReport>();
  return <div className="space-y-6">
    <div><h2 className="text-xl font-bold text-white">Document intelligence & validation</h2><p className="text-slate-400 text-sm mt-1">Audit the built-in synthetic invoice with deterministic arithmetic checks. This example does not extract an uploaded document or approve a real payment.</p></div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="space-y-4">
        <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={discrepancy} onChange={event => { setDiscrepancy(event.target.checked); action.reset(); }} className="accent-cyan-400" /> Inject a sample $10 arithmetic discrepancy</label>
        <button type="button" onClick={() => void action.run(signal => client.validate(discrepancy, { signal }))} disabled={action.pending} className={button}>{action.pending ? 'Auditing…' : 'Run Deterministic Audit'}</button>
      </div>
      <ResultBox title="Validation report" pending={action.pending} error={action.error} mode={mode}>
        {action.result ? <>
          <p className={`text-sm font-semibold ${action.result.is_valid ? 'text-emerald-300' : 'text-rose-300'}`}>{action.result.is_valid ? 'Sample arithmetic checks passed' : 'Sample validation failed'}</p>
          <p className="text-xs text-slate-300">Invoice: {action.result.invoice_id} · Math delta: ${action.result.math_delta.toFixed(2)}</p>
          <p className="text-sm text-slate-300">Recommendation only: {action.result.action_recommended}</p>
          <ul className="text-xs text-rose-300 list-disc pl-4 space-y-1">{action.result.discrepancy_details.map((detail, index) => <li key={index}>{detail}</li>)}</ul>
        </> : !action.pending && <p className="text-sm text-slate-400">Run the audit to inspect the sample invoice.</p>}
      </ResultBox>
    </div>
  </div>;
}

function OnboardingPanel({ client, mode }: PanelProps) {
  const action = useWorkbenchAction<OnboardingResult>();
  return <div className="space-y-6">
    <div><h2 className="text-xl font-bold text-white">Customer data onboarding</h2><p className="text-slate-400 text-sm mt-1">Map sample column names and identify invalid rows in the built-in five-row batch. No customer file is uploaded or written to a production database.</p></div>
    <button type="button" onClick={() => void action.run(signal => client.onboard({ signal }))} disabled={action.pending} className={button}>{action.pending ? 'Processing…' : 'Process Sample CSV Batch'}</button>
    <ResultBox title="Batch report" pending={action.pending} error={action.error} mode={mode}>
      {action.result ? <>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">{[
          ['Total rows', action.result.report.total_rows], ['Accepted rows', action.result.report.accepted_rows],
          ['Quarantined rows', action.result.report.quarantined_rows], ['Mapped schema', `${action.result.report.schema_match_pct}%`],
        ].map(([label, value]) => <div key={label} className="p-3 bg-slate-900 rounded-lg text-slate-300"><dt>{label}</dt><dd className="font-bold text-white text-lg mt-1">{value}</dd></div>)}</dl>
        <dl className="text-xs text-slate-300 space-y-1">{Object.entries(action.result.report.mapped_headers).map(([from, to]) => <div key={from} className="flex flex-wrap gap-2"><dt>{from}</dt><dd>→ {to}</dd></div>)}</dl>
        <ul className="list-disc pl-4 text-xs text-rose-300 space-y-1">{action.result.rows.filter(row => !row.is_valid).map(row => <li key={row.row_number}>Row {row.row_number}: {row.quarantine_reason}</li>)}</ul>
      </> : !action.pending && <p className="text-sm text-slate-400">Process the sample batch to see mappings and row-level issues.</p>}
    </ResultBox>
  </div>;
}

function OperationsPanel({ client, mode }: PanelProps) {
  const action = useWorkbenchAction<IncidentResult>();
  const rollback = useWorkbenchAction<RollbackResult>();
  const incident = action.result?.status === 'remediation_executed' ? action.result.incident : null;
  const rolledBack = rollback.result?.status === 'success' && rollback.result.incident_id === incident?.incident_id;
  const pending = action.pending || rollback.pending;
  return <div className="space-y-6">
    <div><h2 className="text-xl font-bold text-white">Operations command center</h2><p className="text-slate-400 text-sm mt-1">Correlate synthetic alerts and update an in-memory incident record. Remediation and rollback are simulated state transitions; no infrastructure is changed.</p></div>
    <button type="button" onClick={() => { rollback.reset(); void action.run(signal => client.correlate({ signal })); }} disabled={pending} className={button}>{action.pending ? 'Correlating…' : 'Run Sample Incident'}</button>
    <ResultBox title="Incident state" pending={pending} error={action.error || rollback.error} mode={mode}>
      {incident ? <>
        <div className="flex flex-wrap justify-between gap-2 text-xs"><span className="text-rose-300 font-semibold">{incident.severity}: {incident.title}</span><span className="text-slate-300">ID: {incident.incident_id}</span></div>
        <p className="text-sm text-slate-300">Sample root cause: {incident.probable_root_cause}</p>
        <p className="text-sm text-slate-300">Simulated action description: {incident.remediation_action}</p>
        <p className="text-xs text-slate-300">Record state: {rolledBack ? rollback.result?.incident.state : incident.state}</p>
        {!rolledBack && action.result?.status === 'remediation_executed' && action.result.rollback_ready && incident.can_rollback && incident.rollback_token && incident.state === 'remediated' && <button type="button" onClick={() => void rollback.run(signal => client.rollback(incident, { signal }))} disabled={pending} className={`flex items-center gap-2 px-3 py-2 bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/40 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors motion-reduce:transition-none ${focus}`}><RotateCcw size={16} aria-hidden="true" /> {rollback.pending ? 'Rolling back…' : 'Roll Back Sample Incident'}</button>}
        {rolledBack && <p className="text-sm text-emerald-300">{mode === 'demo' ? 'Local demo' : 'API'} confirmed the synthetic incident was rolled back.</p>}
      </> : action.result?.status === 'no_incidents' ? <p className="text-sm text-slate-300">No incidents eligible for remediation were returned.</p> : !pending && <p className="text-sm text-slate-400">Run a sample incident to inspect its state and try rollback.</p>}
    </ResultBox>
  </div>;
}

export default function ArchetypesPage() {
  const [activeTab, setActiveTab] = useState<Tab>('project1');
  const [mode, setMode] = useState<WorkbenchMode>('connected');
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const client = useMemo(() => mode === 'demo' ? createDemoWorkbench() : connectedWorkbench, [mode]);
  const Panel = { project1: KnowledgePanel, project2: IntakePanel, project3: InvoicePanel, project4: OnboardingPanel, project5: OperationsPanel }[activeTab];
  return <div className="space-y-8">
    <div>
      <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3"><span aria-hidden="true" className="p-2 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-xl text-white shadow-lg shadow-cyan-500/20">5</span>Enterprise Archetype Workbench</h1>
      <p className="text-slate-400 mt-2 text-sm max-w-3xl">Explore five reference workflows with synthetic inputs. Connected mode runs the repository’s backend implementations; local demo mode runs browser-only examples.</p>
    </div>
    <section aria-label="Workbench execution mode" className="bg-slate-900/60 border border-slate-700 rounded-xl p-4 space-y-3">
      <fieldset className="flex flex-wrap gap-4">
        <legend className="text-sm font-semibold text-white mb-2">Execution mode</legend>
        <label className="flex items-center gap-2 text-sm text-slate-200 cursor-pointer"><input type="radio" name="workbench-mode" checked={mode === 'connected'} onChange={() => setMode('connected')} className="accent-cyan-400" /> Connected API</label>
        <label className="flex items-center gap-2 text-sm text-slate-200 cursor-pointer"><input type="radio" name="workbench-mode" checked={mode === 'demo'} onChange={() => setMode('demo')} className="accent-cyan-400" /> Synthetic demo (local)</label>
      </fieldset>
      <p role="status" className={`text-sm ${mode === 'demo' ? 'text-amber-200' : 'text-cyan-200'}`}>{mode === 'demo' ? 'Synthetic demo selected. No API requests are made; records exist only in this browser session.' : 'Connected API selected. Results appear only after a successful API response. Backend examples use synthetic data and in-memory state.'}</p>
      <p className="text-xs text-slate-400">Use sample content only. Switching tabs or modes clears the displayed result. Requests already sent may still finish on the server. API failures never switch you to demo mode.</p>
    </section>
    <div role="tablist" aria-label="Enterprise archetypes" className="flex flex-wrap gap-2 border-b border-slate-800 pb-4">{tabs.map((tab, index) => {
      const Icon = tab.icon;
      return <button key={tab.id} ref={element => { tabRefs.current[index] = element; }} id={`tab-${tab.id}`} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls={`panel-${tab.id}`} tabIndex={activeTab === tab.id ? 0 : -1} onClick={() => setActiveTab(tab.id)}
        onKeyDown={event => {
          const target = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
          if (target >= 0) { event.preventDefault(); setActiveTab(tabs[target].id); tabRefs.current[target]?.focus(); }
        }}
        className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors motion-reduce:transition-none ${focus} ${activeTab === tab.id ? 'bg-cyan-500 text-slate-950 font-semibold shadow-lg shadow-cyan-500/20' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'}`}><Icon size={16} aria-hidden="true" />{tab.label}</button>;
    })}</div>
    {tabs.map(tab => <div key={tab.id} id={`panel-${tab.id}`} role="tabpanel" aria-labelledby={`tab-${tab.id}`} hidden={activeTab !== tab.id} tabIndex={0} className={`bg-slate-900/60 border border-slate-800 rounded-2xl p-4 sm:p-6 backdrop-blur-xl ${focus}`}>{activeTab === tab.id && <Panel key={`${mode}-${activeTab}`} client={client} mode={mode} />}</div>)}
  </div>;
}
