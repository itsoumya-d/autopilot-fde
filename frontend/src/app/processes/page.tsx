'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Background, Controls, ReactFlow } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { CheckCircle2, Loader2, Play, ShieldCheck } from 'lucide-react';
import ProcessNode from '@/components/ProcessNode';
import { api, APScore, Process } from '@/lib/api';

const nodeTypes = { processNode: ProcessNode };

export default function Processes() {
  const [processes, setProcesses] = useState<Process[]>([]);
  const [scores, setScores] = useState<APScore[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    const [foundProcesses, foundScores] = await Promise.all([api.processes(), api.scores()]);
    setProcesses(foundProcesses); setScores(foundScores);
    setSelectedId((current) => current || foundProcesses[0]?.id || '');
  }, []);

  useEffect(() => { load().catch((reason: Error) => setError(reason.message)); }, [load]);
  const scoreFor = (id: string) => scores.find((score) => score.process_id === id);
  const selected = processes.find((process) => process.id === selectedId);
  const selectedScore = selected ? scoreFor(selected.id) : undefined;
  const nodes = useMemo(() => processes.map((process, index) => ({
    id: process.id, type: 'processNode', position: { x: 70 + (index % 2) * 310, y: 70 + Math.floor(index / 2) * 180 },
    data: { label: process.name, score: scores.find((score) => score.process_id === process.id)?.score || 0, traces: process.metrics.trace_count },
  })), [processes, scores]);
  const edges = useMemo(() => processes.slice(1).map((process, index) => ({ id: `map-${index}`, source: processes[index].id, target: process.id, animated: true, style: { stroke: '#155e75' } })), [processes]);

  async function runDiscovery() {
    setRunning(true); setError(''); setNotice('');
    try { const result = await api.discover(); await load(); setNotice(`${result.processes} workflows rebuilt from ${result.activities} source-linked activities.`); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Discovery failed'); }
    finally { setRunning(false); }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-end">
        <div><div className="flex items-center gap-2 text-sm text-cyan-300"><ShieldCheck size={16} /> Evidence-backed discovery</div><h1 className="mt-2 text-3xl font-bold">Process map</h1><p className="mt-1 text-slate-400">Threads become candidate workflows only when repeated evidence supports them.</p></div>
        <button onClick={runDiscovery} disabled={running} className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-5 py-3 font-medium text-slate-950 hover:bg-cyan-400 disabled:opacity-60">{running ? <Loader2 className="animate-spin" size={17} /> : <Play size={17} />}{running ? 'Discovering' : 'Run discovery'}</button>
      </header>
      {notice && <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-green-200">{notice}</div>}
      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}</div>}
      <div className="grid gap-6 lg:grid-cols-[1.55fr_1fr]">
        <div className="h-[470px] overflow-hidden rounded-2xl border border-slate-800 bg-[#08111f]">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodeClick={(_, node) => setSelectedId(node.id)} fitView className="bg-[#08111f]"><Background color="#1e293b" gap={20} /><Controls className="!border-slate-700 !bg-slate-900 !fill-slate-200" /></ReactFlow>
        </div>
        <aside className="glass-card rounded-2xl p-6">
          {selected && selectedScore ? <>
            <p className="text-sm text-cyan-300">Selected workflow</p><h2 className="mt-1 text-xl font-semibold">{selected.name}</h2><p className="mt-2 text-sm text-slate-400">{selected.description}</p>
            <div className="mt-5 grid grid-cols-2 gap-3"><Metric label="Observed cases" value={selected.metrics.trace_count} /><Metric label="Evidence items" value={selected.metrics.evidence_count} /><Metric label="Pattern match" value={`${Math.round(selected.metrics.pattern_consistency * 100)}%`} /><Metric label="Opportunity" value={selectedScore.score} /></div>
            <h3 className="mt-6 text-sm font-semibold text-slate-200">Evidence-linked steps</h3>
            <ol className="mt-3 space-y-3 border-l border-slate-700 pl-4">{selected.activities.map((activity) => <li key={activity.id}><div className="flex gap-2"><CheckCircle2 size={15} className="mt-0.5 text-cyan-400 shrink-0" /><div><p className="text-sm font-medium">{activity.name}</p><p className="mt-0.5 text-xs text-slate-400">“{activity.evidence}”</p></div></div></li>)}</ol>
          </> : <p className="text-slate-400">Select a process to inspect its evidence.</p>}
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) { return <div className="rounded-lg bg-slate-900/70 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>; }
