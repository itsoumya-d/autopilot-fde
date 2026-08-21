import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import APSGauge from './APSGauge';
import StatsCard from './StatsCard';

afterEach(cleanup);

describe('APSGauge', () => {
  it('renders the numeric score and label', () => {
    render(<APSGauge score={74} />);
    expect(screen.getByText('74')).toBeTruthy();
    expect(screen.getByText('APS')).toBeTruthy();
  });

  it('encodes the arc as stroke-dashoffset proportional to the score', () => {
    const { container } = render(<APSGauge score={50} />);
    const arcs = Array.from(container.querySelectorAll('circle'));
    const progress = arcs.find(
      (c) => c.getAttribute('stroke-dashoffset') !== null,
    );
    expect(progress?.getAttribute('stroke-dashoffset')).toBe('141.5'); // 283 - 283*0.5
  });
});

describe('StatsCard', () => {
  it('renders label, value, and an upward trend badge', () => {
    const Icon = () => <svg data-testid="icon" />;
    render(<StatsCard label="Workflows" value={7} icon={Icon} trend="+12%" trendUp />);
    expect(screen.getByText('Workflows')).toBeTruthy();
    expect(screen.getByText('7')).toBeTruthy();
    expect(screen.getByText('+12%')).toBeTruthy();
    expect(screen.getByTestId('icon')).toBeTruthy();
  });

  it('omits the trend badge when no trend is given', () => {
    const Icon = () => <svg />;
    render(<StatsCard label="Agents" value={2} icon={Icon} />);
    expect(screen.queryByText(/%/)).toBeNull();
  });
});
