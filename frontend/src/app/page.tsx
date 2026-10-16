'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Activity, ArrowRight, Clock3, Cpu, FileSearch } from 'lucide-react';
import StatsCard from '@/components/StatsCard';
import { ErrorState, PageHeader, SectionHeader, SourceLabel, StatusBadge } from '@/components/Workspace';
import { api, DashboardSummary } from '@/lib/api';

export default function Home() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let current = true;
    api.dashboard().then(result => { if (current) setSummary(result); })
      .catch((reason: Error) => { if (current) setError(reason.message); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, []);

  return (
    <div className="page-stack">
      <PageHeader title="Workspace overview"
        description="Observe work, inspect the evidence, and prepare human-reviewed draft pilots."
        actions={<Link href="/processes" className="button-primary">Inspect processes <ArrowRight size={16} aria-hidden="true" /></Link>} />

      {loading && <p role="status" className="muted">Loading workspace summary…</p>}
      {error && <ErrorState>Backend unavailable: {error}. Start the FastAPI service to load live evidence.</ErrorState>}

      <section aria-label="Recorded workspace metrics" aria-busy={loading}>
        <div className="ledger grid grid-cols-1 min-[480px]:grid-cols-2 xl:grid-cols-4">
          <StatsCard label="Processes discovered" value={summary?.processes_discovered ?? '—'} icon={FileSearch} />
          <StatsCard label="Avg opportunity score" value={summary?.average_opportunity_score ?? '—'} icon={Activity} />
          <StatsCard label="Evidence-backed hrs / mo" value={summary?.evidence_backed_hours ?? '—'} icon={Clock3} />
          <StatsCard label="Approved draft agents" value={summary?.active_agents ?? '—'} icon={Cpu} />
        </div>
        <div className="mt-3"><SourceLabel>Source: backend summary. Workspace records may include seeded demo evidence.</SourceLabel></div>
      </section>

      <section className="surface surface-pad">
        <SectionHeader title="From observation to a reviewed pilot" description="Keep the source evidence in view at every step. An opportunity score does not authorize an action." />
        <ol className="mt-6 grid gap-0 md:grid-cols-3">
          {[
            { number: '01', title: 'Observe', description: 'Review read-only sources and reconstruct repeatable work.', href: '/channels', action: 'View sources' },
            { number: '02', title: 'Review', description: 'Inspect workflow evidence, confidence, and eligible steps.', href: '/processes', action: 'Review workflows' },
            { number: '03', title: 'Pilot', description: 'Create a limited draft record and inspect its approval policy.', href: '/deploy', action: 'Review pilots' },
          ].map(item => <li key={item.number} className="min-w-0 border-t border-[var(--border)] py-5 md:pr-6">
            <p className="mono metadata">{item.number}</p>
            <h3 className="mt-3 text-lg font-semibold">{item.title}</h3>
            <p className="muted mt-2 max-w-sm text-sm">{item.description}</p>
            {item.title === 'Pilot' && <div className="mt-3"><StatusBadge tone={summary?.pending_approvals ? 'warning' : undefined}>{summary ? `${summary.pending_approvals} pending approvals` : 'Approvals unavailable'}</StatusBadge></div>}
            <Link href={item.href} className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[var(--accent)]">{item.action}<ArrowRight size={14} aria-hidden="true" /></Link>
          </li>)}
        </ol>
      </section>

      <div className="flex flex-col gap-2 border-t border-[var(--border)] pt-5 sm:flex-row sm:items-start sm:justify-between">
        <p className="muted max-w-2xl text-sm">Pilot records describe configuration and review state. Creating or approving a record does not start a live worker.</p>
        <Link href="/archetypes" className="shrink-0 text-sm font-medium text-[var(--accent)]">Explore the Workflow Lab →</Link>
      </div>
    </div>
  );
}
