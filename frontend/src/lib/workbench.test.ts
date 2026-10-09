import { afterEach, describe, expect, it, vi } from 'vitest';
import { connectedWorkbench, createDemoWorkbench, type Incident, type IntakeTicket } from './workbench';

const ok = (value: unknown) => new Response(JSON.stringify(value), { status: 200 });
const ticket: IntakeTicket = {
  id: 'TICK-42', customer: 'Sample customer', content: 'refund', channel: 'slack', priority: 'high', status: 'pending_approval',
  state_machine_step: 'awaiting_human_approval', requires_approval: true, approval_token: 'APP-42', suggested_action: 'Review refund', assigned_tier: 'tier2',
};
const resolved = { ...ticket, status: 'resolved', state_machine_step: 'action_executed', requires_approval: false, approval_token: null };
const incident: Incident = {
  incident_id: 'INC-42', title: 'Synthetic alert', severity: 'critical', probable_root_cause: 'Pool saturation',
  remediation_action: 'Simulated state update', state: 'remediated', can_rollback: true, rollback_token: 'RBK-42',
};
const rollback = { incident_id: incident.incident_id, status: 'success', action: 'Reverted synthetic record', incident: { ...incident, state: 'rolled_back', can_rollback: false, rollback_token: '' } };
const knowledge = { query: 'architecture', user_role: 'engineering', allowed: true, answer: 'Sample answer', grounding_score: 1, blocked_count: 0, citations: [] };

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules(); });

