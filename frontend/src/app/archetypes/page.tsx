'use client';

import React, { useMemo, useRef, useState } from 'react';
import { Shield, GitBranch, FileText, Database, Radio, CheckCircle, AlertTriangle, RotateCcw } from 'lucide-react';
import {
  connectedWorkbench, createDemoWorkbench,
  type WorkbenchClient, type WorkbenchMode, type KnowledgeRole, type KnowledgeResult,
  type IntakeTicket, type InvoiceReport, type OnboardingResult, type IncidentResult, type RollbackResult,
} from '@/lib/workbench';
import { useWorkbenchAction } from './use-workbench-action';
import { motion, useReducedMotion } from 'framer-motion';
import { PageHeader, StatusBadge, SourceLabel } from '@/components/Workspace';
import invoicePreview from '@/lib/invoice-preview.json';

const focus = '';
const button = 'button-primary';
const input = 'field';
const money = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
const tabs = [
  { id: 'project1', label: 'Knowledge', icon: Shield },
  { id: 'project2', label: 'Intake', icon: GitBranch },
  { id: 'project3', label: 'Invoice checks', icon: FileText },
  { id: 'project4', label: 'Data onboarding', icon: Database },
  { id: 'project5', label: 'Operations', icon: Radio },
] as const;
type Tab = typeof tabs[number]['id'];
type PanelProps = { client: WorkbenchClient; mode: WorkbenchMode };

function ResultBox({ title, pending, error, mode, children, announcement }: {
  title: string; pending: boolean; error: string | null; mode: WorkbenchMode; children: React.ReactNode; announcement?: string;
}) {
  const reduced = useReducedMotion();
  return <section className="result-box" aria-label={title} aria-busy={pending}>
    <div className="result-heading"><h3>{title}</h3><SourceLabel>{mode === 'demo' ? 'Local example' : 'Connected API'}</SourceLabel></div>
    <p className="metadata mb-5">{mode === 'demo' ? 'Source: local synthetic example' : 'Source: connected API · synthetic sample workflow'}</p>
    {error && <p role="alert" className="error-state mb-4">Request failed: {error}</p>}
    <p role="status" aria-live="polite" className={pending ? 'metadata mb-3' : 'sr-only'}>{pending ? `Waiting for ${mode === 'demo' ? 'the local example' : 'the API'}…` : announcement ?? ''}</p>
    <motion.div initial={false} animate={{ opacity: pending ? 0.6 : 1 }} transition={{ duration: reduced ? 0 : 0.18 }} className="space-y-4">{children}</motion.div>
  </section>;
}

