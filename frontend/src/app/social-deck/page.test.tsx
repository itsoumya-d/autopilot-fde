import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import SocialDeckPage from './page';

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((yes, no) => { resolve = yes; reject = no; });
  // Baseline does not handle rejections; keep the regression run free of unhandled promises.
  void promise.catch(() => {});
  return { promise, resolve, reject };
}
function clipboard(writeText: ReturnType<typeof vi.fn> | undefined) {
  vi.stubGlobal('navigator', { clipboard: writeText ? { writeText } : undefined });
}
function carousel() {
  fireEvent.click(screen.getByRole('button', { name: '3. 5-Slide Master Pitch Deck' }));
  return screen.getAllByRole('button', { name: 'Copy 280-char Tweet' });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('Social Studio clipboard feedback', () => {
  it('only reports success after the clipboard write resolves', async () => {
    const pending = deferred();
    const writeText = vi.fn(() => pending.promise);
    clipboard(writeText);
    render(<SocialDeckPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy Post' }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('UI Generation is NOT just Web Code.'));
    expect(screen.queryByRole('button', { name: 'Copied!' })).toBeNull();
    expect((screen.getByRole('button', { name: 'Copying…' }) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => { pending.resolve(); });
    expect(screen.getByRole('button', { name: 'Copied!' })).toBeTruthy();
  });

  it('shows clipboard rejection and permits a successful retry', async () => {
    const pending = deferred();
    const writeText = vi.fn().mockReturnValueOnce(pending.promise).mockResolvedValueOnce(undefined);
    clipboard(writeText);
    render(<SocialDeckPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy Post' }));
    await act(async () => { pending.reject(new Error('Permission denied')); });
    expect(screen.getByRole('alert').textContent).toContain('Could not copy');
    expect(screen.queryByRole('button', { name: 'Copied!' })).toBeNull();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Copy Post' })); });
    expect(screen.getByRole('button', { name: 'Copied!' })).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('reports an unavailable clipboard without claiming success', async () => {
    clipboard(undefined);
    render(<SocialDeckPage />);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Copy Post' })); });
    expect(screen.getByRole('alert').textContent).toContain('Could not copy');
    expect(screen.queryByRole('button', { name: 'Copied!' })).toBeNull();
  });

  it('gives each successive copy its full confirmation interval', async () => {
    vi.useFakeTimers();
    clipboard(vi.fn().mockResolvedValue(undefined));
    render(<SocialDeckPage />);
    const [first, second] = carousel();
    await act(async () => { fireEvent.click(first); });
    act(() => { vi.advanceTimersByTime(1000); });
    await act(async () => { fireEvent.click(second); });
    act(() => { vi.advanceTimersByTime(1000); });
    expect(second.textContent).toBe('Copied Tweet!');
    expect(first.textContent).toBe('Copy 280-char Tweet');
    act(() => { vi.advanceTimersByTime(1000); });
    expect(second.textContent).toBe('Copy 280-char Tweet');
  });

  it('ignores an older pending clipboard result after a newer copy succeeds', async () => {
    const older = deferred();
    const newer = deferred();
    clipboard(vi.fn().mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise));
    render(<SocialDeckPage />);
    const [first, second] = carousel();
    fireEvent.click(first);
    expect((first as HTMLButtonElement).disabled).toBe(true);
    expect((second as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(second);
    await act(async () => { newer.resolve(); });
    expect(second.textContent).toBe('Copied Tweet!');
    await act(async () => { older.reject(new Error('Late clipboard failure')); });
    expect(second.textContent).toBe('Copied Tweet!');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('does not replace a newer failure with an older successful completion', async () => {
    const older = deferred();
    const newer = deferred();
    clipboard(vi.fn().mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise));
    render(<SocialDeckPage />);
    const [first, second] = carousel();
    fireEvent.click(first);
    expect((first as HTMLButtonElement).disabled).toBe(true);
    expect((second as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(second);
    await act(async () => { newer.reject(new Error('Clipboard denied')); });
    expect(screen.getByRole('alert').textContent).toContain('Could not copy');
    await act(async () => { older.resolve(); });
    expect(screen.getByRole('alert').textContent).toContain('Could not copy');
    expect(screen.queryByRole('button', { name: 'Copied Tweet!' })).toBeNull();
  });

  it('does not start a feedback timer for a clipboard request resolved after unmount', async () => {
    vi.useFakeTimers();
    const pending = deferred();
    clipboard(vi.fn(() => pending.promise));
    const { unmount } = render(<SocialDeckPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy Post' }));
    unmount();
    await act(async () => { pending.resolve(); });
    expect(vi.getTimerCount()).toBe(0);
  });

  it('cleans up the feedback timer on unmount', async () => {
    vi.useFakeTimers();
    clipboard(vi.fn().mockResolvedValue(undefined));
    const { unmount } = render(<SocialDeckPage />);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Copy Post' })); });
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});


describe('Social Studio preview boundaries', () => {
  it('retains all three layouts and copies short posts with their example disclosures', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    clipboard(writeText);
    render(<SocialDeckPage />);
    expect(screen.getByRole('region', { name: 'Infographic preview' })).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: '2. AutoPilot FDE: 4-Panel Editorial' }));
    expect(screen.getByRole('region', { name: 'Four-panel editorial preview' })).toBeDefined();
    expect(screen.getByText(/No current benchmark, customer outcome/)).toBeDefined();
    const buttons = carousel();
    expect(buttons).toHaveLength(5);
    for (const button of buttons) await act(async () => { fireEvent.click(button); });
    expect(writeText).toHaveBeenCalledTimes(5);
    for (const [text] of writeText.mock.calls) {
      expect(text.length).toBeLessThanOrEqual(280);
      expect(text).not.toContain('your-username');
    }
    expect(writeText.mock.calls[0][0]).toContain('static example');
    expect(writeText.mock.calls[2][0]).toContain('illustrative example data');
    expect(writeText.mock.calls[4][0]).toContain('not a current verified CI result');
  });
});
