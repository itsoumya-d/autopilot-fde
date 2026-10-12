import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, within } from '@testing-library/react';
import Channels from './page';

const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Observation sources states', () => {
  it('finishes loading when the backend returns an empty channel list', async () => {
    let resolve!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(yes => { resolve = yes; })));
    render(<Channels />);
    expect(screen.getByText('Loading channel information…')).toBeTruthy();
    await act(async () => { resolve(response([])); });
    expect(await screen.findByText('No observation sources connected yet.')).toBeTruthy();
    expect(screen.queryByText('Loading channel information…')).toBeNull();
  });

  it('renders the backend active, inactive, and error statuses without inventing permission information', async () => {
    // ChannelPublic declares these statuses and does not send a read_only field.
    const channels = ['active', 'inactive', 'error'].map((status, index) => ({
      id: `channel-${index}`, name: `${status} source`, type: 'slack', status,
      message_count: index, created_at: '2026-01-01T00:00:00Z',
    }));
    vi.stubGlobal('fetch', vi.fn(async () => response(channels)));
    render(<Channels />);
    for (const [index, status] of ['Active', 'Inactive', 'Error'].entries()) {
      const heading = await screen.findByRole('heading', { name: channels[index].name });
      const card = within(heading.closest('article')!);
      expect(card.getByText(status)).toBeTruthy();
      expect(card.getByText('Not reported')).toBeTruthy();
      expect(card.queryByText('Read-only active')).toBeNull();
    }
  });

  it('uses explicitly reported read-only and non-read-only scope values', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response([
      { id: 'readonly', type: 'slack', name: 'Read-only source', status: 'active', message_count: 2, read_only: true },
      { id: 'writable', type: 'email', name: 'Other source', status: 'inactive', message_count: 0, read_only: false },
    ])));
    render(<Channels />);
    const first = await screen.findByRole('heading', { name: 'Read-only source' });
    const second = screen.getByRole('heading', { name: 'Other source' });
    expect(within(first.closest('article')!).getByText('Read-only')).toBeTruthy();
    expect(within(second.closest('article')!).getByText('Not read-only')).toBeTruthy();
  });

  it('reports each service from its API type instead of labeling every source as Slack', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response([
      { id: 'email-1', type: 'email', name: 'Support inbox', status: 'active', message_count: 12 },
      { id: 'calls-1', type: 'call', name: 'Call evidence', status: 'inactive', message_count: 3 },
    ])));
    render(<Channels />);
    const email = await screen.findByRole('article', { name: 'Support inbox' });
    expect(within(email).getByText('Email')).toBeTruthy();
    expect(within(email).getByText('12')).toBeTruthy();
    expect(within(email).getByText('email-1')).toBeTruthy();
    expect(within(email).queryByText('Slack thread')).toBeNull();
    expect(within(screen.getByRole('article', { name: 'Call evidence' })).getByText('Call')).toBeTruthy();
  });

  it('announces request errors and stops loading without presenting an empty success state', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Channel service unavailable' }, 503)));
    render(<Channels />);
    expect((await screen.findByRole('alert')).textContent).toContain('Channel service unavailable');
    expect(screen.queryByText('Loading channel information…')).toBeNull();
    expect(screen.queryByText('No observation sources connected yet.')).toBeNull();
  });
});
