import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

const ok = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200 });

const fail = (status: number, detail: string) =>
  new Response(JSON.stringify({ detail }), { status });

describe('api request layer', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('returns parsed JSON on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ok({ status: 'ok' })));
    await expect(api.dashboard()).resolves.toEqual({ status: 'ok' });
  });

  it('throws the backend detail message on error responses', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => fail(401, 'Missing or invalid X-API-Key header.')));
    await expect(api.dashboard()).rejects.toThrow('Missing or invalid X-API-Key header.');
  });

  it('falls back to a generic message when the body is not JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('server exploded', { status: 500 })),
    );
    await expect(api.processes()).rejects.toThrow('Request failed');
  });

  it('sends JSON bodies with the right method for mutations', async () => {
    const fetchMock = vi.fn(
      async (_url: unknown, _init?: RequestInit) => ok({ id: 'agent-1' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await api.deploy({
      process_id: 'p1',
      name: 'Copilot',
      config: {
        traffic_percentage: 100,
        enabled_steps: ['Step A'],
        approval_required: true,
        mode: 'draft',
        confidence_threshold: 0.8,
      },
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/agents\/deploy$/);
    expect(init?.method).toBe('POST');
    const headers = init?.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(String(init?.body ?? '{}'))).toMatchObject({ process_id: 'p1' });
  });

  it('maps delete to the right path', async () => {
    const fetchMock = vi.fn(
      async (_url: unknown, _init?: RequestInit) => ok({ message: 'removed' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await api.removeAgent('agent-9');
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/agents\/agent-9$/);
    expect(init?.method).toBe('DELETE');
  });
});
