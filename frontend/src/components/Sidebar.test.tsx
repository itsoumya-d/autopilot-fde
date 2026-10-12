import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Sidebar from './Sidebar';

vi.mock('next/navigation', () => ({ usePathname: () => '/channels' }));
afterEach(cleanup);
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
});
const destinations = [
  ['Overview', '/'], ['Sources', '/channels'], ['Workflows', '/processes'], ['Object Lens', '/objects'], ['Opportunities', '/scores'],
  ['Pilots', '/deploy'], ['Performance', '/performance'], ['Workflow Lab', '/archetypes'], ['Model Recipes', '/distillation'], ['Simulation', '/showcase'], ['Social Studio', '/social-deck'],
];

describe('Sidebar navigation accessibility', () => {
  it('names the toggle and preserves every link after keyboard collapse and expansion', async () => {
    const user = userEvent.setup();
    render(<Sidebar />);
    const toggle = screen.getByRole('button', { name: 'Collapse sidebar' });
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    toggle.focus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('button', { name: 'Expand sidebar' }).getAttribute('aria-expanded')).toBe('false');
    const navigation = within(screen.getByRole('navigation', { name: 'Primary navigation' }));
    for (const [label] of destinations) expect(navigation.getByRole('link', { name: label })).toBeTruthy();
    await user.keyboard(' ');
    expect(screen.getByRole('button', { name: 'Collapse sidebar' }).getAttribute('aria-expanded')).toBe('true');
    for (const [label] of destinations) expect(navigation.getByRole('link', { name: label })).toBeTruthy();
  });
  it('keeps every grouped destination in keyboard order in both desktop modes', async () => {
    const user = userEvent.setup(); render(<Sidebar />);
    const toggle = screen.getByRole('button', { name: 'Collapse sidebar' });
    const nav = within(screen.getByRole('navigation', { name: 'Primary navigation' }));
    for (const collapsed of [false, true]) {
      if (collapsed) await user.click(toggle);
      toggle.focus();
      for (const [label, href] of destinations) {
        await user.tab(); const link = nav.getByRole('link', { name: label });
        expect(document.activeElement).toBe(link); expect(link.getAttribute('href')).toBe(href);
      }
    }
  });
  it('identifies the current page when expanded and collapsed', async () => {
    render(<Sidebar />);
    const nav = within(screen.getByRole('navigation', { name: 'Primary navigation' }));
    expect(nav.getByRole('link', { name: 'Sources' }).getAttribute('aria-current')).toBe('page');
    expect(nav.getByRole('link', { name: 'Overview' }).hasAttribute('aria-current')).toBe(false);
    await userEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
    expect(nav.getByRole('link', { name: 'Sources' }).getAttribute('aria-current')).toBe('page');
  });
  it('opens a named native modal and restores focus after cancel, backdrop, and navigation', async () => {
    render(<Sidebar />);
    const menu = screen.getByRole('button', { name: 'Open navigation' });
    for (const action of ['cancel', 'backdrop', 'link', 'close']) {
      await userEvent.click(menu);
      const dialog = screen.getByRole('dialog', { name: 'Workspace navigation' });
      expect(menu.getAttribute('aria-expanded')).toBe('true');
      expect(within(dialog).getAllByRole('link')).toHaveLength(11);
      if (action === 'cancel') fireEvent(dialog, new Event('cancel', { cancelable: true }));
      else if (action === 'backdrop') fireEvent.click(dialog);
      else if (action === 'link') fireEvent.click(within(dialog).getByRole('link', { name: 'Sources' }));
      else fireEvent.click(within(dialog).getByRole('button', { name: 'Close navigation' }));
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(menu.getAttribute('aria-expanded')).toBe('false');
      expect(document.activeElement).toBe(menu);
    }
  });
});
