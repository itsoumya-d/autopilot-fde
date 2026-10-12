import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import ProcessNode from './ProcessNode';

// Handles require ReactFlow's store; only the node's score display is under test.
vi.mock('@xyflow/react', () => ({
  Handle: () => null,
  Position: { Top: 'top', Bottom: 'bottom' },
}));
afterEach(cleanup);

describe('ProcessNode opportunity score', () => {
  it('shows an explicit unknown mark for an absent score', () => {
    const { container } = render(<ProcessNode data={{ label: 'Unscored workflow', traces: 3 }} />);
    expect(screen.getByText('Opportunity — · 3 observed cases')).toBeDefined();
    expect(container.firstElementChild?.classList.contains('border-slate-500')).toBe(true);
  });

  it.each([
    [0, 'border-slate-500'],
    [44, 'border-slate-500'],
    [45, 'border-amber-400'],
    [64, 'border-amber-400'],
    [65, 'border-cyan-400'],
    [100, 'border-cyan-400'],
  ] as const)('preserves score %i and its existing color threshold', (score, color) => {
    const { container } = render(<ProcessNode data={{ label: 'Scored workflow', score, traces: 3 }} />);
    expect(screen.getByText(`Opportunity ${score} · 3 observed cases`)).toBeDefined();
    expect(container.firstElementChild?.classList.contains(color)).toBe(true);
  });
});
