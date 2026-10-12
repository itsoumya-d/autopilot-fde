'use client';

import { useEffect, useMemo, useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BarChart3, ShieldCheck } from 'lucide-react';
import { api, Agent } from '@/lib/api';
import { performanceData } from '@/lib/mockData';

const modeLabels: Record<Agent['config']['mode'], string> = {
  draft: 'Draft-only mode', assisted: 'Assisted mode', autonomous: 'Autonomous mode',
};

export default function Performance() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  useEffect(() => {
    let current = true;
    api.agents().then(items => {
      if (!current) return;
      setAgents(items);
      setHasLoaded(true);
    }).catch((reason: Error) => { if (current) setError(reason.message); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, []);
  const active = agents.filter(agent => agent.status === 'running');
  const drafts = agents.reduce((sum, agent) => sum + Number(agent.metrics.drafts_created || 0), 0);
  const approvalRate = useMemo(() => {
    const values = agents.map(agent => agent.metrics.human_approval_rate).filter((value): value is number => typeof value === 'number');
    return values.length ? `${Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)}%` : '—';
  }, [agents]);

  return <div className="max-w-7xl mx-auto space-y-7">
    <div>
      <div className="flex items-center gap-2 text-sm text-cyan-300"><ShieldCheck size={16} /> Measure before expanding</div>
      <h1 className="mt-2 text-3xl font-bold">Pilot performance</h1>
      <p className="mt-1 text-slate-400">Recorded agent activity and configured review policies. Running status does not confirm a live worker.</p>
    </div>
    {loading && <p role="status" className="text-slate-400">Loading agent records…</p>}
    {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</div>}
    <div className="grid gap-5 md:grid-cols-3" aria-busy={loading}>
      <Metric label="Running agent records" value={hasLoaded ? active.length : '—'} note="Backend lifecycle status" />
      <Metric label="Drafts created" value={hasLoaded ? drafts : '—'} note="Recorded by the backend" />
      <Metric label="Human approval rate" value={approvalRate} note="Mean of reported agent rates" />
    </div>
    <section className="glass-card rounded-2xl p-6">
      <div className="flex items-center gap-2"><BarChart3 className="text-cyan-300" size={20} /><h2 className="text-xl font-semibold">Illustrative pilot trend</h2></div>
      <p className="mt-1 text-sm text-slate-400">This deterministic sandbox baseline is illustrative, not a live metrics stream.</p>
      <div className="mt-6 h-[310px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={performanceData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
            <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }} />
            <Legend />
            <Line type="monotone" dataKey="drafts" name="Drafts routed" stroke="#22d3ee" strokeWidth={3} dot={false} />
            <Line type="monotone" dataKey="reviews" name="Human reviews" stroke="#a78bfa" strokeWidth={3} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
    <section className="glass-card rounded-2xl overflow-hidden" aria-busy={loading}>
      <div className="border-b border-slate-800 p-6"><h2 className="text-xl font-semibold">Agent safety ledger</h2></div>
      <div className="divide-y divide-slate-800">
        {agents.map(agent => <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between" key={agent.id}>
          <div><p className="font-medium">{agent.name}</p><p className="mt-1 text-sm text-slate-400">{agent.metrics.drafts_created || 0} drafts · {agent.metrics.external_actions || 0} external actions</p></div>
          <div className="text-sm text-slate-300"><p>{modeLabels[agent.config.mode]}</p><p className="mt-1 text-xs text-slate-400">{agent.config.approval_required ? 'Human approval required' : 'Human approval not required'}</p></div>
        </div>)}
        {hasLoaded && !agents.length && <p className="p-6 text-slate-400">No pilot agents yet. Create a limited draft pilot from the Deploy page.</p>}
        {!loading && !hasLoaded && <p className="p-6 text-slate-400">Agent records are unavailable.</p>}
      </div>
    </section>
  </div>;
}

function Metric({ label, value, note }: { label: string; value: string | number; note: string }) {
  return <div className="glass-card rounded-2xl p-6"><p className="text-sm text-slate-400">{label}</p><p className="mt-2 text-4xl font-bold">{value}</p><p className="mt-2 text-sm text-cyan-200">{note}</p></div>;
}
