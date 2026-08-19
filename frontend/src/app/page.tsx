'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Activity, ArrowRight, Clock3, Cpu, FileSearch, ShieldCheck } from 'lucide-react';
import StatsCard from '@/components/StatsCard';
import { api, DashboardSummary } from '@/lib/api';

const initialSummary: DashboardSummary = {
  processes_discovered: 0, average_opportunity_score: 0, evidence_backed_hours: 0, active_agents: 0, pending_approvals: 0,
};

export default function Home() {
  const [summary, setSummary] = useState(initialSummary);
  const [error, setError] = useState('');

  useEffect(() => {
    api.dashboard().then(setSummary).catch((reason: Error) => setError(reason.message));
  }, []);

  return (
    <div className="max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      <header className="mb-10 max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-sm text-cyan-300 mb-4"><ShieldCheck size={15} /> Safe discovery mode</div>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight mb-4">Evidence, then <span className="text-cyan-400">automation.</span></h1>
        <p className="text-lg text-slate-400">AutoPilot observes work in Slack, reconstructs repeatable workflows, and only proposes human-approved draft assistants.</p>
      </header>

      {error && <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200">Backend unavailable: {error}. Start the FastAPI service to load live evidence.</div>}

      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-10">
        <StatsCard label="Processes discovered" value={String(summary.processes_discovered)} icon={FileSearch} />
        <StatsCard label="Avg opportunity score" value={`${summary.average_opportunity_score}`} icon={Activity} />
        <StatsCard label="Evidence-backed hrs / mo" value={String(summary.evidence_backed_hours)} icon={Clock3} />
        <StatsCard label="Approved draft agents" value={String(summary.active_agents)} icon={Cpu} trend={summary.pending_approvals ? `${summary.pending_approvals} pending` : undefined} />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-card rounded-2xl p-7">
          <h2 className="text-xl font-semibold">Start with a verified operating loop</h2>
          <p className="mt-2 text-slate-400">Every recommendation links back to Slack evidence. Scores express opportunity, not permission to act.</p>
          <div className="mt-6 grid sm:grid-cols-3 gap-4">
            {[
              ['1', 'Observe', 'Read-only messages and threads'],
              ['2', 'Validate', 'Inspect evidence and confidence'],
              ['3', 'Pilot', 'Draft output, then human approval'],
            ].map(([number, title, description]) => <div key={number} className="rounded-xl border border-slate-700 bg-slate-900/50 p-4"><span className="text-cyan-400 text-sm font-semibold">{number}</span><h3 className="mt-2 font-semibold">{title}</h3><p className="mt-1 text-sm text-slate-400">{description}</p></div>)}
          </div>
        </div>
        <div className="glass-card rounded-2xl p-7 flex flex-col justify-between">
          <div><h2 className="text-xl font-semibold">Recommended next move</h2><p className="mt-3 text-slate-400 text-sm">Run discovery, inspect source-linked workflow evidence, then create a limited draft-only pilot.</p></div>
          <Link href="/processes" className="mt-7 inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-3 font-medium text-slate-950 hover:bg-cyan-400">Inspect processes <ArrowRight size={17} /></Link>
        </div>
      </section>
    </div>
  );
}
