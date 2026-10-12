import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Sidebar from './Sidebar';

vi.mock('next/navigation', () => ({ usePathname: () => '/channels' }));
afterEach(cleanup);

const labels = ['Dashboard', '5 Archetypes', 'Distill Studio', 'Social Studio', 'Motion Showcase', 'Channels', 'Processes', 'Object Lens', 'Scores', 'Deploy', 'Performance'];

describe('Sidebar navigation accessibility', () => {
  it('names the toggle and preserves every link name after keyboard collapse and expansion', async () => {
    const user = userEvent.setup();
    render(<Sidebar />);
    const toggle = screen.getByRole('button', { name: 'Collapse sidebar' });
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    await user.tab();
    expect(document.activeElement).toBe(toggle);
    await user.keyboard('{Enter}');
    expect(screen.getByRole('button', { name: 'Expand sidebar' }).getAttribute('aria-expanded')).toBe('false');
    for (const label of labels) expect(screen.getByRole('link', { name: label })).toBeTruthy();
    await user.keyboard(' ');
    expect(screen.getByRole('button', { name: 'Collapse sidebar' }).getAttribute('aria-expanded')).toBe('true');
    for (const label of labels) expect(screen.getByRole('link', { name: label })).toBeTruthy();
  });

  it('identifies the current page in both expanded and collapsed navigation', async () => {
    render(<Sidebar />);
    expect(screen.getByRole('link', { name: 'Channels' }).getAttribute('aria-current')).toBe('page');
    expect(screen.getByRole('link', { name: 'Dashboard' }).hasAttribute('aria-current')).toBe(false);
    await userEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('link', { name: 'Channels' }).getAttribute('aria-current')).toBe('page');
  });
});
