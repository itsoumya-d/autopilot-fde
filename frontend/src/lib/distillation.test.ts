import { afterEach, describe, expect, it, vi } from 'vitest';
import { distillationApi, type CreateDistillationJob } from './distillation';

const payload: CreateDistillationJob = {
  teacher_model: 'gpt-4o', student_model: 'Qwen/Qwen2.5-7B-Instruct',
  attest_internal_use_only: true, commercial_foundation_competition_waiver: true,
  allow_synthetic_samples: false,
};
const job = {
  ...payload, id: 'DISTILL-TEST', status: 'completed', sample_count: 2,
  pii_scrubbed_count: 1, output_dir: 'runs/distillation/DISTILL-TEST',
  generated_recipe_files: ['runs/distillation/DISTILL-TEST/dataset_alpaca.jsonl'],
  used_synthetic_samples: false,
};
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules(); });

describe('distillation API boundary', () => {
  it('uses the configured API base and sends only the requested text', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://localhost:9123/api/');
    vi.resetModules();
    const { distillationApi: configured } = await import('./distillation');
    const fetch = vi.fn(async () => response({ original: 'hi test@example.org', scrubbed: 'hi [REDACTED_EMAIL]', redactions_count: 1 }));
    vi.stubGlobal('fetch', fetch);
    const controller = new AbortController();
    await expect(configured.scrubPreview('hi test@example.org', controller.signal)).resolves.toMatchObject({ redactions_count: 1 });
    expect(fetch).toHaveBeenCalledWith('http://localhost:9123/api/distillation/scrub-preview', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ text: 'hi test@example.org' }), signal: controller.signal,
    }));
  });

  it('preserves a network failure instead of fabricating scrubbed text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(distillationApi.scrubPreview('new input')).rejects.toThrow('Failed to fetch');
  });

  it('rejects a non-JSON success response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>wrong API origin</html>')));
    await expect(distillationApi.scrubPreview('new input')).rejects.toThrow(/JSON/i);
  });

  it.each([
    null,
    { detail: 'error disguised as success' },
    { original: 'wrong input', scrubbed: 'wrong output', redactions_count: 1 },
    { original: 'new input', scrubbed: 42, redactions_count: 1 },
    { original: 'new input', scrubbed: 'new input', redactions_count: -1 },
  ])('rejects malformed or mismatched scrub responses: %j', async (data) => {
    vi.stubGlobal('fetch', vi.fn(async () => response(data)));
    await expect(distillationApi.scrubPreview('new input')).rejects.toThrow('invalid sanitizer result');
  });

  it('surfaces rejected attestations without returning a job', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Both usage attestations are required.' }, 400)));
    await expect(distillationApi.createJob({ ...payload, attest_internal_use_only: false })).rejects.toThrow('Both usage attestations');
  });

  it('sends explicit synthetic choice and validates the completed backend job', async () => {
    const fetch = vi.fn(async () => response(job));
    vi.stubGlobal('fetch', fetch);
    await expect(distillationApi.createJob(payload)).resolves.toEqual(job);
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/distillation\/jobs$/), expect.objectContaining({ method: 'POST', body: JSON.stringify(payload) }));
  });

  it.each([
    { ...job, generated_recipe_files: null },
    { ...job, generated_recipe_files: [] },
    { ...job, generated_recipe_files: [42] },
    { ...job, sample_count: 0 },
    { ...job, sample_count: 0.5 },
    { ...job, status: 'trained' },
    { ...job, student_model: 'unexpected model' },
    { ...job, used_synthetic_samples: undefined },
    { ...job, used_synthetic_samples: true },
  ])('rejects malformed or unrequested generation results: %j', async (data) => {
    vi.stubGlobal('fetch', vi.fn(async () => response(data)));
    await expect(distillationApi.createJob(payload)).rejects.toThrow('Completion could not be verified');
  });

  it('accepts explicitly authorized synthetic sample provenance', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ ...job, used_synthetic_samples: true })));
    await expect(distillationApi.createJob({ ...payload, allow_synthetic_samples: true })).resolves.toMatchObject({ used_synthetic_samples: true });
  });
});
