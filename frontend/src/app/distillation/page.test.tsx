import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DistillationPage from './page';

const job = {
  id: 'DISTILL-REAL', teacher_model: 'gpt-4o', student_model: 'Qwen/Qwen2.5-7B-Instruct',
  status: 'completed', sample_count: 2, pii_scrubbed_count: 1,
  output_dir: 'runs/distillation/DISTILL-REAL',
  generated_recipe_files: ['runs/distillation/DISTILL-REAL/dataset_alpaca.jsonl', 'runs/distillation/DISTILL-REAL/train_unsloth.py'],
  used_synthetic_samples: false,
};
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const generateButton = () => screen.getByRole('button', { name: /Compile Dataset/ }) as HTMLButtonElement;
async function attest() {
  await userEvent.click(screen.getByRole('checkbox', { name: /I intend/ }));
  await userEvent.click(screen.getByRole('checkbox', { name: /I will not/ }));
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Distillation Studio', () => {
  it('starts with unchecked attestations and explicit demo opt-in', () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    render(<DistillationPage />);
    expect(screen.getAllByRole('checkbox').every(input => !(input as HTMLInputElement).checked)).toBe(true);
    expect(generateButton().disabled).toBe(true);
    fireEvent.click(generateButton());
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByText(/does not call a teacher model/)).toBeDefined();
    expect(screen.getByText(/not live model prices/)).toBeDefined();
  });

  it('shows additional cost rather than clamping negative savings to zero', () => {
    render(<DistillationPage />);
    fireEvent.change(screen.getByRole('slider', { name: 'Monthly volume' }), { target: { value: '10000' } });
    expect(screen.getByRole('heading', { name: /\$540 \/ year additional cost/ })).toBeDefined();
  });

  it('shows backend scrubbed text for the exact entered input', async () => {
    const fetch = vi.fn(async () => response({ original: 'Email bob@example.org', scrubbed: 'Email [REDACTED_EMAIL]', redactions_count: 1 }));
    vi.stubGlobal('fetch', fetch);
    render(<DistillationPage />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Email bob@example.org' } });
    await userEvent.click(screen.getByRole('button', { name: 'Test PII Sanitizer' }));
    expect(await screen.findByText('Email [REDACTED_EMAIL]')).toBeDefined();
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/distillation\/scrub-preview$/), expect.objectContaining({ body: JSON.stringify({ text: 'Email bob@example.org' }) }));
  });

  it('surfaces a scrub network failure without fake output and allows retry', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error('Backend unavailable')).mockResolvedValueOnce(response({ original: 'fresh input', scrubbed: 'fresh input', redactions_count: 0 }));
    vi.stubGlobal('fetch', fetch);
    render(<DistillationPage />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'fresh input' } });
    await userEvent.click(screen.getByRole('button', { name: 'Test PII Sanitizer' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Backend unavailable');
    expect(screen.queryByText(/Backend preview/)).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Test PII Sanitizer' }));
    expect(await screen.findByText(/0 pattern matches/)).toBeDefined();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('rejects malformed preview JSON without showing it as successful', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ scrubbed: 'made up' })));
    render(<DistillationPage />);
    await userEvent.click(screen.getByRole('button', { name: 'Test PII Sanitizer' }));
    expect((await screen.findByRole('alert')).textContent).toContain('invalid sanitizer result');
    expect(screen.queryByText('made up')).toBeNull();
  });

  it('prevents duplicate preview requests and ignores stale success after input changes', async () => {
    const oldRequest = deferred<Response>();
    const freshRequest = deferred<Response>();
    const fetch = vi.fn().mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(freshRequest.promise);
    vi.stubGlobal('fetch', fetch);
    render(<DistillationPage />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'old input' } });
    const button = screen.getByRole('button', { name: 'Test PII Sanitizer' });
    act(() => { fireEvent.click(button); fireEvent.click(button); });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect((screen.getByRole('button', { name: 'Checking redactions…' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'fresh input' } });
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Test PII Sanitizer' }));
    await act(async () => { freshRequest.resolve(response({ original: 'fresh input', scrubbed: 'fresh output', redactions_count: 0 })); });
    expect(await screen.findByText('fresh output')).toBeDefined();
    await act(async () => { oldRequest.resolve(response({ original: 'old input', scrubbed: 'stale output', redactions_count: 0 })); });
    expect(screen.queryByText('stale output')).toBeNull();
    expect(screen.getByText('fresh output')).toBeDefined();
  });

  it('ignores a stale error after the input changes', async () => {
    const pending = deferred<Response>();
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pending.promise));
    render(<DistillationPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Test PII Sanitizer' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'different input' } });
    await act(async () => { pending.reject(new Error('stale error')); });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('shows backend-rejected attestations without artifacts', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Both usage attestations are required.' }, 400)));
    render(<DistillationPage />);
    await attest();
    await userEvent.click(generateButton());
    expect((await screen.findByRole('alert')).textContent).toContain('Both usage attestations');
    expect(screen.queryByRole('region', { name: 'Generation result' })).toBeNull();
    expect(generateButton().disabled).toBe(false);
  });

  it.each([
    ['network failure', () => Promise.reject(new Error('Backend unreachable')), 'Backend unreachable'],
    ['non-JSON', async () => new Response('<html>error</html>'), 'JSON'],
    ['malformed result', async () => response({ status: 'completed' }), 'Completion could not be verified'],
    ['failed job', async () => response({ ...job, status: 'failed', generated_recipe_files: [] }), 'Recipe generation failed'],
  ])('does not claim success for %s', async (_label, fetch, message) => {
    vi.stubGlobal('fetch', vi.fn(fetch));
    render(<DistillationPage />);
    await attest();
    await userEvent.click(generateButton());
    expect((await screen.findByRole('alert')).textContent).toContain(message);
    expect(screen.queryByText(/Dataset and recipes generated/)).toBeNull();
  });

  it('prevents repeated generation and keeps the requested configuration stable until completion', async () => {
    const pending = deferred<Response>();
    const fetch = vi.fn().mockReturnValue(pending.promise);
    vi.stubGlobal('fetch', fetch);
    render(<DistillationPage />);
    await attest();
    const button = generateButton();
    act(() => { fireEvent.click(button); fireEvent.click(button); });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Waiting for the backend/).getAttribute('role')).toBe('status');
    expect((screen.getByRole('combobox', { name: /Teacher model/ }).closest('fieldset') as HTMLFieldSetElement).disabled).toBe(true);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({ allow_synthetic_samples: false, attest_internal_use_only: true });
    await act(async () => { pending.resolve(response(job)); });
    expect(await screen.findByText(/Dataset and recipes generated: DISTILL-REAL/)).toBeDefined();
    expect(screen.getByText(/No model was trained or deployed/)).toBeDefined();
    expect(screen.getByText(/Source: workspace process evidence/).textContent).toContain('seeded demo');
    expect(screen.getByText(job.generated_recipe_files[0])).toBeDefined();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: /Target student/ }), 'google/gemma-2-9b-it');
    expect(screen.queryByRole('region', { name: 'Generation result' })).toBeNull();
  });

  it('labels explicitly selected synthetic output', async () => {
    const fetch = vi.fn(async () => response({ ...job, used_synthetic_samples: true }));
    vi.stubGlobal('fetch', fetch);
    render(<DistillationPage />);
    await attest();
    await userEvent.click(screen.getByRole('checkbox', { name: /Allow synthetic/ }));
    await userEvent.click(generateButton());
    expect(await screen.findByText(/Synthetic demo dataset: these samples are fabricated/)).toBeDefined();
    expect(fetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ body: expect.stringContaining('"allow_synthetic_samples":true') }));
  });

  it('does not label a pending backend job as completed', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ ...job, status: 'generating_recipe', generated_recipe_files: [] })));
    render(<DistillationPage />);
    await attest();
    await userEvent.click(generateButton());
    expect(await screen.findByText(/Backend generation status: generating recipe/)).toBeDefined();
    expect(screen.queryByText(/Dataset and recipes generated/)).toBeNull();
  });

  it('aborts page-owned requests on unmount and ignores their responses on a fresh page', async () => {
    const pending = deferred<Response>();
    const fetch = vi.fn().mockReturnValue(pending.promise);
    vi.stubGlobal('fetch', fetch);
    const first = render(<DistillationPage />);
    await attest();
    fireEvent.click(generateButton());
    first.unmount();
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    render(<DistillationPage />);
    await act(async () => { pending.resolve(response(job)); });
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Generation result' })).toBeNull());
  });
});
