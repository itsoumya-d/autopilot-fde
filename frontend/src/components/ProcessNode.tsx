import React from 'react';

const ProcessNode = ({ data, selected = false }: { data: { label: string; score?: number; traces: number }; selected?: boolean }) => {
  const scoreTone = data.score == null ? 'unknown' : data.score >= 65 ? 'high' : data.score >= 45 ? 'medium' : 'low';
  return (
    <div data-score-tone={scoreTone} data-selected={selected} className={`process-node w-60 rounded-[10px] border bg-[var(--surface)] px-4 py-3.5 ${selected ? 'border-[var(--accent)] ring-1 ring-[var(--accent)]' : 'border-[var(--border-control)]'}`}>
      <p className="text-sm font-semibold leading-5 text-[var(--text)]">{data.label}</p>
      <p className="mt-2 text-xs text-[var(--text-muted)]">Opportunity {data.score ?? '—'} · {data.traces} observed cases</p>
      {selected && <p className="mt-2 text-xs font-semibold text-[var(--accent)]">In inspector</p>}
    </div>
  );
};

export default ProcessNode;
