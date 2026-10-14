import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Scores from './page';

// Chart geometry is outside jsdom; retain the page's real controls and selected data.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  RadarChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Radar: () => null, PolarGrid: () => null, PolarAngleAxis: () => null,
}));
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const processes = [{ id: 'one', name: 'Support triage' }, { id: 'two', name: 'Invoice review' }];
const scores = processes.map((process, index) => ({
  process_id: process.id, score: 70 + index, value_score: 80, feasibility_score: 70, evidence_confidence: 60,
  factors: { consistency: 80 }, recommendation: `Recommendation for ${process.name}`,
  recommended_mode: 'draft_only', eligible_steps: [`Draft ${process.name}`], blocked_steps: [`Send ${process.name}`],
  estimated_hours_saved_monthly: 20,
}));
function setup(scoreItems: unknown = scores) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => response(new URL(url).pathname === '/api/processes/' ? processes : scoreItems)));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Automation opportunity states', () => {
  it('replaces the explanation loader after a valid empty score response', async () => {
    let resolve!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn((url: string) => new URL(url).pathname === '/api/processes/'
      ? Promise.resolve(response([])) : new Promise<Response>(yes => { resolve = yes; })));
    render(<Scores />);
    expect(screen.getByText('Loading score explanation…')).toBeTruthy();
    await act(async () => { resolve(response([])); });
    expect(await screen.findByText('No scored workflows yet. Run discovery to generate automation scores.')).toBeTruthy();
    expect(screen.queryByText('Loading score explanation…')).toBeNull();
  });

  it('selects workflows with keyboard-operable controls and exposes the selected state', async () => {
    setup();
    const user = userEvent.setup();
    render(<Scores />);
    const first = await screen.findByRole('button', { name: 'Show score for Support triage' });
    const second = screen.getByRole('button', { name: 'Show score for Invoice review' });
    expect(first.getAttribute('aria-pressed')).toBe('true');
    expect(second.getAttribute('aria-pressed')).toBe('false');
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('region', { name: 'Workflow scores table' }));
    await user.tab();
    expect(document.activeElement).toBe(first);
    await user.tab();
    expect(document.activeElement).toBe(second);
    await user.keyboard('{Enter}');
    expect(second.getAttribute('aria-pressed')).toBe('true');
    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(within(screen.getByRole('complementary')).getByText('Recommendation for Invoice review')).toBeTruthy();
    await user.tab({ shift: true });
    await user.keyboard(' ');
    expect(first.getAttribute('aria-pressed')).toBe('true');
    expect(within(screen.getByRole('complementary')).getByText('Recommendation for Support triage')).toBeTruthy();
  });

  it('keeps pointer selection working across a row', async () => {
    setup();
    render(<Scores />);
    const row = (await screen.findByText('Invoice review')).closest('tr')!;
    await userEvent.click(within(row).getByText('71'));
    expect(within(screen.getByRole('complementary')).getByText('Recommendation for Invoice review')).toBeTruthy();
  });

  it.each([
    ['observation_only', 'Observe only'], ['draft_only', 'Draft + review'], ['assisted', 'Assisted'], ['autonomous', 'Autonomous'],
  ])('renders the returned %s recommendation without hard-coding draft mode', async (recommended_mode, label) => {
    setup([{ ...scores[0], recommended_mode }]);
    render(<Scores />);
    const row = (await screen.findByRole('button', { name: 'Show score for Support triage' })).closest('tr')!;
    expect(within(row).getByText(label)).toBeTruthy();
    if (recommended_mode !== 'draft_only') expect(within(row).queryByText('Draft + review')).toBeNull();
  });

  it('provides factor values and eligible/blocked steps as inspector text', async () => {
    setup([scores[0]]);
    render(<Scores />);
    await screen.findByRole('button', { name: 'Show score for Support triage' });
    const inspector = within(screen.getByRole('complementary'));
    expect(inspector.getByText('consistency')).toBeTruthy();
    expect(inspector.getByText('Draft Support triage')).toBeTruthy();
    expect(inspector.getByText('Send Support triage')).toBeTruthy();
    expect(inspector.getByRole('meter').getAttribute('aria-valuenow')).toBe('70');
  });

  it('announces a failed score request without retaining a loading explanation', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Score service unavailable' }, 503)));
    render(<Scores />);
    expect((await screen.findByRole('alert')).textContent).toContain('Score service unavailable');
    expect(screen.queryByText('Loading score explanation…')).toBeNull();
    expect(screen.queryByText('No scored workflows yet. Run discovery to generate automation scores.')).toBeNull();
  });
});
