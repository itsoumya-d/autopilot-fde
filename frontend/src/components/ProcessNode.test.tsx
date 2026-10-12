import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import ProcessNode from './ProcessNode';

afterEach(cleanup);

describe('ProcessNode opportunity score', () => {
  it('shows an explicit unknown mark for an absent score', () => {
    const { container } = render(<ProcessNode data={{ label: 'Unscored workflow', traces: 3 }} />);
    expect(screen.getByText('Opportunity — · 3 observed cases')).toBeDefined();
    expect(container.firstElementChild?.getAttribute('data-score-tone')).toBe('unknown');
  });

  it.each([[0, 'low'], [44, 'low'], [45, 'medium'], [64, 'medium'], [65, 'high'], [100, 'high']] as const)('preserves score %i and its classification', (score, tone) => {
    const { container } = render(<ProcessNode data={{ label: 'Scored workflow', score, traces: 3 }} />);
    expect(screen.getByText(`Opportunity ${score} · 3 observed cases`)).toBeDefined();
    expect(container.firstElementChild?.getAttribute('data-score-tone')).toBe(tone);
  });

  it('visibly marks the node selected in the evidence inspector', () => {
    const { container, rerender } = render(<ProcessNode data={{ label: 'Selected workflow', traces: 2 }} selected />);
    expect(screen.getByText('In inspector')).toBeTruthy();
    expect(container.firstElementChild?.getAttribute('data-selected')).toBe('true');
    expect(container.firstElementChild?.classList.contains('border-[var(--accent)]')).toBe(true);
    rerender(<ProcessNode data={{ label: 'Selected workflow', traces: 2 }} />);
    expect(screen.queryByText('In inspector')).toBeNull();
    expect(container.firstElementChild?.getAttribute('data-selected')).toBe('false');
  });
});
