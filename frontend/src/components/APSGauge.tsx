import React from 'react';

interface APSGaugeProps {
  score: number;
}

// Compact comparison mark. Opportunity measures suitability, never permission.
const APSGauge: React.FC<APSGaugeProps> = ({ score }) => (
  <div className="min-w-0">
    <div className="flex items-baseline justify-between gap-3"><span className="text-2xl font-semibold tabular-nums text-[var(--text)]">{score}</span><span className="metadata">APS / 100</span></div>
    <div role="meter" aria-label="Automation opportunity score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={score} className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--surface-subtle)]">
      <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
    </div>
  </div>
);

export default APSGauge;
