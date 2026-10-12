import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Processes from './page';
import type { APScore, Process } from '@/lib/api';

// Isolate page state and API behavior; graph layout/interaction requires browser QA.
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ nodes, onNodeClick, children }: {
    nodes: { id: string; data: { label: string; score?: number } }[];
    onNodeClick: (event: React.MouseEvent, node: { id: string }) => void;
    children: React.ReactNode;
  }) => <div>{nodes.map(node => <button key={node.id} data-score={node.data.score} onClick={event => onNodeClick(event, node)}>Inspect {node.data.label}</button>)}{children}</div>,
  Background: () => null,
  Controls: () => null,
  Handle: () => null,
  Position: { Top: 'top', Bottom: 'bottom' },
}));
const workflow = (id: string): Process => ({
  id, name: `Workflow ${id}`, description: `Evidence for ${id}`,
  activities: [{ id: `${id}-step`, case_id: `${id}-case`, name: `Review ${id}`, category: 'review', actors: ['reviewer'], timestamp: '2026-01-01T00:00:00Z', source_messages: ['message-1'], evidence: `Source ${id}`, confidence: 0.9 }],
  edges: [], metrics: { trace_count: 3, evidence_count: 8, pattern_consistency: 0.9, volume_per_month: 10, avg_completion_minutes: 20 }, evidence_case_ids: [], safety_notes: [],
});
const score = (id: string): APScore => ({ process_id: id, score: 80, value_score: 80, feasibility_score: 80, evidence_confidence: 0.9, factors: {}, recommendation: 'Review evidence', recommended_mode: 'draft_only', eligible_steps: ['Review'], blocked_steps: [], estimated_hours_saved_monthly: 2 });
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function setup(options: { ids?: string[]; request?: (path: string) => Response | Promise<Response> | undefined } = {}) {
  const state = { ids: options.ids ?? ['first', 'second'] };
  const fetch = vi.fn(async (url: string) => {
    const path = new URL(url).pathname;
    const custom = options.request?.(path);
    if (custom !== undefined) return custom;
    if (path === '/api/processes/') return response(state.ids.map(workflow));
    if (path === '/api/scores/') return response(state.ids.map(score));
    if (path === '/api/processes/discover') return response({ message: 'Discovery completed from read-only observations', processes: state.ids.length, activities: 8 });
    throw new Error(`Unexpected request ${path}`);
  });
  vi.stubGlobal('fetch', fetch);
  return { state, fetch };
}
const selected = (id: string) => screen.findByRole('heading', { name: `Workflow ${id}` });
const discover = () => fireEvent.click(screen.getByRole('button', { name: 'Run discovery' }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Process map state', () => {
  it('announces loading without showing an empty selection prompt', () => {
    setup({ request: () => new Promise(() => {}) });
    render(<Processes />);
    expect(screen.getByRole('status').textContent).toContain('Loading workflows');
    expect(screen.queryByText('Select a process to inspect its evidence.')).toBeNull();
  });

  it('selects the first process and allows graph selection', async () => {
    setup();
    render(<Processes />);
    await selected('first');
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Workflow second' }));
    expect(await selected('second')).toBeDefined();
    expect(screen.getByText('“Source second”')).toBeDefined();
  });

  it('selects an available workflow when discovery removes the selection', async () => {
    const { state } = setup();
    render(<Processes />);
    await selected('first');
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Workflow second' }));
    await selected('second');
    state.ids = ['replacement'];
    discover();
    expect(await selected('replacement')).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Workflow second' })).toBeNull();
    expect((await screen.findByRole('status')).textContent).toContain('1 workflows rebuilt from 8 source-linked activities.');
  });

  it('preserves a selection still present after discovery', async () => {
    const { state } = setup();
    render(<Processes />);
    await selected('first');
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Workflow second' }));
    state.ids = ['replacement', 'second'];
    discover();
    await screen.findByText('2 workflows rebuilt from 8 source-linked activities.');
    expect(await selected('second')).toBeDefined();
  });

  it('explains an empty discovery result and clears prior evidence', async () => {
    const { state } = setup();
    render(<Processes />);
    await selected('first');
    state.ids = [];
    discover();
    expect(await screen.findByText('No workflows discovered yet. Run discovery to inspect source-linked evidence.')).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Workflow first' })).toBeNull();
  });

  it('ignores an initial-load error arriving after successful discovery', async () => {
    const initial = deferred<Response>();
    let processReads = 0;
    setup({ ids: ['fresh'], request: path => path === '/api/processes/' && ++processReads === 1 ? initial.promise : undefined });
    render(<Processes />);
    discover();
    await selected('fresh');
    await act(async () => { initial.reject(new Error('Old initial load failed')); });
    expect(screen.queryByText('Old initial load failed')).toBeNull();
    expect(await selected('fresh')).toBeDefined();
  });

  it('ignores initial data arriving after successful discovery', async () => {
    const initial = deferred<Response>();
    let processReads = 0;
    setup({ ids: ['fresh'], request: path => path === '/api/processes/' && ++processReads === 1 ? initial.promise : undefined });
    render(<Processes />);
    discover();
    await selected('fresh');
    await act(async () => { initial.resolve(response([workflow('stale')])); });
    expect(screen.queryByRole('button', { name: 'Inspect Workflow stale' })).toBeNull();
    expect(await selected('fresh')).toBeDefined();
  });

  it('invalidates initial reads as soon as discovery starts', async () => {
    const initial = deferred<Response>();
    const mutation = deferred<Response>();
    let processReads = 0;
    setup({ ids: ['fresh'], request: path => path === '/api/processes/' && ++processReads === 1 ? initial.promise : path === '/api/processes/discover' ? mutation.promise : undefined });
    render(<Processes />);
    discover();
    await act(async () => { initial.resolve(response([workflow('stale')])); });
    expect(screen.queryByRole('button', { name: 'Inspect Workflow stale' })).toBeNull();
    await act(async () => { mutation.resolve(response({ processes: 1, activities: 8 })); });
    expect(await selected('fresh')).toBeDefined();
  });

  it('announces discovery errors and permits retry', async () => {
    let attempts = 0;
    setup({ request: path => path === '/api/processes/discover' && ++attempts === 1 ? response({ detail: 'Discovery unavailable' }, 503) : undefined });
    render(<Processes />);
    await selected('first');
    discover();
    expect((await screen.findByRole('alert')).textContent).toContain('Discovery unavailable');
    expect(await selected('first')).toBeDefined();
    discover();
    await screen.findByText('2 workflows rebuilt from 8 source-linked activities.');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('keeps source evidence visible when the selected workflow has no score yet', async () => {
    setup({ request: path => path === '/api/scores/' ? response([]) : undefined });
    render(<Processes />);
    expect(await selected('first')).toBeDefined();
    expect(screen.getByText('“Source first”')).toBeDefined();
    expect(screen.getByText('Opportunity').parentElement?.textContent).toContain('—');
  });

  it('does not replace a missing graph opportunity score with zero', async () => {
    setup({ request: path => path === '/api/scores/' ? response([]) : undefined });
    render(<Processes />);
    await selected('first');
    expect(screen.getByRole('button', { name: 'Inspect Workflow first' }).getAttribute('data-score')).toBeNull();
  });

  it('passes a genuine zero opportunity score to the graph', async () => {
    setup({ request: path => path === '/api/scores/' ? response([{ ...score('first'), score: 0 }]) : undefined });
    render(<Processes />);
    await selected('first');
    expect(screen.getByRole('button', { name: 'Inspect Workflow first' }).getAttribute('data-score')).toBe('0');
    expect(screen.getByText('Opportunity').parentElement?.textContent).toContain('0');
  });

  it('announces an initial loading error and recovers through discovery', async () => {
    let reads = 0;
    setup({ request: path => path === '/api/processes/' && ++reads === 1 ? response({ detail: 'Initial read failed' }, 500) : undefined });
    render(<Processes />);
    expect((await screen.findByRole('alert')).textContent).toContain('Initial read failed');
    expect(screen.queryByText('No workflows discovered yet. Run discovery to inspect source-linked evidence.')).toBeNull();
    discover();
    expect(await selected('first')).toBeDefined();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('keeps confirmed evidence and exposes a failed discovery refresh', async () => {
    let reads = 0;
    setup({ request: path => path === '/api/processes/' && ++reads === 2 ? response({ detail: 'Refresh unavailable' }, 503) : undefined });
    render(<Processes />);
    await selected('first');
    discover();
    expect((await screen.findByRole('alert')).textContent).toContain('Refresh unavailable');
    expect(await selected('first')).toBeDefined();
    expect(screen.queryByText('2 workflows rebuilt from 8 source-linked activities.')).toBeNull();
    expect((screen.getByRole('button', { name: 'Run discovery' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('does not refresh or update a remounted page for an obsolete discovery', async () => {
    const pending = deferred<Response>();
    const { fetch } = setup({ request: path => path === '/api/processes/discover' ? pending.promise : undefined });
    const first = render(<Processes />);
    await selected('first');
    discover();
    first.unmount();
    render(<Processes />);
    await selected('first');
    await act(async () => { pending.resolve(response({ processes: 99, activities: 99 })); });
    expect(fetch.mock.calls.filter(([url]) => url.endsWith('/processes/'))).toHaveLength(2);
    expect(screen.queryByText('99 workflows rebuilt from 99 source-linked activities.')).toBeNull();
  });

  it('does not send duplicate discovery requests while one is pending', async () => {
    const pending = deferred<Response>();
    const { fetch } = setup({ request: path => path === '/api/processes/discover' ? pending.promise : undefined });
    render(<Processes />);
    await selected('first');
    const button = screen.getByRole('button', { name: 'Run discovery' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(fetch.mock.calls.filter(([url]) => url.endsWith('/discover'))).toHaveLength(1);
    await act(async () => { pending.resolve(response({ processes: 2, activities: 8 })); });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  });
});