describe('connected workbench boundary', () => {
  it('uses NEXT_PUBLIC_API_URL including its path and normalizes its trailing slash', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'https://example.test/custom/api/');
    vi.resetModules();
    const { connectedWorkbench: configured } = await import('./workbench');
    const fetchMock = vi.fn(async (_url: unknown) => ok(knowledge));
    vi.stubGlobal('fetch', fetchMock);
    await configured.query('architecture', 'engineering');
    expect(fetchMock.mock.calls[0]?.[0]).toBe('https://example.test/custom/api/archetypes/project1/query');
  });

  it('sends actual approval and rollback requests with IDs, tokens, and abort signals', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(ok(resolved)).mockResolvedValueOnce(ok(rollback));
    vi.stubGlobal('fetch', fetchMock);
    const signal = new AbortController().signal;
    await expect(connectedWorkbench.approve(ticket, { signal })).resolves.toEqual(resolved);
    await expect(connectedWorkbench.rollback(incident, { signal })).resolves.toEqual(rollback);
    const [approveUrl, approveInit] = fetchMock.mock.calls[0];
    expect(approveUrl).toMatch(/\/api\/archetypes\/project2\/approve$/);
    expect(approveInit.method).toBe('POST');
    expect(approveInit.signal).toBe(signal);
    expect(JSON.parse(approveInit.body)).toEqual({ ticket_id: 'TICK-42', approval_token: 'APP-42', operator: 'Workbench reviewer' });
    const [rollbackUrl, rollbackInit] = fetchMock.mock.calls[1];
    expect(rollbackUrl).toMatch(/\/api\/archetypes\/project5\/rollback$/);
    expect(JSON.parse(rollbackInit.body)).toEqual({ incident_id: 'INC-42', rollback_token: 'RBK-42', operator: 'Workbench reviewer' });
    expect(rollbackInit.signal).toBe(signal);
    expect(approveInit.headers).not.toHaveProperty('X-API-Key');
  });

  it.each([400, 401, 403, 404, 409, 422, 500])('rejects HTTP %i instead of producing a sample result', async status => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: `Failure ${status}` }), { status })));
    await expect(connectedWorkbench.query('architecture', 'engineering')).rejects.toThrow(`Failure ${status}`);
  });

  it('renders validation details and handles invalid JSON and network errors', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: [{ msg: 'Field required', loc: ['body', 'content'] }] }), { status: 422 }))
      .mockResolvedValueOnce(new Response('<html>proxy page</html>', { status: 200 }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);
    await expect(connectedWorkbench.ingest('refund')).rejects.toThrow('Field required');
    await expect(connectedWorkbench.ingest('refund')).rejects.toThrow('invalid JSON');
    await expect(connectedWorkbench.ingest('refund')).rejects.toThrow('Failed to fetch');
  });

  it.each([
    { ...resolved, id: 'other-ticket' }, { ...resolved, approval_token: 'APP-42' },
    { ...resolved, requires_approval: true }, { ...resolved, state_machine_step: 'awaiting_human_approval' },
    { ...resolved, suggested_action: {} }, { ...resolved, customer: undefined },
  ])('rejects malformed or contradictory approval responses', async response => {
    vi.stubGlobal('fetch', vi.fn(async () => ok(response)));
    await expect(connectedWorkbench.approve(ticket)).rejects.toThrow('unexpected response');
  });

  it.each([
    { ...rollback, incident: undefined },
    { ...rollback, incident_id: 'other-incident' },
    { ...rollback, incident: { ...rollback.incident, incident_id: 'other-incident' } },
    { ...rollback, incident: { ...rollback.incident, can_rollback: true } },
    { ...rollback, incident: { ...rollback.incident, rollback_token: 'still-active' } },
    { ...rollback, incident: { ...rollback.incident, state: 'remediated' } },
    { ...rollback, status: 'failed' },
  ])('requires a consistent authoritative rollback snapshot', async response => {
    vi.stubGlobal('fetch', vi.fn(async () => ok(response)));
    await expect(connectedWorkbench.rollback(incident)).rejects.toThrow('unexpected response');
  });

  it.each([
    { status: 'no_incidents' }, { status: 'no_incidents', incidents: [incident] },
    { status: 'remediation_executed', incident: { ...incident, state: 'ready_for_execution' }, rollback_ready: true },
    { status: 'remediation_executed', incident, rollback_ready: false },
  ])('rejects malformed incident results', async response => {
    vi.stubGlobal('fetch', vi.fn(async () => ok(response)));
    await expect(connectedWorkbench.correlate()).rejects.toThrow('unexpected response');
  });

  it('supports a real no-incidents response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ok({ status: 'no_incidents', incidents: [] })));
    await expect(connectedWorkbench.correlate()).resolves.toEqual({ status: 'no_incidents', incidents: [] });
  });

  it('does not transmit consumed or missing action tokens', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    await expect(connectedWorkbench.approve(resolved)).rejects.toThrow('no pending approval');
    await expect(connectedWorkbench.rollback({ ...incident, rollback_token: null })).rejects.toThrow('no available rollback');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('routes invoice and onboarding through the API rather than local fabricated counts', async () => {
    const report = { invoice_id: 'INV-1', is_valid: false, arithmetic_valid: false, discrepancy_details: ['Delta $10'], math_delta: -10, action_recommended: 'MANUAL_AUDIT_REQUIRED' };
    const batch = await createDemoWorkbench().onboard();
    const fetchMock = vi.fn().mockResolvedValueOnce(ok(report)).mockResolvedValueOnce(ok(batch));
    vi.stubGlobal('fetch', fetchMock);
    expect(await connectedWorkbench.validate(true)).toEqual(report);
    expect(await connectedWorkbench.onboard()).toEqual(batch);
    expect(fetchMock.mock.calls[0][0]).toMatch(/project3\/validate-invoice$/);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ simulate_discrepancy: true });
    expect(fetchMock.mock.calls[1][0]).toMatch(/project4\/onboard-data$/);
  });
});

