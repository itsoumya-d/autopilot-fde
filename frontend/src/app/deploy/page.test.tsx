import React, { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Deploy from './page';
import type { Agent, AgentStatus } from '@/lib/api';

const workflow = { id: 'process-1', name: 'Support triage' };
const score = { process_id: workflow.id, score: 82, recommendation: 'Start with context review.', eligible_steps: ['Read context', 'Draft reply'], blocked_steps: ['Send reply'] };
const config: Agent['config'] = { traffic_percentage: 10, enabled_steps: ['Read context'], approval_required: true, mode: 'draft', confidence_threshold: 0.85 };
const agent = (status: AgentStatus = 'paused', id = 'agent-1'): Agent => ({
  id, process_id: workflow.id, name: `Pilot ${id}`, status, config: { ...config },
  created_at: '2026-01-01T00:00:00Z', metrics: { drafts_created: 2, audit: [{ action: 'deploy' }], approved_by: 'anonymous' },
});
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function setup(options: { agents?: Agent[]; processes?: unknown; scores?: unknown; request?: (path: string, init?: RequestInit) => Promise<Response> | Response | undefined } = {}) {
  const state = { agents: options.agents ?? [agent()], processes: options.processes ?? [workflow], scores: options.scores ?? [score] };
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const path = new URL(url).pathname;
    const custom = options.request?.(path, init);
    if (custom !== undefined) return custom;
    if (path === '/api/processes/') return response(state.processes);
    if (path === '/api/scores/') return response(state.scores);
    if (path === '/api/agents/') return response(state.agents);
    if (path === '/api/agents/deploy') {
      const body = JSON.parse(String(init?.body));
      const created = { ...agent('pending_approval', 'created-1'), ...body };
      state.agents.push(created);
      return response(created, 201);
    }
    const match = path.match(/^\/api\/agents\/([^/]+)(?:\/(approve|pause|resume))?$/);
    if (match) {
      const found = state.agents.find(item => item.id === match[1]);
      if (!found) return response({ detail: 'Agent not found' }, 404);
      if (init?.method === 'DELETE') {
        state.agents = state.agents.filter(item => item.id !== found.id);
        return response({ message: 'Draft agent removed; no external action was performed.' });
      }
      const next = { ...found, status: match[2] === 'pause' ? 'paused' as const : 'running' as const };
      state.agents = state.agents.map(item => item.id === next.id ? next : item);
      return response(next);
    }
    throw new Error(`Unexpected request ${init?.method || 'GET'} ${path}`);
  });
  vi.stubGlobal('fetch', fetch);
  return { state, fetch, mutations: () => fetch.mock.calls.filter(([, init]) => init?.method === 'POST' || init?.method === 'DELETE') };
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const ready = async () => waitFor(() => expect(screen.queryByText('Loading deployment records…')).toBeNull());
const row = (id = 'agent-1') => within(screen.getByRole('group', { name: `Pilot ${id}` }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('deployment lifecycle records', () => {
  it('creates, approves, pauses, resumes, and removes through the configured request client', async () => {
    const { mutations } = setup({ agents: [] });
    render(<Deploy />);
    await ready();
    fireEvent.click(button('Create draft pilot'));
    await screen.findByText('Pilot record created. Pending human approval; no worker was started.');
    await ready();
    expect(screen.getByText('Pending approval')).toBeDefined();
    expect(JSON.parse(String(mutations()[0][1]?.body))).toEqual({ process_id: workflow.id, name: 'Support triage · draft assistant', config });
    fireEvent.click(button('Approve'));
    await screen.findByText('Approval saved. Agent record status: Running.');
    await ready();
    fireEvent.click(button('Pause'));
    await screen.findByText('Pause saved. Agent record status: Paused.');
    await ready();
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
    fireEvent.click(button('Resume'));
    await screen.findByText('Resume saved. Agent record status: Running.');
    await ready();
    fireEvent.click(button('Remove Support triage · draft assistant'));
    await screen.findByText('Agent record removed.');
    await ready();
    expect(screen.getByText('No pilot records have been created.')).toBeDefined();
    expect(mutations().map(([url, init]) => `${init?.method} ${new URL(url).pathname}`)).toEqual([
      'POST /api/agents/deploy', 'POST /api/agents/created-1/approve', 'POST /api/agents/created-1/pause',
      'POST /api/agents/created-1/resume', 'DELETE /api/agents/created-1',
    ]);
  });

  it('labels all backend states and exposes only state-appropriate lifecycle actions', async () => {
    const statuses: AgentStatus[] = ['pending_approval', 'deploying', 'running', 'paused', 'stopped', 'failed'];
    setup({ agents: statuses.map(status => agent(status, status)) });
    render(<Deploy />);
    await ready();
    const labels = ['Pending approval', 'Deploying', 'Running', 'Paused', 'Stopped', 'Failed'];
    statuses.forEach((status, index) => {
      expect(row(status).getByText(labels[index])).toBeDefined();
      const actions = row(status).getAllByRole('button').map(item => item.textContent || item.getAttribute('aria-label'));
      const lifecycle = status === 'pending_approval' ? ['Approve'] : status === 'running' ? ['Pause'] : status === 'paused' ? ['Resume'] : [];
      expect(actions).toEqual([...lifecycle, `Remove Pilot ${status}`]);
    });
    expect(screen.queryByText('Needs approval')).toBeNull();
    expect(screen.getByText(/does not start a hosted worker or route live traffic/)).toBeDefined();
    expect(screen.getByText(/Running does not confirm a live worker/)).toBeDefined();
  });

  it('displays legitimate assisted/autonomous records and keeps unsafe activation disabled', async () => {
    setup({ agents: [
      { ...agent('paused', 'assisted'), config: { ...config, mode: 'assisted' } },
      { ...agent('pending_approval', 'autonomous'), config: { ...config, mode: 'autonomous' } },
      { ...agent('paused', 'no-gate'), config: { ...config, approval_required: false } },
    ] });
    render(<Deploy />);
    await ready();
    expect((row('assisted').getByRole('button', { name: 'Resume' }) as HTMLButtonElement).disabled).toBe(false);
    expect((row('autonomous').getByRole('button', { name: 'Approve' }) as HTMLButtonElement).disabled).toBe(true);
    expect((row('no-gate').getByRole('button', { name: 'Resume' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('labels an empty configured step list as default selection', async () => {
    setup({ agents: [{ ...agent(), config: { ...config, enabled_steps: [] } }] });
    render(<Deploy />);
    await ready();
    expect(row().getByText(/Default step selection/)).toBeDefined();
    expect(screen.queryByText(/No enabled steps/)).toBeNull();
  });

  it.each([401, 409, 422, 500])('announces a rejected resume (%i), keeps Paused, and never claims success', async status => {
    const { mutations } = setup({ request: path => path.endsWith('/resume') ? response({ detail: 'Resume denied by backend' }, status) : undefined });
    render(<Deploy />);
    await ready();
    fireEvent.click(button('Resume'));
    expect((await screen.findByRole('alert')).textContent).toContain('Resume denied by backend');
    expect(screen.getByRole('status').textContent).not.toContain('saved');
    expect(row().getByText('Paused')).toBeDefined();
    expect(button('Resume').disabled).toBe(true);
    fireEvent.click(button('Resume'));
    expect(mutations()).toHaveLength(1);
    fireEvent.click(button('Retry refresh'));
    await ready();
    expect(button('Resume').disabled).toBe(false);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('requires a refresh after an uncertain network result without claiming success', async () => {
    setup({ request: path => path.endsWith('/resume') ? Promise.reject(new Error('Network disconnected')) : undefined });
    render(<Deploy />);
    await ready();
    fireEvent.click(button('Resume'));
    expect((await screen.findByRole('alert')).textContent).toContain('Could not confirm the change: Network disconnected');
    expect(screen.getByRole('status').textContent).not.toContain('saved');
    expect(button('Resume').disabled).toBe(true);
  });

  it.each([
    ['wrong identity', { ...agent('running'), id: 'different-agent' }],
    ['wrong process', { ...agent('running'), process_id: 'different-process' }],
    ['wrong status', agent('paused')],
    ['non-string mode', { ...agent('running'), config: { ...config, mode: ['draft'] } }],
    ['out-of-range confidence', { ...agent('running'), config: { ...config, confidence_threshold: 0.2 } }],
    ['missing config', { ...agent('running'), config: undefined }],
    ['malformed used metric', { ...agent('running'), metrics: { drafts_created: { made_up: true } } }],
    ['null body', null],
  ])('fails closed on a 2xx resume with %s', async (_label, body) => {
    const { fetch } = setup({ request: path => path.endsWith('/resume') ? response(body) : undefined });
    render(<Deploy />);
    await ready();
    fireEvent.click(button('Resume'));
    expect((await screen.findByRole('alert')).textContent).toContain('invalid agent result');
    expect(screen.getByRole('status').textContent).not.toContain('saved');
    expect(row().getByText('Paused')).toBeDefined();
    expect(fetch).toHaveBeenCalledTimes(4); // No success refresh after an invalid result.
  });

  it.each([
    ['Approve', 'pending_approval', { ...config, approval_required: false }],
    ['Approve', 'pending_approval', { ...config, mode: 'autonomous' }],
    ['Resume', 'paused', { ...config, approval_required: false }],
    ['Resume', 'paused', { ...config, mode: 'autonomous' }],
  ] as const)('rejects a successful %s response with unsafe activation configuration (%s, %j)', async (action, status, unsafeConfig) => {
    const { fetch } = setup({ agents: [agent(status)], request: path => path.endsWith(`/${action.toLowerCase()}`) ? response({ ...agent('running'), config: unsafeConfig }) : undefined });
    render(<Deploy />);
    await ready();
    fireEvent.click(button(action));
    expect((await screen.findByRole('alert')).textContent).toContain('activation requires human approval and draft or assisted mode');
    expect(screen.getByRole('status').textContent).not.toContain('saved');
    expect(row().getByText(status === 'paused' ? 'Paused' : 'Pending approval')).toBeDefined();
    expect(button(action).disabled).toBe(true);
    expect(button('Retry refresh')).toBeDefined();
    expect(fetch).toHaveBeenCalledTimes(4);
  });

  it('does not accept malformed successful creation or deletion results', async () => {
    const { state } = setup({ request: (path, init) => path.endsWith('/deploy') ? response({ ...agent('pending_approval', 'new'), name: 'Wrong config' }, 201)
      : init?.method === 'DELETE' ? response({}) : undefined });
    render(<Deploy />);
    await ready();
    fireEvent.click(button('Create draft pilot'));
    expect((await screen.findByRole('alert')).textContent).toContain('invalid pilot configuration');
    expect(screen.queryByText('Wrong config')).toBeNull();
    fireEvent.click(button('Retry refresh'));
    await ready();
    fireEvent.click(button('Remove Pilot agent-1'));
    expect((await screen.findByRole('alert')).textContent).toContain('invalid removal result');
    expect(screen.getByRole('status').textContent).not.toContain('removed');
    expect(row().getByText('Paused')).toBeDefined();
    expect(state.agents).toHaveLength(1);
  });

  it('locks repeated clicks, other rows, creation, configuration, removal, and refresh while a mutation is pending', async () => {
    const pending = deferred<Response>();
    const { mutations, fetch } = setup({ agents: [agent(), agent('running', 'agent-2')], request: path => path.endsWith('/resume') ? pending.promise : undefined });
    render(<Deploy />);
    await ready();
    const resume = button('Resume');
    const pause = button('Pause');
    const remove = button('Remove Pilot agent-2');
    const create = button('Create draft pilot');
    const refresh = button('Refresh records');
    act(() => {
      fireEvent.click(resume); fireEvent.click(resume); fireEvent.click(pause);
      fireEvent.click(remove); fireEvent.click(create); fireEvent.click(refresh);
    });
    expect(mutations()).toHaveLength(1);
    expect(fetch).toHaveBeenCalledTimes(4);
    expect([resume, pause, remove, create, refresh].every(item => item.disabled)).toBe(true);
    expect((screen.getByRole('slider', { name: 'Configured traffic percentage' }) as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole('combobox', { name: 'Evidence-backed workflow' }) as HTMLSelectElement).disabled).toBe(true);
    await act(async () => { pending.resolve(response(agent('running'))); });
    await ready();
  });

  it('locks the same controls when creation is the first mutation', async () => {
    const pending = deferred<Response>();
    const { mutations } = setup({ request: path => path.endsWith('/deploy') ? pending.promise : undefined });
    render(<Deploy />);
    await ready();
    const create = button('Create draft pilot');
    const resume = button('Resume');
    act(() => { fireEvent.click(create); fireEvent.click(create); fireEvent.click(resume); });
    expect(mutations()).toHaveLength(1);
    expect(mutations()[0][0]).toMatch(/\/agents\/deploy$/);
    await act(async () => { pending.resolve(response({ ...agent('pending_approval', 'created'), name: 'Support triage · draft assistant' })); });
  });

  it('distinguishes loading, empty records, and no eligible workflows', async () => {
    const pending = deferred<Response>();
    setup({ processes: [], scores: [], agents: [], request: path => path === '/api/agents/' ? pending.promise : undefined });
    render(<Deploy />);
    expect(screen.getByRole('status').textContent).toContain('Loading deployment records');
    expect(screen.queryByText('No pilot records have been created.')).toBeNull();
    expect(button('Create draft pilot').disabled).toBe(true);
    await act(async () => { pending.resolve(response([])); });
    expect(screen.getByText('No pilot records have been created.')).toBeDefined();
    expect(screen.getByText(/No scored workflows are available/)).toBeDefined();
    expect(screen.queryByText('Loading policy…')).toBeNull();
    expect(button('Create draft pilot').disabled).toBe(true);
  });

  it.each([
    ['no eligible steps', [workflow], [{ ...score, eligible_steps: [] }]],
    ['missing workflow', [], [score]],
  ])('does not permit creation with %s', async (_label, processes, scores) => {
    const { mutations } = setup({ processes, scores });
    render(<Deploy />);
    await ready();
    expect(screen.getByText('No eligible workflow is available for a draft pilot.')).toBeDefined();
    expect(button('Create draft pilot').disabled).toBe(true);
    fireEvent.click(button('Create draft pilot'));
    expect(mutations()).toHaveLength(0);
  });

  it('announces an initial read failure without showing an empty-state success and can retry', async () => {
    let fail = true;
    setup({ request: path => fail && path === '/api/agents/' ? response({ detail: 'Storage unavailable' }, 503) : undefined });
    render(<Deploy />);
    expect((await screen.findByRole('alert')).textContent).toContain('Storage unavailable');
    expect(screen.queryByText('No pilot records have been created.')).toBeNull();
    expect(screen.getByText('Agent records could not be loaded.')).toBeDefined();
    expect(button('Create draft pilot').disabled).toBe(true);
    fail = false;
    fireEvent.click(button('Retry refresh'));
    await ready();
    expect(row().getByText('Paused')).toBeDefined();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it.each([
    ['agent records', '/api/agents/', [{ ...agent(), status: 'unknown' }]],
    ['workflow scores', '/api/scores/', [{ ...score, eligible_steps: null }]],
    ['workflows', '/api/processes/', { data: [workflow] }],
  ])('rejects malformed %s without crashing or allowing a mutation', async (kind, endpoint, body) => {
    setup({ request: path => path === endpoint ? response(body) : undefined });
    render(<Deploy />);
    expect((await screen.findByRole('alert')).textContent).toContain(`invalid ${kind}`);
    expect(button('Create draft pilot').disabled).toBe(true);
    expect(screen.queryByRole('button', { name: 'Resume' })).toBeNull();
  });

  it('reselects only a current eligible workflow after a refresh', async () => {
    const { state } = setup();
    render(<Deploy />);
    await ready();
    state.processes = [{ id: 'process-2', name: 'Fresh process' }];
    state.scores = [{ ...score, process_id: 'process-2' }];
    fireEvent.click(button('Refresh records'));
    await ready();
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('process-2');
    expect(screen.getByRole('option', { name: 'Fresh process (82)' })).toBeDefined();
  });

  it.each(['success', 'failure'])('ignores an older load %s after a newer load completes', async completion => {
    const old = deferred<Response>();
    let calls = 0;
    setup({ request: path => path === '/api/agents/' && calls++ === 0 ? old.promise : undefined });
    render(<Deploy />);
    fireEvent.click(button('Refresh records'));
    await ready();
    expect(row().getByText('Paused')).toBeDefined();
    await act(async () => {
      if (completion === 'success') old.resolve(response([agent('failed', 'stale')]));
      else old.reject(new Error('Old request failed'));
    });
    expect(row().getByText('Paused')).toBeDefined();
    expect(screen.queryByText('Pilot stale')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(button('Resume').disabled).toBe(false);
  });

  it('does not let a stale load overwrite a later confirmed mutation', async () => {
    const old = deferred<Response>();
    let calls = 0;
    setup({ request: path => path === '/api/agents/' && calls++ === 0 ? old.promise : undefined });
    render(<Deploy />);
    fireEvent.click(button('Refresh records'));
    await ready();
    fireEvent.click(button('Resume'));
    await screen.findByText('Resume saved. Agent record status: Running.');
    await ready();
    await act(async () => { old.resolve(response([agent()])); });
    expect(row().getByText('Running')).toBeDefined();
    expect(screen.queryByRole('button', { name: 'Resume' })).toBeNull();
  });

  it.each(['success', 'failure'])('ignores an unmounted mutation %s and never starts a follow-up refresh', async completion => {
    const pending = deferred<Response>();
    const { fetch } = setup({ request: path => path.endsWith('/resume') ? pending.promise : undefined });
    const view = render(<Deploy />);
    await ready();
    fireEvent.click(button('Resume'));
    view.unmount();
    await act(async () => {
      if (completion === 'success') pending.resolve(response(agent('running')));
      else pending.reject(new Error('Disconnected after leaving'));
    });
    expect(fetch).toHaveBeenCalledTimes(4);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('ignores an unmounted initial read and the discarded StrictMode read', async () => {
    const pending = deferred<Response>();
    let calls = 0;
    setup({ request: path => path === '/api/agents/' && calls++ === 0 ? pending.promise : undefined });
    const view = render(<StrictMode><Deploy /></StrictMode>);
    await ready();
    expect(row().getByText('Paused')).toBeDefined();
    await act(async () => { pending.resolve(response([agent('failed', 'discarded')])); });
    expect(screen.queryByText('Pilot discarded')).toBeNull();
    view.unmount();
    const unmounted = deferred<Response>();
    setup({ request: path => path === '/api/agents/' ? unmounted.promise : undefined });
    const next = render(<Deploy />);
    next.unmount();
    await act(async () => { unmounted.reject(new Error('Read failed after leaving')); });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it.each(['resume', 'create', 'remove'])('preserves a confirmed %s when refresh fails and retries only reads', async action => {
    let reads = 0;
    let failRefresh = true;
    const { mutations } = setup({ request: path => {
      if (path === '/api/agents/' && reads++ > 0 && failRefresh) return response({ detail: 'Refresh unavailable' }, 503);
      return undefined;
    } });
    render(<Deploy />);
    await ready();
    fireEvent.click(button(action === 'resume' ? 'Resume' : action === 'create' ? 'Create draft pilot' : 'Remove Pilot agent-1'));
    expect((await screen.findByRole('alert')).textContent).toContain('The change was saved, but records could not be refreshed');
    expect(screen.getByRole('alert').textContent).not.toContain('Could not confirm');
    expect(screen.getByRole('status').textContent).toContain(action === 'resume' ? 'Resume saved' : action === 'create' ? 'Pilot record created' : 'Agent record removed');
    if (action === 'resume') {
      expect(row().getByText('Running')).toBeDefined();
      expect(button('Pause').disabled).toBe(true);
      expect(screen.queryByRole('button', { name: 'Resume' })).toBeNull();
    } else if (action === 'create') {
      expect(screen.getByRole('group', { name: 'Support triage · draft assistant' })).toBeDefined();
    } else {
      expect(screen.queryByRole('group', { name: 'Pilot agent-1' })).toBeNull();
    }
    expect(button('Create draft pilot').disabled).toBe(true);
    expect(mutations()).toHaveLength(1);
    failRefresh = false;
    fireEvent.click(button('Retry refresh'));
    await ready();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(mutations()).toHaveLength(1);
    expect(button('Create draft pilot').disabled).toBe(false);
  });
});
