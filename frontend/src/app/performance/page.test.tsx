import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import Performance from './page';
import type { Agent } from '@/lib/api';

// Chart dimensions/painting are outside jsdom; keep its fixture boundary visible.
vi.mock('recharts', () => ({
  ResponsiveContainer: () => <div data-testid="illustrative-chart" />,
  CartesianGrid: () => null, Legend: () => null, Line: () => null,
  LineChart: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));
function agent(id: string, mode: Agent['config']['mode'] = 'draft'): Agent {
  return { id, process_id: 'process-1', name: `Agent ${id}`, status: 'running', config: { traffic_percentage: 10, enabled_steps: ['Review'], approval_required: true, mode, confidence_threshold: 0.85 }, created_at: '2026-01-01T00:00:00Z', metrics: { drafts_created: 2, external_actions: 0, human_approval_rate: null } };
}
function setup(agents: Agent[]) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(agents), { status: 200 })));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Pilot performance', () => {
  it('reports assisted configuration without claiming draft-only mode', async () => {
    setup([agent('assisted', 'assisted')]);
    render(<Performance />);
    await screen.findByText('Agent assisted');
    expect(screen.getByText('Assisted mode')).toBeDefined();
    expect(screen.queryByText('Draft-only policy')).toBeNull();
    expect(screen.queryByText('Draft-only mode')).toBeNull();
    expect(screen.queryByText('Approved draft agents')).toBeNull();
    expect(screen.getByText('Human approval required')).toBeDefined();
  });

  it('reports autonomous configuration without implying a human approval gate', async () => {
    setup([{ ...agent('autonomous', 'autonomous'), config: { ...agent('autonomous').config, mode: 'autonomous', approval_required: false } }]);
    render(<Performance />);
    await screen.findByText('Agent autonomous');
    expect(screen.getByText('Autonomous mode')).toBeDefined();
    expect(screen.getByText('Human approval not required')).toBeDefined();
    expect(screen.queryByText('All require review')).toBeNull();
  });

  it('does not promise zero external actions when records contain activity', async () => {
    setup([{ ...agent('assisted', 'assisted'), metrics: { drafts_created: 3, external_actions: 2 } }]);
    render(<Performance />);
    await screen.findByText('3 drafts · 2 external actions');
    expect(screen.queryByText(/External actions stay at zero by design/)).toBeNull();
  });

  it('retains the illustrative trend boundary separately from recorded metrics', async () => {
    setup([agent('draft')]);
    render(<Performance />);
    await screen.findByText('Agent draft');
    expect(screen.getByText('Illustrative pilot trend')).toBeDefined();
    expect(screen.getByText(/deterministic sandbox baseline/)).toBeDefined();
    expect(screen.getByTestId('illustrative-chart')).toBeDefined();
    expect(screen.getByText('Draft-only mode')).toBeDefined();
  });

  it('announces loading without reporting an empty agent ledger', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    render(<Performance />);
    expect(screen.getByRole('status').textContent).toContain('Loading agent records');
    expect(screen.queryByText(/No pilot agents yet/)).toBeNull();
  });

  it('announces load errors without reporting no agents', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Metrics offline' }), { status: 503 })));
    render(<Performance />);
    expect((await screen.findByRole('alert')).textContent).toContain('Metrics offline');
    expect(screen.queryByText(/No pilot agents yet/)).toBeNull();
  });

  it('shows a genuine empty state only after successful loading', async () => {
    setup([]);
    render(<Performance />);
    expect(await screen.findByText(/No pilot agents yet/)).toBeDefined();
    await waitFor(() => expect(screen.queryByText('Loading agent records…')).toBeNull());
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it.each(['success', 'failure'])('ignores an obsolete StrictMode request (%s)', async result => {
    let resolve!: (value: Response) => void;
    let reject!: (reason: Error) => void;
    const pending = new Promise<Response>((yes, no) => { resolve = yes; reject = no; });
    vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(pending).mockResolvedValueOnce(new Response(JSON.stringify([agent('current')]), { status: 200 })));
    render(<StrictMode><Performance /></StrictMode>);
    await screen.findByText('Agent current');
    await act(async () => {
      if (result === 'failure') reject(new Error('Obsolete metrics failure'));
      else resolve(new Response(JSON.stringify([agent('obsolete')]), { status: 200 }));
    });
    expect(screen.queryByText('Obsolete metrics failure')).toBeNull();
    expect(screen.queryByText('Agent obsolete')).toBeNull();
    expect(screen.getByText('Agent current')).toBeDefined();
  });

  it('aggregates recorded draft counts and available approval rates', async () => {
    setup([
      { ...agent('one'), metrics: { drafts_created: 7, human_approval_rate: 90 } },
      { ...agent('two', 'assisted'), status: 'paused', metrics: { drafts_created: 3, human_approval_rate: 70 } },
      { ...agent('three'), metrics: {} },
    ]);
    render(<Performance />);
    await screen.findByText('Agent three');
    expect(screen.getByText('10')).toBeDefined();
    expect(screen.getByText('80%')).toBeDefined();
    expect(screen.getByText('Running agent records').parentElement?.textContent).toContain('2');
  });
});
