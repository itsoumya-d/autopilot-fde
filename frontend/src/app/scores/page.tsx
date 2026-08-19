'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';
import { AlertTriangle, ArrowUpRight, ShieldCheck } from 'lucide-react';
import APSGauge from '@/components/APSGauge';
import { api, APScore, Process } from '@/lib/api';

export default function Scores() {
  const [processes, setProcesses] = useState<Process[]>([]);
  const [scores, setScores] = useState<APScore[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { Promise.all([api.processes(), api.scores()]).then(([items, scoreItems]) => { setProcesses(items); setScores(scoreItems); setSelectedId(scoreItems[0]?.process_id || ''); }).catch((reason: Error) => setError(reason.message)); }, []);
  const selected = scores.find((score) => score.process_id === selectedId);
  const selectedProcess = processes.find((process) => process.id === selectedId);
  const chartData = useMemo(() => selected ? Object.entries(selected.factors).map(([subject, value]) => ({ subject, value })) : [], [selected]);
  const nameFor = (id: string) => processes.find((process) => process.id === id)?.name || 'Discovering workflow';

  return <div className="max-w-7xl mx-auto space-y-7">
    <div><div className="flex items-center gap-2 text-sm text-cyan-300"><ShieldCheck size={16} /> Opportunity is not authorization</div><h1 className="mt-2 text-3xl font-bold">Automation opportunity</h1><p className="mt-1 text-slate-400">Scores combine business value, feasibility, and evidence confidence. Safety policy separately limits the mode to drafts.</p></div>
    {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</div>}
    <div className="grid gap-7 lg:grid-cols-[1.4fr_0.9fr]">
      <div className="glass-card overflow-hidden rounded-2xl"><div className="border-b border-slate-800 p-6"><h2 className="text-xl font-semibold">Evidence-ranked workflows</h2></div><div className="overflow-x-auto"><table className="w-full text-left"><thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-500"><tr><th className="p-4">Process</th><th className="p-4">Opportunity</th><th className="p-4">Evidence</th><th className="p-4">Mode</th></tr></thead><tbody className="divide-y divide-slate-800">{scores.map((score) => <tr key={score.process_id} onClick={() => setSelectedId(score.process_id)} className={`cursor-pointer transition-colors hover:bg-slate-800/50 ${selectedId === score.process_id ? 'bg-cyan-500/5' : ''}`}><td className="p-4"><p className="font-medium">{nameFor(score.process_id)}</p><p className="mt-1 text-xs text-slate-500">{score.estimated_hours_saved_monthly} h/mo potential</p></td><td className="p-4"><div className="flex items-center gap-2"><div className="h-2 w-20 overflow-hidden rounded-full bg-slate-700"><div className="h-full rounded-full bg-cyan-400" style={{ width: `${score.score}%` }} /></div><span className="font-semibold">{score.score}</span></div></td><td className="p-4 text-slate-300">{score.evidence_confidence}%</td><td className="p-4"><span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2.5 py-1 text-xs text-amber-200">Draft + review</span></td></tr>)}</tbody></table></div></div>
      <aside className="glass-card rounded-2xl p-6">{selected ? <><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Score explanation</h2><APSGauge score={selected.score} /></div><p className="mt-2 font-medium">{selectedProcess?.name}</p><div className="mt-5 grid grid-cols-3 gap-2"><SmallScore label="Value" value={selected.value_score} /><SmallScore label="Feasibility" value={selected.feasibility_score} /><SmallScore label="Evidence" value={selected.evidence_confidence} /></div><div className="mt-5 h-60"><ResponsiveContainer width="100%" height="100%"><RadarChart data={chartData} outerRadius="72%"><PolarGrid stroke="#334155" /><PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 10 }} /><Radar dataKey="value" stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.28} /></RadarChart></ResponsiveContainer></div><p className="mt-3 text-sm text-slate-400">{selected.recommendation}</p></> : <p className="text-slate-400">Loading score explanation…</p>}</aside>
    </div>
    {selected && <div className="grid gap-6 md:grid-cols-2"><StepPanel title="Eligible for a limited draft pilot" icon={<ArrowUpRight size={17} className="text-cyan-300" />} items={selected.eligible_steps} tone="cyan" /><StepPanel title="Blocked from automation" icon={<AlertTriangle size={17} className="text-amber-300" />} items={selected.blocked_steps} tone="amber" /></div>}
  </div>;
}

function SmallScore({ label, value }: { label: string; value: number }) { return <div className="rounded-lg bg-slate-900/70 p-3 text-center"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>; }
function StepPanel({ title, icon, items, tone }: { title: string; icon: ReactNode; items: string[]; tone: 'cyan' | 'amber' }) { return <div className={`rounded-2xl border p-6 ${tone === 'cyan' ? 'border-cyan-500/20 bg-cyan-500/5' : 'border-amber-500/20 bg-amber-500/5'}`}><div className="flex items-center gap-2"><span>{icon}</span><h2 className="font-semibold">{title}</h2></div><ul className="mt-4 space-y-2 text-sm text-slate-300">{items.length ? items.map((item) => <li key={item}>• {item}</li>) : <li>• No step meets the draft-safety threshold.</li>}</ul></div>; }
