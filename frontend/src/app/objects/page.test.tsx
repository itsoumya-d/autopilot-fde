import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Object Lens page', () => {
  it('renders summaries and filters by type chip', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(log), { status: 200 })));
    render(<Objects />);
    expect(await screen.findByText('Object Lens')).toBeDefined();
    expect(await screen.findByText('vendor:acme')).toBeDefined();

    await userEvent.click(screen.getByRole('button', { name: /^case\s*1$/ }));
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

  it.each(['{Enter}', ' '])('selects an object with the keyboard (%s)', async key => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(log), { status: 200 })));
    const user = userEvent.setup();
    render(<Objects />);
    const object = await screen.findByRole('button', { name: 'vendor:acme' });
    object.focus();
    await user.keyboard(key);
    expect(await screen.findByText('Invoice received')).toBeDefined();
    expect(object.getAttribute('aria-pressed')).toBe('true');
  });

  it('lets keyboard users focus the named table scroll area before its object controls', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(log), { status: 200 })));
    const user = userEvent.setup();
    render(<Objects />);
    const cases = await screen.findByRole('button', { name: /^case\s*1$/ });
    cases.focus();
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('region', { name: 'Objects table' }));
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'vendor:acme' }));
    await user.keyboard('{Enter}');
    expect(await screen.findByText('Invoice received')).toBeDefined();
  });

  it('exposes the active type filter', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(log), { status: 200 })));
    const user = userEvent.setup();
    render(<Objects />);
    const all = await screen.findByRole('button', { name: /all/ });
    expect(all.getAttribute('aria-pressed')).toBe('true');
    const cases = screen.getByRole('button', { name: /^case\s*1$/ });
    await user.click(cases);
    expect(cases.getAttribute('aria-pressed')).toBe('true');
    expect(all.getAttribute('aria-pressed')).toBe('false');
  });

  it('announces loading while awaiting an object log', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    render(<Objects />);
    expect(screen.getByRole('status').textContent).toContain('Loading object log');
  });

  it.each(['success', 'failure'])('ignores an obsolete StrictMode request (%s)', async result => {
    let resolve!: (value: Response) => void;
    let reject!: (reason: Error) => void;
    const pending = new Promise<Response>((yes, no) => { resolve = yes; reject = no; });
    vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(pending).mockResolvedValueOnce(new Response(JSON.stringify(log), { status: 200 })));
    render(<StrictMode><Objects /></StrictMode>);
    await screen.findByText('vendor:acme');
    await act(async () => {
      if (result === 'failure') reject(new Error('Obsolete object log failure'));
      else resolve(new Response(JSON.stringify({ ...log, objects: [], events: [] }), { status: 200 }));
    });
    expect(screen.queryByText('Obsolete object log failure')).toBeNull();
    expect(screen.getByText('vendor:acme')).toBeDefined();
  });

  it('surfaces backend errors instead of a blank page', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'boom' }), { status: 500 })));
    render(<Objects />);
    expect((await screen.findByRole('alert')).textContent).toContain('boom');
  });
});