describe('explicit local synthetic client', () => {
  it('runs all five examples without fetch and validates one-use state transitions', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const demo = createDemoWorkbench();
    expect((await demo.query('Executive compensation bonus', 'engineering')).allowed).toBe(false);
    expect((await demo.query('Executive compensation bonus', 'hr')).allowed).toBe(true);
    const pending = await demo.ingest('Please refund this invoice');
    expect((await demo.approve(pending)).status).toBe('resolved');
    await expect(demo.approve(pending)).rejects.toThrow('No matching pending');
    expect((await demo.validate(true)).is_valid).toBe(false);
    expect((await demo.validate(false)).is_valid).toBe(true);
    expect((await demo.onboard()).report).toMatchObject({ total_rows: 5, accepted_rows: 2, quarantined_rows: 3 });
    const result = await demo.correlate();
    expect(result.status).toBe('remediation_executed');
    if (result.status !== 'remediation_executed') throw new Error('Expected demo incident');
    expect((await demo.rollback(result.incident)).incident.state).toBe('rolled_back');
    await expect(demo.rollback(result.incident)).rejects.toThrow('No matching available');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('isolates demo records across clients', async () => {
    const ticket = await createDemoWorkbench().ingest('refund');
    await expect(createDemoWorkbench().approve(ticket)).rejects.toThrow('No matching pending');
  });
});

describe('truthful output invariants', () => {
  it.each([
    { ...ticket, content: 'other input' },
    { ...ticket, customer: 'Other customer' },
    { ...ticket, channel: 'email' },
    { ...resolved },
    { ...ticket, status: 'resolving' },
    { ...ticket, state_machine_step: 'action_executed' },
  ])('rejects unrelated or terminal records returned from intake creation', async response => {
    vi.stubGlobal('fetch', vi.fn(async () => ok(response)));
    await expect(connectedWorkbench.ingest('refund')).rejects.toThrow('unexpected response');
  });

  it.each([
    { grounding_score: 1.1 }, { grounding_score: -0.1 }, { blocked_count: -1 }, { blocked_count: 0.2 },
    { query: 'other query' }, { user_role: 'hr' },
  ])('rejects contradictory knowledge response metadata', async changes => {
    vi.stubGlobal('fetch', vi.fn(async () => ok({ ...knowledge, ...changes })));
    await expect(connectedWorkbench.query('architecture', 'engineering')).rejects.toThrow('unexpected response');
  });

  it.each([
    { arithmetic_valid: false }, { discrepancy_details: ['Mismatch'] }, { math_delta: 10 },
  ])('does not label contradictory invoice data as passed', async changes => {
    const report = { invoice_id: 'INV-1', is_valid: true, arithmetic_valid: true, discrepancy_details: [], math_delta: 0, action_recommended: 'AUTO_APPROVE', ...changes };
    vi.stubGlobal('fetch', vi.fn(async () => ok(report)));
    await expect(connectedWorkbench.validate(false)).rejects.toThrow('unexpected response');
  });

  it.each([
    { total_rows: 6 }, { accepted_rows: 5, quarantined_rows: 0 }, { accepted_rows: 2.5 },
    { quarantined_rows: -1 }, { schema_match_pct: 101 }, { schema_match_pct: -1 },
  ])('rejects contradictory onboarding report counts', async changes => {
    const batch = await createDemoWorkbench().onboard();
    vi.stubGlobal('fetch', vi.fn(async () => ok({ ...batch, report: { ...batch.report, ...changes } })));
    await expect(connectedWorkbench.onboard()).rejects.toThrow('unexpected response');
  });

  it.each(['duplicate', 'zero', 'fraction', 'missing_reason', 'changed_validity'])('rejects invalid onboarding row metadata: %s', async scenario => {
    const batch = await createDemoWorkbench().onboard();
    if (scenario === 'duplicate') batch.rows[1].row_number = 1;
    if (scenario === 'zero') batch.rows[1].row_number = 0;
    if (scenario === 'fraction') batch.rows[1].row_number = 1.5;
    if (scenario === 'missing_reason') batch.rows[1].quarantine_reason = '';
    if (scenario === 'changed_validity') batch.rows[1].is_valid = true;
    vi.stubGlobal('fetch', vi.fn(async () => ok(batch)));
    await expect(connectedWorkbench.onboard()).rejects.toThrow('unexpected response');
  });
});
