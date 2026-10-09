import { request } from './api';

export type WorkbenchMode = 'connected' | 'demo';
export type KnowledgeRole = 'engineering' | 'hr' | 'finance' | 'guest';

export interface KnowledgeResult {
  query: string;
  user_role: string;
  allowed: boolean;
  answer: string;
  grounding_score: number;
  blocked_count: number;
  citations: Array<{ doc_id: string; title: string; department: string }>;
}

export interface IntakeTicket {
  id: string;
  customer: string;
  content: string;
  channel: string;
  priority: string;
  status: string;
  state_machine_step: string;
  requires_approval: boolean;
  approval_token: string | null;
  suggested_action: string;
  assigned_tier: string;
}

export interface InvoiceReport {
  invoice_id: string;
  is_valid: boolean;
  arithmetic_valid: boolean;
  discrepancy_details: string[];
  math_delta: number;
  action_recommended: string;
}

export interface OnboardingResult {
  report: {
    batch_id: string;
    source_filename: string;
    total_rows: number;
    accepted_rows: number;
    quarantined_rows: number;
    schema_match_pct: number;
    mapped_headers: Record<string, string>;
  };
  rows: Array<{ row_number: number; is_valid: boolean; quarantine_reason: string | null }>;
}

export interface Incident {
  incident_id: string;
  title: string;
  severity: string;
  probable_root_cause: string;
  remediation_action: string;
  state: string;
  can_rollback: boolean;
  rollback_token: string | null;
}

export type IncidentResult =
  | { status: 'no_incidents'; incidents: Incident[] }
  | { status: 'remediation_executed'; incident: Incident; rollback_ready: boolean };

export interface RollbackResult {
  incident_id: string;
  status: 'success';
  action: string;
  incident: Incident;
}

type Options = { signal?: AbortSignal };
export interface WorkbenchClient {
  query: (query: string, role: KnowledgeRole, options?: Options) => Promise<KnowledgeResult>;
  ingest: (content: string, options?: Options) => Promise<IntakeTicket>;
  approve: (ticket: IntakeTicket, options?: Options) => Promise<IntakeTicket>;
  validate: (discrepancy: boolean, options?: Options) => Promise<InvoiceReport>;
  onboard: (options?: Options) => Promise<OnboardingResult>;
  correlate: (options?: Options) => Promise<IncidentResult>;
  rollback: (incident: Incident, options?: Options) => Promise<RollbackResult>;
}

type JsonObject = Record<string, unknown>;
const object = (value: unknown): value is JsonObject => typeof value === 'object' && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === 'string';
const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const bool = (value: unknown): value is boolean => typeof value === 'boolean';
const count = (value: unknown): value is number => number(value) && Number.isSafeInteger(value) && value >= 0;
const nullableText = (value: unknown) => value === null || text(value);
const strings = (value: unknown) => Array.isArray(value) && value.every(text);
const ticketShape = (v: unknown): v is IntakeTicket => object(v) && text(v.id) && text(v.status) && text(v.suggested_action)
  && bool(v.requires_approval) && nullableText(v.approval_token) && text(v.state_machine_step)
  && text(v.customer) && text(v.content) && text(v.channel) && text(v.priority) && text(v.assigned_tier)
  && (!v.requires_approval || (text(v.approval_token) && v.approval_token.length > 0));
const incidentShape = (v: unknown): v is Incident => object(v) && text(v.incident_id) && text(v.title)
  && text(v.severity) && text(v.probable_root_cause) && text(v.remediation_action) && text(v.state)
  && bool(v.can_rollback) && nullableText(v.rollback_token);

function onboardingShape(value: unknown): value is OnboardingResult {
  if (!object(value) || !object(value.report) || !Array.isArray(value.rows)) return false;
  const report = value.report;
  if (!text(report.batch_id) || !text(report.source_filename) || !count(report.total_rows)
    || !count(report.accepted_rows) || !count(report.quarantined_rows)
    || !number(report.schema_match_pct) || report.schema_match_pct < 0 || report.schema_match_pct > 100
    || !object(report.mapped_headers) || !Object.values(report.mapped_headers).every(text)) return false;
  if (!value.rows.every(row => object(row) && count(row.row_number) && row.row_number > 0 && bool(row.is_valid)
    && nullableText(row.quarantine_reason) && (row.is_valid || (text(row.quarantine_reason) && row.quarantine_reason.trim().length > 0)))) return false;
  const rows = value.rows as OnboardingResult['rows'];
  return rows.length === report.total_rows && report.total_rows === report.accepted_rows + report.quarantined_rows
    && rows.filter(row => row.is_valid).length === report.accepted_rows
    && rows.filter(row => !row.is_valid).length === report.quarantined_rows
    && new Set(rows.map(row => row.row_number)).size === rows.length;
}

