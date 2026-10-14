import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ShowcasePage from './page';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('Illustrative simulation workspace', () => {
  it('preserves the seven keyboard-usable scenario choices and local formulas', async () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    render(<ShowcasePage />);
    const choices = within(screen.getByRole('region', { name: 'Sample workflows' })).getAllByRole('button');
    expect(choices).toHaveLength(7);
    expect(choices[0].getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('62%')).toBeDefined();
    expect(screen.getByText('45 hrs')).toBeDefined();
    choices[1].focus();
    await userEvent.keyboard('{Enter}');
    expect(choices[1].getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('heading', { name: 'Support Escalation Resolution' })).toBeDefined();
    expect(screen.getByText('56%')).toBeDefined();
    expect(screen.getByText('41 hrs')).toBeDefined();
    fireEvent.change(screen.getByRole('slider', { name: 'Confidence Gate Threshold (τ)' }), { target: { value: '95' } });
    expect(screen.getByText('47%')).toBeDefined();
    expect(screen.getByText('49 hrs')).toBeDefined();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('keeps all three views and clearly labels code and historical claims', () => {
    render(<ShowcasePage />);
    fireEvent.click(screen.getByRole('button', { name: 'Example code' }));
    expect(screen.getByRole('heading', { name: 'Example Python LangGraph state machine' })).toBeDefined();
    expect(screen.getByText(/approval node is a placeholder/)).toBeDefined();
    expect(screen.queryByText('Ready for Deployment')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Historical matrix' }));
    expect(screen.getByRole('heading', { name: 'Historical verification examples' })).toBeDefined();
    expect(screen.getByText(/No current run, source artifact, or CI result/)).toBeDefined();
    expect(screen.getByText('142 / 142 Passed')).toBeDefined();
    expect(screen.getByText(/Dates are unverified targets/)).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Simulation inputs' }));
    expect(screen.getByRole('slider')).toBeDefined();
  });

  it('labels the trigger as local and clears its feedback timer on unmount', () => {
    vi.useFakeTimers();
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    const { unmount } = render(<ShowcasePage />);
    const run = screen.getByRole('button', { name: 'Run illustrative simulation' });
    fireEvent.click(run);
    expect((run as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole('status', { name: 'Simulation feedback' }).textContent).toBe('Local example updated.');
    expect(screen.getByText(/does not run 1,000 backend trials/)).toBeDefined();
    act(() => { vi.advanceTimersByTime(600); });
    expect((run as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(run);
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
    expect(fetch).not.toHaveBeenCalled();
  });
});
