import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import Home from './page';

const summary = { processes_discovered: 7, average_opportunity_score: 64, evidence_backed_hours: 123, active_agents: 3, pending_approvals: 2 };
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Workspace overview', () => {
  it('shows unknown metrics while the actual summary loads', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    render(<Home />);
    expect(screen.getByRole('status').textContent).toContain('Loading workspace summary');
    expect(screen.getAllByText('—')).toHaveLength(4);
    expect(screen.queryByText('0')).toBeNull();
    expect(screen.getByText('Approvals unavailable')).toBeDefined();
  });

  it('renders backend values and an actual pending approval count', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response(summary)));
    render(<Home />);
    expect(await screen.findByText('2 pending approvals')).toBeDefined();
    for (const value of ['7', '64', '123', '3']) expect(screen.getByText(value)).toBeDefined();
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.getByRole('link', { name: 'Inspect processes' }).getAttribute('href')).toBe('/processes');
    expect(screen.getByRole('link', { name: 'View sources' }).getAttribute('href')).toBe('/channels');
    expect(screen.getByRole('link', { name: 'Review pilots' }).getAttribute('href')).toBe('/deploy');
  });

  it('does not turn an unavailable backend into confirmed zero metrics', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Summary unavailable' }, 503)));
    render(<Home />);
    expect((await screen.findByRole('alert')).textContent).toContain('Summary unavailable');
    expect(screen.getAllByText('—')).toHaveLength(4);
    expect(screen.queryByText('0')).toBeNull();
    expect(screen.queryByText('0 pending approvals')).toBeNull();
  });

  it.each(['success', 'failure'])('ignores an obsolete StrictMode summary response (%s)', async result => {
    let resolve!: (value: Response) => void;
    let reject!: (reason: Error) => void;
    const pending = new Promise<Response>((yes, no) => { resolve = yes; reject = no; });
    vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(pending).mockResolvedValueOnce(response(summary)));
    render(<StrictMode><Home /></StrictMode>);
    await screen.findByText('2 pending approvals');
    await act(async () => {
      if (result === 'failure') reject(new Error('Obsolete summary failure'));
      else resolve(response({ ...summary, pending_approvals: 99 }));
    });
    expect(screen.getByText('2 pending approvals')).toBeDefined();
    expect(screen.queryByText('99 pending approvals')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
