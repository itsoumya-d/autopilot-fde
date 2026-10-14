import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import APSGauge from './APSGauge';
import StatsCard from './StatsCard';

afterEach(cleanup);

describe('APSGauge', () => {
  it('renders the numeric score and label', () => {
    render(<APSGauge score={74} />);
    expect(screen.getByText('74')).toBeTruthy();
    expect(screen.getByText('APS / 100')).toBeTruthy();
  });

  it.each([0, 50, 100])('encodes score %i as an accessible proportional meter', score => {
    render(<APSGauge score={score} />);
    const meter = screen.getByRole('meter', { name: 'Automation opportunity score' });
    expect(meter.getAttribute('aria-valuenow')).toBe(String(score));
    expect(meter.getAttribute('aria-valuemin')).toBe('0');
    expect(meter.getAttribute('aria-valuemax')).toBe('100');
    expect((meter.firstElementChild as HTMLElement).style.width).toBe(`${score}%`);
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
