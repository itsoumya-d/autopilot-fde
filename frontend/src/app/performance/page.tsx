'use client';

import { useEffect, useMemo, useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import Link from 'next/link';
import { EmptyState, ErrorState, PageHeader, SectionHeader, SourceLabel, StatusBadge } from '@/components/Workspace';
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

  return <div className="page-stack">
    <PageHeader title="Pilot performance" description="Recorded agent activity and configured review policies. Running status does not confirm a live worker." />
    {loading && <p role="status" className="muted">Loading agent records…</p>}
    {error && <ErrorState>{error}</ErrorState>}
    <div className="ledger grid grid-cols-1 md:grid-cols-3" aria-busy={loading}>
      <Metric label="Running agent records" value={hasLoaded ? active.length : '—'} note="Backend lifecycle status" />
      <Metric label="Drafts created" value={hasLoaded ? drafts : '—'} note="Recorded by the backend" />
      <Metric label="Human approval rate" value={approvalRate} note="Mean of reported agent rates" />
    </div>
    <section className="surface overflow-hidden" aria-busy={loading}>
      <div className="surface-pad border-b border-[var(--border)]"><SectionHeader title="Agent safety ledger" description="Actual returned records, configuration, and reported activity." actions={<Link href="/deploy" className="button-secondary">Manage pilots</Link>} /></div>
      <div className="divide-y divide-[var(--border)]">
        {agents.map(agent => <div className="grid gap-4 p-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-center" key={agent.id}>
          <div className="min-w-0"><h3 className="font-semibold">{agent.name}</h3><p className="mono metadata mt-1 break-all">{agent.id}</p><p className="muted mt-2 text-sm">{agent.metrics.drafts_created || 0} drafts · {agent.metrics.external_actions || 0} external actions</p></div>
          <div className="text-sm"><p>{modeLabels[agent.config.mode]}</p><p className="muted mt-1 text-xs">{agent.config.approval_required ? 'Human approval required' : 'Human approval not required'}</p></div>
          <div><StatusBadge tone={agent.status === 'running' ? 'success' : agent.status === 'failed' ? 'danger' : agent.status === 'pending_approval' ? 'warning' : undefined}>{agent.status.replaceAll('_', ' ')}</StatusBadge></div>
        </div>)}
        {hasLoaded && !agents.length && <EmptyState title="No pilot agents yet.">Create a limited draft pilot from the Deploy page.</EmptyState>}
        {!loading && !hasLoaded && <p className="muted p-6">Agent records are unavailable.</p>}
      </div>
    </section>
    <section className="surface surface-pad">
      <SectionHeader title="Illustrative pilot trend" description="This deterministic sandbox baseline is illustrative, not a live metrics stream." actions={<SourceLabel>Example data</SourceLabel>} />
      <p className="muted mt-2 text-sm">The series stays independent of the agent records above. It does not measure this workspace.</p>
      <div className="mt-6 h-[280px] min-w-0" role="img" aria-label="Illustrative draft and review trend. Example data only; a text table follows.">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={performanceData} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#D8DDD6" vertical={false} />
            <XAxis dataKey="date" stroke="#636C66" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#636C66" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ background: '#FFFFFF', color: '#202421', border: '1px solid #D8DDD6', borderRadius: 6 }} />
            <Legend />
            <Line type="monotone" dataKey="drafts" name="Drafts routed" stroke="#2458D3" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="reviews" name="Human reviews" stroke="#25664B" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-4 border-t border-[var(--border)] pt-4 text-sm">
        <summary className="cursor-pointer font-medium">View illustrative data</summary>
        <div className="mt-3 overflow-x-auto" role="region" aria-label="Illustrative trend data" tabIndex={0}>
          <table className="w-full text-left text-sm"><caption className="sr-only">Static example trend values</caption><thead><tr><th className="p-2" scope="col">Day</th><th className="p-2" scope="col">Drafts routed</th><th className="p-2" scope="col">Human reviews</th></tr></thead><tbody>{performanceData.map(row => <tr key={row.date} className="border-t border-[var(--border)]"><td className="p-2">{row.date}</td><td className="p-2 tabular-nums">{row.drafts}</td><td className="p-2 tabular-nums">{row.reviews}</td></tr>)}</tbody></table>
        </div>
      </details>
    </section>
  </div>;
}

function Metric({ label, value, note }: { label: string; value: string | number; note: string }) {
  return <div className="ledger-stat"><p className="muted text-sm">{label}</p><p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p><p className="metadata mt-2">{note}</p></div>;
}
