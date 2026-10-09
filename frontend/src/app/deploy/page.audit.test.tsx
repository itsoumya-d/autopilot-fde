import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Deploy from './page';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('resumes a paused agent through the resume endpoint instead of re-approving it', async () => {
  const paused = { id: 'synthetic-paused', process_id: 'synthetic-process', name: 'Synthetic paused pilot', status: 'paused',
    config: { traffic_percentage: 10, enabled_steps: ['Read context'], approval_required: true, mode: 'draft', confidence_threshold: 0.85 },
    created_at: '2026-01-01T00:00:00Z', metrics: { drafts_created: 0 } };
  const requests: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = new URL(url).pathname;
    requests.push(`${init?.method || 'GET'} ${path}`);
    if (path === '/api/agents/') return new Response(JSON.stringify([paused]), { status: 200 });
    if (path === '/api/processes/' || path === '/api/scores/') return new Response('[]', { status: 200 });
    if (path === '/api/agents/synthetic-paused/approve') return new Response(JSON.stringify({ detail: 'Only a pending_approval agent can be approved (current: paused).' }), { status: 409 });
    if (path === '/api/agents/synthetic-paused/resume') return new Response(JSON.stringify({ ...paused, status: 'running' }), { status: 200 });
    throw new Error(`Unexpected synthetic request ${path}`);
  }));
  render(<Deploy />);
  fireEvent.click(await screen.findByRole('button', { name: /Approve|Resume/ }));
  await waitFor(() => expect(requests).toContain('POST /api/agents/synthetic-paused/resume'));
  expect(requests).not.toContain('POST /api/agents/synthetic-paused/approve');
});