function KnowledgePanel({ client, mode }: PanelProps) {
  const [role, setRole] = useState<KnowledgeRole>('engineering');
  const [query, setQuery] = useState('Engineering architecture microservices');
  const action = useWorkbenchAction<KnowledgeResult>();
  const changeQuery = (value: string) => { setQuery(value); action.reset(); };
  return <div className="space-y-6">
    <div>
      <h2 className="text-lg font-semibold">Permission-aware knowledge retrieval</h2>
      <p className="muted text-sm mt-1 max-w-[78ch]">Try lexical retrieval and role filtering over a synthetic corpus. The selected role is a scenario input, not an authenticated identity or a production access-control guarantee.</p>
    </div>
    <div className="lab-columns">
      <form className="lab-input space-y-5" onSubmit={event => { event.preventDefault(); if (query.trim()) void action.run(signal => client.query(query.trim(), role, { signal })); }}>
        <fieldset>
          <legend className="label">Simulated role</legend>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">{(['engineering', 'hr', 'finance', 'guest'] as const).map(value => <label key={value} className="role-option capitalize cursor-pointer">
            <input type="radio" name="knowledge-role" value={value} checked={role === value} onChange={() => { setRole(value); action.reset(); }} className="accent-[var(--accent)]" />{value}
          </label>)}</div>
        </fieldset>
        <label htmlFor="knowledge-query" className="label">Knowledge query</label>
        <div className="flex flex-wrap gap-2">
          <input id="knowledge-query" value={query} onChange={event => changeQuery(event.target.value)} className={`${input} flex-1 basis-48`} required maxLength={2000} />
          <button type="submit" disabled={action.pending || !query.trim()} className={button}>{action.pending ? 'Searching…' : 'Search'}</button>
        </div>
        <div className="metadata flex flex-wrap gap-3"><span>Try a sample:</span>
          <button type="button" onClick={() => changeQuery('Executive compensation bonus')} className={`underline hover:text-[var(--accent)] ${focus}`}>Executive compensation</button>
          <button type="button" onClick={() => changeQuery('Engineering architecture')} className={`underline hover:text-[var(--accent)] ${focus}`}>Architecture</button>
        </div>
      </form>
      <ResultBox title="Retrieval result" announcement={action.result ? (action.result.allowed ? "Role filter passed. Retrieval result available." : "Blocked by sample role filter.") : undefined} pending={action.pending} error={action.error} mode={mode}>
        {action.result ? <>
          <p className={`text-xs font-semibold ${action.result.allowed ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}>{action.result.allowed ? 'Role filter passed' : 'Blocked by sample role filter'}</p>
          <p className="text-sm leading-relaxed break-words">{action.result.answer}</p>
          <p className="metadata">Heuristic grounding score: {(action.result.grounding_score * 100).toFixed(0)}% · Blocked matches: {action.result.blocked_count}</p>
          {action.result.citations.map(citation => <p key={citation.doc_id} className="metadata border-t border-[var(--border)] pt-3">Sample citation: {citation.title} ({citation.department})</p>)}
        </> : !action.pending && <p className="muted text-sm">Search the sample corpus to see a result.</p>}
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
      <h2 className="text-lg font-semibold">Intake-to-resolution workflow</h2>
      <p className="muted text-sm mt-1 max-w-[78ch]">Heuristic triage pauses selected sample requests for approval. Approval changes an in-memory ticket record; it does not send a message, issue a refund, or change an account.</p>
    </div>
    <div className="lab-columns">
      <form className="lab-input space-y-4" onSubmit={event => { event.preventDefault(); if (content.trim()) void action.run(signal => client.ingest(content.trim(), { signal })); }}>
        <label htmlFor="ticket-content" className="label">Sample ticket content</label>
        <textarea id="ticket-content" value={content} disabled={action.pending} onChange={event => { setContent(event.target.value); action.reset(); }} rows={4} maxLength={5000} required className={input} />
        <button type="submit" disabled={action.pending || !content.trim()} className={button}>{action.pending && !ticket ? 'Ingesting…' : 'Ingest Ticket'}</button>
      </form>
      <ResultBox title="Ticket state" announcement={ticket ? `Ticket ${ticket.id}: ${ticket.status}.` : undefined} pending={action.pending} error={action.error} mode={mode}>
        {ticket ? <>
          <div className="flex flex-wrap justify-between gap-2 text-xs"><span className="muted">Ticket: <strong className="mono text-[var(--text)]">{ticket.id}</strong></span><span className="status-badge warning">{ticket.status}</span></div>
          <p className="metadata">Priority: {ticket.priority} · Step: {ticket.state_machine_step}</p>
          <ol className="ticket-stages" aria-label="Sample ticket stages">
            <li aria-current={!ticket.requires_approval && !approved ? 'step' : undefined}>01 · Received</li>
            <li aria-current={ticket.requires_approval ? 'step' : undefined}>02 · Awaiting review</li>
            <li aria-current={approved ? 'step' : undefined}>03 · Resolved in sample</li>
          </ol>
          <p className="text-sm">Suggested action: {ticket.suggested_action}</p>
          {ticket.requires_approval && <div className="review-note space-y-3">
            <p className="flex items-center gap-2 text-xs text-[var(--warning)]"><AlertTriangle size={16} aria-hidden="true" /> Sample approval required</p>
            <button type="button" onClick={() => void action.run(signal => client.approve(ticket, { signal }), true)} disabled={action.pending || !ticket.approval_token} className={`${button} w-full`}>{action.pending ? 'Approving…' : 'Approve Sample Ticket'}</button>
          </div>}
          {approved && <p className="text-sm text-[var(--success)] flex items-center gap-2"><CheckCircle size={16} aria-hidden="true" /> {mode === 'demo' ? 'Local demo' : 'API'} confirmed the ticket is resolved.</p>}
        </> : !action.pending && <p className="muted text-sm">Ingest a sample ticket to inspect its state.</p>}
      </ResultBox>
    </div>
  </div>;
}

function InvoicePanel({ client, mode }: PanelProps) {
  const [discrepancy, setDiscrepancy] = useState(false);
  const action = useWorkbenchAction<InvoiceReport>();
  const statedTotal = invoicePreview.total_amount + (discrepancy ? 10 : 0);
  return <div className="space-y-6">
    <div className="lab-case-header"><h2>Document intelligence & validation</h2><p>Audit the built-in synthetic invoice with deterministic arithmetic checks. This example does not extract an uploaded document or approve a real payment.</p></div>
    <div className="lab-columns">
      <article className="invoice-preview" aria-label="Built-in sample invoice preview">
        <SourceLabel>Built-in sample preview</SourceLabel>
        <div className="invoice-masthead"><div><p className="page-kicker">Invoice</p><h3>{invoicePreview.vendor}</h3></div><div className="metadata text-right"><p className="mono">{invoicePreview.invoice_id}</p><p>{invoicePreview.date}</p></div></div>
        <table className="invoice-lines"><caption className="sr-only">Built-in invoice line items</caption><thead><tr><th scope="col">Description</th><th scope="col">Qty</th><th scope="col">Amount</th></tr></thead><tbody>{invoicePreview.line_items.map(line => <tr key={line.description}><td className="pr-3">{line.description}<span className="block metadata">{money(line.unit_price)} each</span></td><td>{line.quantity}</td><td>{money(line.total)}</td></tr>)}</tbody></table>
        <dl className="invoice-totals"><div><dt>Subtotal</dt><dd>{money(invoicePreview.subtotal)}</dd></div><div><dt>Tax</dt><dd>{money(invoicePreview.tax)}</dd></div><div className="invoice-total"><dt>Stated total</dt><dd>{money(statedTotal)}</dd></div></dl>
      </article>
      <div className="space-y-5">
        <div className="surface surface-pad space-y-4"><h3>Check the arithmetic</h3><label className="flex items-start gap-3 text-sm"><input type="checkbox" checked={discrepancy} onChange={event => { setDiscrepancy(event.target.checked); action.reset(); }} className="mt-1" /> Inject a sample $10 arithmetic discrepancy</label><p className="metadata">Changes the stated total only. The expected total stays {money(invoicePreview.total_amount)}.</p><button type="button" onClick={() => void action.run(signal => client.validate(discrepancy, { signal }))} disabled={action.pending} className={button}>{action.pending ? 'Auditing…' : 'Run Deterministic Audit'}</button></div>
        <ResultBox title="Validation report" announcement={action.result ? (action.result.is_valid ? "Invoice check passed." : "Invoice check failed. Review the difference.") : undefined} pending={action.pending} error={action.error} mode={mode}>
          {action.result ? <>
            <StatusBadge tone={action.result.is_valid ? 'success' : 'danger'}>{action.result.is_valid ? 'Sample arithmetic checks passed' : 'Sample validation failed'}</StatusBadge>
            <dl className="validation-totals"><div><dt>Expected</dt><dd>{money(invoicePreview.total_amount)}</dd></div><div><dt>Stated</dt><dd>{money(statedTotal)}</dd></div><div><dt>Difference</dt><dd className={action.result.math_delta ? 'text-[var(--danger)]' : 'text-[var(--success)]'}>{money(action.result.math_delta)}</dd></div></dl>
            <p className="metadata">Invoice: {action.result.invoice_id} · Math delta: ${action.result.math_delta.toFixed(2)}</p>
            <p className="metadata">Difference = expected minus stated. This is an arithmetic check, not payment authorization.</p>
            <p className="text-sm">Recommendation only: {action.result.action_recommended}</p>
            <ul className="text-xs text-[var(--danger)] list-disc pl-4 space-y-2">{action.result.discrepancy_details.map((detail, index) => <li key={index}>{detail}</li>)}</ul>
          </> : !action.pending && <p className="muted text-sm">Run the audit to inspect the sample invoice.</p>}
        </ResultBox>
      </div>
    </div>
  </div>;
}

function OnboardingPanel({ client, mode }: PanelProps) {
  const action = useWorkbenchAction<OnboardingResult>();
  return <div className="space-y-6">
    <div><h2 className="text-lg font-semibold">Customer data onboarding</h2><p className="muted text-sm mt-1 max-w-[78ch]">Map sample column names and identify invalid rows in the built-in five-row batch. No customer file is uploaded or written to a production database.</p></div>
    <button type="button" onClick={() => void action.run(signal => client.onboard({ signal }))} disabled={action.pending} className={button}>{action.pending ? 'Processing…' : 'Process Sample CSV Batch'}</button>
    <ResultBox title="Batch report" announcement={action.result ? `Batch processed: ${action.result.report.accepted_rows} accepted, ${action.result.report.quarantined_rows} quarantined.` : undefined} pending={action.pending} error={action.error} mode={mode}>
      {action.result ? <>
        <dl className="ledger text-xs">{[
          ['Total rows', action.result.report.total_rows], ['Accepted rows', action.result.report.accepted_rows],
          ['Quarantined rows', action.result.report.quarantined_rows], ['Mapped schema', `${action.result.report.schema_match_pct}%`],
        ].map(([label, value]) => <div key={label} className="ledger-stat"><dt>{label}</dt><dd className="font-semibold mt-1">{value}</dd></div>)}</dl>
        <dl className="grid gap-2 sm:grid-cols-2 text-xs">{Object.entries(action.result.report.mapped_headers).map(([from, to]) => <div key={from} className="flex flex-wrap gap-2 border border-[var(--border)] bg-white p-3 rounded"><dt className="mono">{from}</dt><dd>→ {to}</dd></div>)}</dl>
        <div className="table-scroll surface" role="region" aria-label="Sample row validation" tabIndex={0}><table className="register"><thead><tr><th scope="col">Row</th><th scope="col">Result</th><th scope="col">Validation detail</th></tr></thead><tbody>{action.result.rows.map(row => <tr key={row.row_number}><td className="mono">{row.row_number}</td><td><StatusBadge tone={row.is_valid ? "success" : "warning"}>{row.is_valid ? "Accepted" : "Quarantined"}</StatusBadge></td><td className="text-xs">{row.is_valid ? "Passed sample validation" : `Row ${row.row_number}: ${row.quarantine_reason}`}</td></tr>)}</tbody></table></div>
      </> : !action.pending && <p className="muted text-sm">Process the sample batch to see mappings and row-level issues.</p>}
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
    <div><h2 className="text-lg font-semibold">Operations command center</h2><p className="muted text-sm mt-1 max-w-[78ch]">Correlate synthetic alerts and update an in-memory incident record. Remediation and rollback are simulated state transitions; no infrastructure is changed.</p></div>
    <button type="button" onClick={() => { rollback.reset(); void action.run(signal => client.correlate({ signal })); }} disabled={pending} className={button}>{action.pending ? 'Correlating…' : 'Run Sample Incident'}</button>
    <ResultBox title="Incident state" announcement={incident ? `Incident ${incident.incident_id}: ${rolledBack ? "rolled back" : incident.state}.` : undefined} pending={pending} error={action.error || rollback.error} mode={mode}>
      {incident ? <>
        <div className="flex flex-wrap justify-between gap-2 text-xs"><span className="text-[var(--danger)] font-semibold">{incident.severity}: {incident.title}</span><span className="muted">ID: {incident.incident_id}</span></div>
        <p className="text-sm">Sample root cause: {incident.probable_root_cause}</p>
        <p className="text-sm">Simulated action description: {incident.remediation_action}</p>
        <p className="metadata">Record state: {rolledBack ? rollback.result?.incident.state : incident.state}</p>
        {!rolledBack && action.result?.status === 'remediation_executed' && action.result.rollback_ready && incident.can_rollback && incident.rollback_token && incident.state === 'remediated' && <button type="button" onClick={() => void rollback.run(signal => client.rollback(incident, { signal }))} disabled={pending} className="button-danger"><RotateCcw size={16} aria-hidden="true" /> {rollback.pending ? 'Rolling back…' : 'Roll Back Sample Incident'}</button>}
        {rolledBack && <p className="text-sm text-[var(--success)]">{mode === 'demo' ? 'Local demo' : 'API'} confirmed the synthetic incident was rolled back.</p>}
      </> : action.result?.status === 'no_incidents' ? <p className="text-sm">No incidents eligible for remediation were returned.</p> : !pending && <p className="muted text-sm">Run a sample incident to inspect its state and try rollback.</p>}
    </ResultBox>
  </div>;
}

export default function ArchetypesPage() {
  const [activeTab, setActiveTab] = useState<Tab>('project1');
  const [mode, setMode] = useState<WorkbenchMode>('connected');
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const client = useMemo(() => mode === 'demo' ? createDemoWorkbench() : connectedWorkbench, [mode]);
  const Panel = { project1: KnowledgePanel, project2: IntakePanel, project3: InvoicePanel, project4: OnboardingPanel, project5: OperationsPanel }[activeTab];
  const reduced = useReducedMotion();
  return <div className="page-stack">
    <PageHeader eyebrow="Five working examples" title="Workflow Lab" description="Inspect the input. Follow the evidence. Review the result." />
    <section aria-label="Workbench execution mode" className="space-y-3">
      <div className="mode-toolbar"><fieldset><legend>Execution mode</legend><label><input type="radio" name="workbench-mode" checked={mode === 'connected'} onChange={() => setMode('connected')} /> Connected API</label><label><input type="radio" name="workbench-mode" checked={mode === 'demo'} onChange={() => setMode('demo')} /> Synthetic demo (local)</label></fieldset><StatusBadge>Synthetic inputs · no external actions</StatusBadge></div>
      <p role="status" className="metadata">{mode === 'demo' ? 'Synthetic demo selected. No API requests are made; records exist only in this browser session.' : 'Connected API selected. Results appear only after a successful API response. Backend examples use synthetic data and in-memory state.'}</p>
      <details className="mode-details"><summary>How these examples work</summary><p>Use sample content only. Switching tabs or modes clears the displayed result. Requests already sent may still finish on the server. API failures never switch you to demo mode.</p></details>
    </section>
    <div role="tablist" aria-label="Workflow Lab examples" className="lab-tabs">{tabs.map((tab, index) => {
      const Icon = tab.icon;
      return <button key={tab.id} ref={element => { tabRefs.current[index] = element; }} id={`tab-${tab.id}`} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls={`panel-${tab.id}`} tabIndex={activeTab === tab.id ? 0 : -1} onClick={() => setActiveTab(tab.id)}
        onKeyDown={event => {
          const target = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
          if (target >= 0) { event.preventDefault(); setActiveTab(tabs[target].id); tabRefs.current[target]?.focus(); }
        }} className="lab-tab motion-reduce:transition-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"><Icon size={15} aria-hidden="true" />{tab.label}{activeTab === tab.id && <motion.span aria-hidden="true" layoutId="lab-tab-marker" className="tab-underline" transition={{ duration: reduced ? 0 : 0.16, ease: [0.2, 0.8, 0.2, 1] }} />}</button>;
    })}</div>
    {tabs.map(tab => <div key={tab.id} id={`panel-${tab.id}`} role="tabpanel" aria-labelledby={`tab-${tab.id}`} hidden={activeTab !== tab.id} tabIndex={0} className="lab-panel">{activeTab === tab.id && <Panel key={`${mode}-${activeTab}`} client={client} mode={mode} />}</div>)}
  </div>;
}
