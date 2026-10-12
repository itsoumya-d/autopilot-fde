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
      const card = within(heading.parentElement!);
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
    expect(within(first.parentElement!).getByText('Read-only')).toBeTruthy();
    expect(within(second.parentElement!).getByText('Not read-only')).toBeTruthy();
  });

  it('announces request errors and stops loading without presenting an empty success state', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'Channel service unavailable' }, 503)));
    render(<Channels />);
    expect((await screen.findByRole('alert')).textContent).toContain('Channel service unavailable');
    expect(screen.queryByText('Loading channel information…')).toBeNull();
    expect(screen.queryByText('No observation sources connected yet.')).toBeNull();
  });
});
