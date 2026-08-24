import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event'
import Objects from './page';

const log = {
  ocel_version: '2.0-inspired',
  eventTypes: [{ name: 'Invoice received' }],
  events: [
    { id: 'e1', type: 'Invoice received', time: '2026-08-24T10:00:00Z', attributes: [{ name: 'evidence', type: 'string', value: 'vendor Acme $500' }], relationships: [{ objectId: 'vendor:acme', qualifier: 'vendor' }] },
    { id: 'e2', type: 'Invoice reconciled', time: '2026-08-24T10:03:00Z', attributes: [], relationships: [{ objectId: 'vendor:acme', qualifier: 'vendor' }, { objectId: 'case:c1', qualifier: 'case' }] },
  ],
  objectTypes: [{ name: 'vendor' }, { name: 'case' }],
  objects: [
    { id: 'vendor:acme', type: 'vendor', relationships: [{ objectId: 'case:c1', qualifier: 'q' }] },
    { id: 'case:c1', type: 'case', relationships: [] },
  ],
  summaries: { vendor: { objects: 1, events_touching: 2 }, case: { objects: 1, events_touching: 1 } },
};

describe('Object Lens page', () => {
  it('renders summaries and filters by type chip', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(log), { status: 200 })));
    render(<Objects />);
    expect(await screen.findByText('Object Lens')).toBeDefined();
    expect(await screen.findByText('vendor:acme')).toBeDefined();

    await userEvent.click(screen.getByRole('button', { name: /case/ }));
    expect(screen.queryByText('vendor:acme')).toBeNull();
    expect(screen.getByText('case:c1')).toBeDefined();
  });

  it('shows the chronological trace for a clicked object', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(log), { status: 200 })));
    const user = userEvent.setup();
    render(<Objects />);
    await user.click(await screen.findByText('vendor:acme'));
    await waitFor(() => expect(screen.getAllByText('Invoice received').length).toBeGreaterThan(0));
    // e2 touches vendor too, so both appear; ordering is chronological.
    const times = screen.getAllByText(/2026-08-24T10:/).map((n) => n.textContent);
    expect(times).toEqual([...times].sort());
  });

  it('surfaces backend errors instead of a blank page', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'boom' }), { status: 500 })));
    render(<Objects />);
    expect(await screen.findByText(/boom/)).toBeDefined();
  });
});
