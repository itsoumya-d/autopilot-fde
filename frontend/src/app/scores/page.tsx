'use client';

import { useEffect, useMemo, useState } from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';
import APSGauge from '@/components/APSGauge';
import { ErrorState, PageHeader, SourceLabel, StatusBadge } from '@/components/Workspace';
import { api, APScore, Process, type SafetyStatus } from '@/lib/api';

const modeLabels: Record<SafetyStatus, string> = { observation_only: 'Observe only', draft_only: 'Draft + review', assisted: 'Assisted', autonomous: 'Autonomous' };

export default function Scores() {
  const [processes, setProcesses] = useState<Process[]>([]);
  const [scores, setScores] = useState<APScore[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    Promise.all([api.processes(), api.scores()])
      .then(([items, scoreItems]) => {
        if (!active) return;
        setProcesses(items);
        setScores(scoreItems);
        setSelectedId(scoreItems[0]?.process_id || '');
      })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Unable to load automation scores.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const selected = scores.find(score => score.process_id === selectedId);
  const selectedProcess = processes.find(process => process.id === selectedId);
  const chartData = useMemo(() => selected ? Object.entries(selected.factors).map(([subject, value]) => ({ subject, value })) : [], [selected]);
  const nameFor = (id: string) => processes.find(process => process.id === id)?.name || id;

  return <div className="page-stack">
    <PageHeader eyebrow="Workspace / Opportunities" title="Automation opportunity" description="Compare value, feasibility, and evidence confidence. An opportunity score is not authorization to act." />
    {error && <ErrorState>{error}</ErrorState>}
    <div className="workspace-grid items-start">
      <section className="surface min-w-0 overflow-hidden" aria-labelledby="ranked-workflows" aria-busy={loading}>
        <div className="surface-pad border-b border-[var(--border)]"><h2 id="ranked-workflows" className="text-lg font-semibold">Evidence-ranked workflows</h2><p className="metadata mt-2">Backend recommendations · estimated hours are potential savings</p></div>
        <div role="region" aria-label="Workflow scores table" tabIndex={0} className="overflow-x-auto">
          <table className="w-full min-w-[35rem] text-left text-sm">
            <thead className="bg-[var(--surface-subtle)] text-xs text-[var(--text-muted)]"><tr><th scope="col" className="px-5 py-3 font-medium">Process</th><th scope="col" className="px-4 py-3 font-medium">Opportunity</th><th scope="col" className="px-4 py-3 font-medium">Evidence</th><th scope="col" className="px-4 py-3 font-medium">Mode</th></tr></thead>
            <tbody className="divide-y divide-[var(--border)]">{scores.map(score => <tr key={score.process_id} onClick={() => setSelectedId(score.process_id)} className={`cursor-pointer transition-colors ${selectedId === score.process_id ? 'bg-[var(--accent-soft)]' : 'hover:bg-[var(--canvas)]'}`}>
              <td className="px-5 py-4"><button type="button" aria-label={`Show score for ${nameFor(score.process_id)}`} aria-pressed={selectedId === score.process_id} aria-controls="score-explanation" onClick={event => { event.stopPropagation(); setSelectedId(score.process_id); }} className="rounded-sm text-left font-medium">{nameFor(score.process_id)}</button><p className="metadata mt-2 tabular-nums">{score.estimated_hours_saved_monthly} h/mo potential</p></td>
              <td className="px-4 py-4"><div className="flex items-center gap-3"><span className="w-6 font-semibold tabular-nums">{score.score}</span><div aria-hidden="true" className="h-1.5 w-14 overflow-hidden rounded-full bg-[var(--border)]"><div className="h-full bg-[var(--accent)]" style={{ width: `${Math.min(100, Math.max(0, score.score))}%` }} /></div></div></td>
              <td className="px-4 py-4 tabular-nums">{score.evidence_confidence}%</td><td className="px-4 py-4"><StatusBadge>{modeLabels[score.recommended_mode] ?? 'Not reported'}</StatusBadge></td>
            </tr>)}</tbody>
          </table>
        </div>
        {!scores.length && <p className="surface-pad muted text-sm">{loading ? 'Loading workflow scores…' : error ? 'Workflow scores are unavailable.' : 'No opportunities to compare yet.'}</p>}
      </section>
      <aside id="score-explanation" className="inspector surface surface-pad min-w-0">
        {selected ? <>
          <SourceLabel>Selected opportunity</SourceLabel>
          <h2 className="mt-3 text-lg font-semibold">Score explanation</h2>
          <p className="mt-3 text-base font-medium">{selectedProcess?.name || selected.process_id}</p>
          <p className="mono metadata mt-1 break-all">{selected.process_id}</p>
          <div className="mt-5"><APSGauge score={selected.score} /></div>
          <div className="mt-5 grid grid-cols-3 border-y border-[var(--border)]"><SmallScore label="Value" value={selected.value_score} /><SmallScore label="Feasibility" value={selected.feasibility_score} /><SmallScore label="Evidence" value={selected.evidence_confidence} /></div>
          <p className="mt-5 text-sm leading-6">{selected.recommendation}</p>
          <p className="metadata mt-3">Recommended mode: <span className="font-medium text-[var(--text)]">{modeLabels[selected.recommended_mode] ?? 'Not reported'}</span></p>
          <section className="mt-6" aria-label="Score factors"><h3 className="text-sm font-semibold">Contributing factors</h3><dl className="mt-3 divide-y divide-[var(--border)]">{chartData.map(factor => <div key={factor.subject} className="flex items-baseline justify-between gap-3 py-2 text-sm"><dt className="min-w-0 break-words text-[var(--text-muted)]">{factor.subject.replaceAll('_', ' ')}</dt><dd className="mono shrink-0 text-xs">{factor.value}</dd></div>)}</dl>{!chartData.length && <p className="metadata mt-2">No factor breakdown was returned.</p>}</section>
          <StepPanel title="Eligible for a limited draft pilot" items={selected.eligible_steps} empty="No step meets the draft-safety threshold." />
          <StepPanel title="Blocked from automation" items={selected.blocked_steps} empty="No blocked steps were reported. This does not grant authorization." blocked />
          {chartData.length > 0 && <details className="mt-6 border-t border-[var(--border)] pt-4"><summary className="cursor-pointer text-sm font-medium">Factor comparison chart</summary><p className="metadata mt-2">Visual comparison of the same factors listed above.</p><div className="mt-2 h-56" aria-hidden="true"><ResponsiveContainer width="100%" height="100%"><RadarChart data={chartData} outerRadius="65%"><PolarGrid stroke="#D8DDD6" /><PolarAngleAxis dataKey="subject" tick={{ fill: '#636C66', fontSize: 10 }} /><Radar dataKey="value" stroke="#2458D3" fill="#2458D3" fillOpacity={0.12} isAnimationActive={false} /></RadarChart></ResponsiveContainer></div></details>}
        </> : <p role="status" className="muted text-sm leading-6">{loading ? 'Loading score explanation…' : error ? 'Score explanation unavailable.' : 'No scored workflows yet. Run discovery to generate automation scores.'}</p>}
      </aside>
    </div>
  </div>;
}

function SmallScore({ label, value }: { label: string; value: number }) { return <div className="py-3 pr-2"><p className="metadata">{label}</p><p className="mt-1 text-lg font-semibold tabular-nums">{value}</p></div>; }
function StepPanel({ title, items, empty, blocked = false }: { title: string; items: string[]; empty: string; blocked?: boolean }) {
  return <section className="mt-6 border-t border-[var(--border)] pt-4"><h3 className={`text-sm font-semibold ${blocked ? 'text-[var(--warning)]' : 'text-[var(--text)]'}`}>{title}</h3><ul className="mt-3 space-y-2 text-sm text-[var(--text-muted)]">{items.length ? items.map(item => <li key={item} className="flex gap-2"><span aria-hidden="true">{blocked ? '—' : '•'}</span><span>{item}</span></li>) : <li>{empty}</li>}</ul></section>;
}