// Responses are checked at the boundary: a proxy's HTML/JSON error must never
// become a success card. All endpoints share the configured API base in api.ts.
async function post<T>(path: string, payload: unknown, valid: (v: unknown) => boolean, options?: Options): Promise<T> {
  const value = await request<unknown>(`/archetypes${path}`, {
    method: 'POST',
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
    signal: options?.signal,
  });
  if (!valid(value)) throw new Error('The API returned an unexpected response. No result was confirmed.');
  return value as T;
}

export const connectedWorkbench: WorkbenchClient = {
  query: (query, role, options) => post<KnowledgeResult>('/project1/query', { query, user_role: role },
    v => object(v) && text(v.query) && text(v.user_role) && v.query === query && v.user_role === role && bool(v.allowed) && text(v.answer) && number(v.grounding_score) && v.grounding_score >= 0 && v.grounding_score <= 1 && count(v.blocked_count)
      && Array.isArray(v.citations) && v.citations.every(c => object(c) && text(c.doc_id) && text(c.title) && text(c.department)), options),
  ingest: (content, options) => post<IntakeTicket>('/project2/ticket', { customer: 'Sample customer', content },
    v => ticketShape(v) && v.customer === 'Sample customer' && v.content === content && v.channel === 'slack'
      && (v.requires_approval
        ? v.status === 'pending_approval' && v.state_machine_step === 'awaiting_human_approval'
        : v.status === 'resolving' && v.state_machine_step === 'automated_resolution' && v.approval_token === null), options),
  approve: (ticket, options) => {
    if (ticket.status !== 'pending_approval' || ticket.state_machine_step !== 'awaiting_human_approval' || !ticket.requires_approval || !ticket.approval_token) return Promise.reject(new Error('This ticket has no pending approval.'));
    return post<IntakeTicket>('/project2/approve', { ticket_id: ticket.id, approval_token: ticket.approval_token, operator: 'Workbench reviewer' },
      v => ticketShape(v) && v.id === ticket.id && v.status === 'resolved' && !v.requires_approval && v.approval_token === null && v.state_machine_step === 'action_executed', options);
  },
  validate: (discrepancy, options) => post<InvoiceReport>('/project3/validate-invoice', { simulate_discrepancy: discrepancy },
    v => object(v) && text(v.invoice_id) && bool(v.is_valid) && bool(v.arithmetic_valid) && strings(v.discrepancy_details)
      && number(v.math_delta) && text(v.action_recommended)
      && v.arithmetic_valid === (Array.isArray(v.discrepancy_details) && v.discrepancy_details.length === 0)
      && (!v.is_valid || (v.arithmetic_valid && Math.abs(v.math_delta) <= 0.01)), options),
  onboard: options => post<OnboardingResult>('/project4/onboard-data', { filename: 'sample_customer_export.csv' },
    onboardingShape, options),
  correlate: options => post<IncidentResult>('/project5/correlate-and-remediate?simulate_incident=true', undefined,
    v => object(v) && ((v.status === 'no_incidents' && Array.isArray(v.incidents) && v.incidents.length === 0)
      || (v.status === 'remediation_executed' && incidentShape(v.incident) && v.incident.state === 'remediated' && v.rollback_ready === true && v.incident.can_rollback && Boolean(v.incident.rollback_token))), options),
  rollback: (incident, options) => {
    if (incident.state !== 'remediated' || !incident.can_rollback || !incident.rollback_token) {
      return Promise.reject(new Error('This incident has no available rollback.'));
    }
    return post<RollbackResult>('/project5/rollback', { incident_id: incident.incident_id, rollback_token: incident.rollback_token, operator: 'Workbench reviewer' },
      v => object(v) && v.status === 'success' && v.incident_id === incident.incident_id && text(v.action)
        && incidentShape(v.incident) && v.incident.incident_id === incident.incident_id && v.incident.state === 'rolled_back' && !v.incident.can_rollback && !v.incident.rollback_token, options);
  },
};

