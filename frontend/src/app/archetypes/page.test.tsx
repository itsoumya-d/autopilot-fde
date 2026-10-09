import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ArchetypesPage from './page';
import type { IntakeTicket, Incident } from '@/lib/workbench';

const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
const fail = (status: number, detail: string) => new Response(JSON.stringify({ detail }), { status });
const ticket: IntakeTicket = {
  id: 'TICK-42', customer: 'Sample customer', content: 'Urgent: need refund of $450 on corporate billing', channel: 'slack',
  priority: 'high', status: 'pending_approval', state_machine_step: 'awaiting_human_approval', requires_approval: true,
  approval_token: 'APP-42', suggested_action: 'Review the refund', assigned_tier: 'tier2',
};
const resolved = { ...ticket, status: 'resolved', state_machine_step: 'action_executed', requires_approval: false, approval_token: null };
const incident: Incident = {
  incident_id: 'INC-42', title: 'Sample latency', severity: 'critical', probable_root_cause: 'Sample pool saturation',
  remediation_action: 'Simulated expansion record', state: 'remediated', can_rollback: true, rollback_token: 'RBK-42',
};
const incidentResult = { status: 'remediation_executed', incident, rollback_ready: true };
const rollbackResult = { incident_id: 'INC-42', status: 'success', action: 'Reversed synthetic state', incident: { ...incident, state: 'rolled_back', can_rollback: false, rollback_token: '' } };
const knowledge = (answer: string, query = 'Engineering architecture microservices', user_role = 'engineering') => ({
  query, user_role, answer, allowed: true, grounding_score: 1, blocked_count: 0, citations: [],
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
const selectTab = (name: RegExp) => fireEvent.click(screen.getByRole('tab', { name }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('archetype workbench', () => {
  it('defaults to connected mode and sends no automatic sample requests', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    expect((screen.getByRole('radio', { name: 'Connected API' }) as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText(/Backend examples use synthetic data and in-memory state/)).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    () => Promise.reject(new TypeError('Failed to fetch')),
    () => Promise.resolve(fail(500, 'Backend unavailable')),
    () => Promise.resolve(new Response('<html>not JSON</html>', { status: 200 })),
    () => Promise.resolve(ok({ detail: 'Invalid result' })),
  ])('shows failures without silently switching to sample success', async response => {
    vi.stubGlobal('fetch', vi.fn(response));
    render(<ArchetypesPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByText('Role filter passed')).toBeNull();
    expect((screen.getByRole('radio', { name: 'Connected API' }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole('button', { name: 'Search' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('runs opt-in synthetic examples with zero network calls', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    fireEvent.click(screen.getByRole('radio', { name: 'Synthetic demo (local)' }));
    expect(screen.getByText(/Synthetic demo selected/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText('The sample architecture uses an event bus between services.')).toBeTruthy();
    selectTab(/Intake-to-Resolution/);
    fireEvent.click(screen.getByRole('button', { name: 'Ingest Ticket' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve Sample Ticket' }));
    expect(await screen.findByText('Local demo confirmed the ticket is resolved.')).toBeTruthy();
    selectTab(/Ops Command Center/);
    fireEvent.click(screen.getByRole('button', { name: 'Run Sample Incident' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Roll Back Sample Incident' }));
    expect(await screen.findByText('Local demo confirmed the synthetic incident was rolled back.')).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('requires an API approval response and suppresses duplicate clicks', async () => {
    const approval = deferred<Response>();
    const fetchMock = vi.fn().mockResolvedValueOnce(ok(ticket)).mockReturnValueOnce(approval.promise);
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    selectTab(/Intake-to-Resolution/);
    fireEvent.click(screen.getByRole('button', { name: 'Ingest Ticket' }));
    const approve = await screen.findByRole('button', { name: 'Approve Sample Ticket' });
    fireEvent.click(approve);
    fireEvent.click(approve);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('API confirmed the ticket is resolved.')).toBeNull();
    expect((screen.getByRole('button', { name: 'Approving…' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText('Sample ticket content') as HTMLTextAreaElement).disabled).toBe(true);
    expect(fetchMock.mock.calls[1][0]).toMatch(/project2\/approve$/);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ ticket_id: 'TICK-42', approval_token: 'APP-42' });
    approval.resolve(ok(resolved));
    expect(await screen.findByText('API confirmed the ticket is resolved.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Approve Sample Ticket' })).toBeNull();
  });

  it('keeps a failed approval pending and lets an explicit retry succeed', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(ok(ticket)).mockResolvedValueOnce(fail(409, 'Stale approval')).mockResolvedValueOnce(ok(resolved));
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    selectTab(/Intake-to-Resolution/);
    fireEvent.click(screen.getByRole('button', { name: 'Ingest Ticket' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve Sample Ticket' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Stale approval');
    expect(screen.queryByText('API confirmed the ticket is resolved.')).toBeNull();
    expect(screen.getByText('pending_approval')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Approve Sample Ticket' }));
    expect(await screen.findByText('API confirmed the ticket is resolved.')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('posts rollback and uses the returned incident state only after confirmation', async () => {
    const rollback = deferred<Response>();
    const fetchMock = vi.fn().mockResolvedValueOnce(ok(incidentResult)).mockReturnValueOnce(rollback.promise);
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    selectTab(/Ops Command Center/);
    fireEvent.click(screen.getByRole('button', { name: 'Run Sample Incident' }));
    const rollbackButton = await screen.findByRole('button', { name: 'Roll Back Sample Incident' });
    fireEvent.click(rollbackButton);
    fireEvent.click(rollbackButton);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Record state: remediated')).toBeTruthy();
    expect(screen.queryByText(/API confirmed the synthetic incident was rolled back/)).toBeNull();
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ incident_id: 'INC-42', rollback_token: 'RBK-42' });
    rollback.resolve(ok(rollbackResult));
    expect(await screen.findByText('API confirmed the synthetic incident was rolled back.')).toBeTruthy();
    expect(screen.getByText('Record state: rolled_back')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Roll Back Sample Incident' })).toBeNull();
  });

  it('does not show rollback success after an HTTP error or malformed snapshot', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(ok(incidentResult)).mockResolvedValueOnce(fail(400, 'Invalid rollback token')).mockResolvedValueOnce(ok({ ...rollbackResult, incident: undefined }));
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    selectTab(/Ops Command Center/);
    fireEvent.click(screen.getByRole('button', { name: 'Run Sample Incident' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Roll Back Sample Incident' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Invalid rollback token');
    fireEvent.click(screen.getByRole('button', { name: 'Roll Back Sample Incident' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('unexpected response'));
    expect(screen.getByText('Record state: remediated')).toBeTruthy();
    expect(screen.queryByText(/API confirmed the synthetic incident was rolled back/)).toBeNull();
  });

  it('ignores an older query completion after an input change and newer request', async () => {
    const old = deferred<Response>();
    const newer = deferred<Response>();
    const fetchMock = vi.fn().mockReturnValueOnce(old.promise).mockReturnValueOnce(newer.promise);
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
    fireEvent.change(screen.getByLabelText('Knowledge query'), { target: { value: 'holiday' } });
    expect(signal.aborted).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    newer.resolve(ok(knowledge('Latest answer', 'holiday')));
    expect(await screen.findByText('Latest answer')).toBeTruthy();
    await act(async () => { old.resolve(ok(knowledge('Stale answer'))); await old.promise; });
    expect(screen.queryByText('Stale answer')).toBeNull();
    expect(screen.getByText('Latest answer')).toBeTruthy();
  });

  it('aborts a request and clears displayed evidence when the simulated role changes', async () => {
    const old = deferred<Response>();
    const fetchMock = vi.fn().mockReturnValueOnce(old.promise);
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    fireEvent.click(screen.getByRole('radio', { name: 'guest' }));
    expect((fetchMock.mock.calls[0][1].signal as AbortSignal).aborted).toBe(true);
    await act(async () => { old.resolve(ok(knowledge('Old engineering result'))); await old.promise; });
    expect(screen.queryByText('Old engineering result')).toBeNull();
    expect((screen.getByRole('button', { name: 'Search' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('discards old requests across tab changes and repeated mode switches', async () => {
    const old = deferred<Response>();
    const fetchMock = vi.fn().mockReturnValueOnce(old.promise);
    vi.stubGlobal('fetch', fetchMock);
    render(<ArchetypesPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    selectTab(/Document Intelligence/);
    expect((fetchMock.mock.calls[0][1].signal as AbortSignal).aborted).toBe(true);
    selectTab(/Knowledge RAG/);
    fireEvent.click(screen.getByRole('radio', { name: 'Synthetic demo (local)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText('The sample architecture uses an event bus between services.')).toBeTruthy();
    fireEvent.click(screen.getByRole('radio', { name: 'Connected API' }));
    fireEvent.click(screen.getByRole('radio', { name: 'Synthetic demo (local)' }));
    await act(async () => { old.resolve(ok(knowledge('Stale API result'))); await old.promise; });
    expect(screen.queryByText('Stale API result')).toBeNull();
    expect(screen.queryByText('The sample architecture uses an event bus between services.')).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('displays invoice discrepancy and row-level quarantine evidence', async () => {
    vi.stubGlobal('fetch', vi.fn());
    render(<ArchetypesPage />);
    fireEvent.click(screen.getByRole('radio', { name: 'Synthetic demo (local)' }));
    selectTab(/Document Intelligence/);
    fireEvent.click(screen.getByRole('checkbox', { name: /Inject a sample/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Run Deterministic Audit' }));
    expect(await screen.findByText('Sample validation failed')).toBeTruthy();
    expect(screen.getByText(/differs from stated total/)).toBeTruthy();
    selectTab(/Data Onboarding/);
    fireEvent.click(screen.getByRole('button', { name: 'Process Sample CSV Batch' }));
    expect(await screen.findByText('Row 3: Missing mandatory customer_id')).toBeTruthy();
    expect(screen.getByText('Row 4: Negative annual spend')).toBeTruthy();
  });

  it('renders no-incidents without offering rollback', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ok({ status: 'no_incidents', incidents: [] })));
    render(<ArchetypesPage />);
    selectTab(/Ops Command Center/);
    fireEvent.click(screen.getByRole('button', { name: 'Run Sample Incident' }));
    expect(await screen.findByText('No incidents eligible for remediation were returned.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Roll Back Sample Incident' })).toBeNull();
  });

  it('supports accessible keyboard tabs and reduced-motion transitions', () => {
    render(<ArchetypesPage />);
    const first = screen.getByRole('tab', { name: /Knowledge RAG/ });
    first.focus();
    fireEvent.keyDown(first, { key: 'ArrowRight' });
    const second = screen.getByRole('tab', { name: /Intake-to-Resolution/ });
    expect(document.activeElement).toBe(second);
    expect(second.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tabpanel').getAttribute('aria-labelledby')).toBe(second.id);
    fireEvent.keyDown(second, { key: 'End' });
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: /Ops Command Center/ }));
    fireEvent.keyDown(document.activeElement!, { key: 'Home' });
    expect(document.activeElement).toBe(first);
    expect(first.className).toContain('motion-reduce:transition-none');
    expect(first.className).toContain('focus-visible:ring-2');
  });
});