// Opt-in local examples. This client never calls the network and is never used
// to recover an API failure. Its in-memory records disappear on a mode change.
export function createDemoWorkbench(): WorkbenchClient {
  let sequence = 0;
  const tickets = new Map<string, IntakeTicket>();
  const incidents = new Map<string, Incident>();
  const id = (prefix: string) => `DEMO-${prefix}-${++sequence}`;
  return {
    async query(query, role) {
      const docs = [
        { id: 'DEMO-DOC-1', title: 'Holiday policy', department: 'General', content: 'The sample holiday policy offers 25 days of PTO.', roles: ['engineering', 'hr', 'finance', 'guest'] },
        { id: 'DEMO-DOC-2', title: 'Engineering architecture', department: 'Engineering', content: 'The sample architecture uses an event bus between services.', roles: ['engineering'] },
        { id: 'DEMO-DOC-3', title: 'Executive compensation bonus', department: 'HR', content: 'This synthetic policy describes executive bonus review.', roles: ['hr'] },
      ];
      const terms = query.toLowerCase().match(/\w+/g) || [];
      const matches = docs.map(doc => ({ ...doc, score: terms.filter(term => `${doc.title} ${doc.content}`.toLowerCase().includes(term)).length }))
        .filter(doc => doc.score > 0).sort((a, b) => b.score - a.score);
      const found = matches.find(doc => doc.roles.includes(role));
      const blocked = matches.filter(doc => !doc.roles.includes(role)).length;
      return { query, user_role: role, allowed: Boolean(found) || blocked === 0,
        answer: found ? found.content : blocked ? 'Access denied in this synthetic role example.' : 'No matching document in the local sample corpus.',
        grounding_score: found ? 1 : 0, blocked_count: blocked,
        citations: found ? [{ doc_id: found.id, title: found.title, department: found.department }] : [] };
    },
    async ingest(content) {
      const gated = /refund|cancel subscription|delete|grant access/i.test(content);
      const ticket: IntakeTicket = { id: id('TICKET'), customer: 'Sample customer', content, channel: 'slack', priority: /urgent|outage/i.test(content) ? 'high' : 'medium',
        status: gated ? 'pending_approval' : 'resolving', state_machine_step: gated ? 'awaiting_human_approval' : 'automated_resolution',
        requires_approval: gated, approval_token: gated ? id('APPROVAL') : null, suggested_action: gated ? 'Review the sample request before changing its state.' : 'Prepare a sample self-service guide.', assigned_tier: 'tier2' };
      tickets.set(ticket.id, ticket);
      return { ...ticket };
    },
    async approve(ticket) {
      const current = tickets.get(ticket.id);
      if (!current?.requires_approval || !ticket.approval_token || current.approval_token !== ticket.approval_token) throw new Error('No matching pending demo approval.');
      const updated = { ...current, status: 'resolved', state_machine_step: 'action_executed', requires_approval: false, approval_token: null };
      tickets.set(updated.id, updated);
      return { ...updated };
    },
    async validate(discrepancy) {
      return { invoice_id: 'DEMO-INVOICE', is_valid: !discrepancy, arithmetic_valid: !discrepancy, math_delta: discrepancy ? -10 : 0,
        discrepancy_details: discrepancy ? ['Sample subtotal + tax ($3456.00) differs from stated total ($3466.00) by $10.00.'] : [],
        action_recommended: discrepancy ? 'MANUAL_AUDIT_REQUIRED: Sample arithmetic mismatch.' : 'AUTO_APPROVE: Sample arithmetic checks passed.' };
    },
    async onboard() {
      return { report: { batch_id: id('BATCH'), source_filename: 'sample_customer_export.csv', total_rows: 5, accepted_rows: 2, quarantined_rows: 3, schema_match_pct: 100,
        mapped_headers: { Client_ID: 'customer_id', 'Full Name': 'full_name', 'Email Address': 'email', ARR: 'annual_spend' } },
      rows: [
        { row_number: 1, is_valid: true, quarantine_reason: null },
        { row_number: 2, is_valid: false, quarantine_reason: 'Malformed email address' },
        { row_number: 3, is_valid: false, quarantine_reason: 'Missing mandatory customer_id' },
        { row_number: 4, is_valid: false, quarantine_reason: 'Negative annual spend' },
        { row_number: 5, is_valid: true, quarantine_reason: null },
      ] };
    },
    async correlate() {
      const incident: Incident = { incident_id: id('INCIDENT'), title: 'Synthetic API latency and database saturation', severity: 'critical',
        probable_root_cause: 'Sample database connection pool saturation.', remediation_action: 'Record a simulated pool-expansion action.',
        state: 'remediated', can_rollback: true, rollback_token: id('ROLLBACK') };
      incidents.set(incident.incident_id, incident);
      return { status: 'remediation_executed', incident: { ...incident }, rollback_ready: true };
    },
    async rollback(incident) {
      const current = incidents.get(incident.incident_id);
      if (current?.state !== 'remediated' || !incident.rollback_token || current.rollback_token !== incident.rollback_token) throw new Error('No matching available demo rollback.');
      const updated = { ...current, state: 'rolled_back', can_rollback: false, rollback_token: null };
      incidents.set(updated.incident_id, updated);
      return { incident_id: updated.incident_id, status: 'success', action: 'Reverted the local synthetic incident record.', incident: { ...updated } };
    },
  };
}
