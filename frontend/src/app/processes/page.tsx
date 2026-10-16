'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Background, Controls, ReactFlow } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Loader2, Play } from 'lucide-react';
import { ErrorState, PageHeader, SourceLabel } from '@/components/Workspace';
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
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const mounted = useRef(false);
  const loadSequence = useRef(0);
  const discovery = useRef<symbol | null>(null);

  const load = useCallback(async (afterDiscovery = false) => {
    const sequence = ++loadSequence.current;
    const current = () => mounted.current && sequence === loadSequence.current;
    setLoading(true);
    setError('');
    try {
      const [foundProcesses, foundScores] = await Promise.all([api.processes(), api.scores()]);
      if (!current()) return false;
      setProcesses(foundProcesses);
      setScores(foundScores);
      setSelectedId(selected => foundProcesses.some(process => process.id === selected) ? selected : foundProcesses[0]?.id || '');
      setHasLoaded(true);
      return true;
    } catch (reason) {
      if (current()) {
        const message = reason instanceof Error ? reason.message : 'Could not load workflows';
        setError(afterDiscovery ? `Discovery completed, but workflow refresh failed: ${message}` : message);
      }
      return false;
    } finally {
      if (current()) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
      loadSequence.current += 1;
      discovery.current = null;
    };
  }, [load]);
  const scoreFor = (id: string) => scores.find((score) => score.process_id === id);
  const selected = processes.find((process) => process.id === selectedId);
  const selectedScore = selected ? scoreFor(selected.id) : undefined;
  const nodes = useMemo(() => processes.map((process, index) => ({
    id: process.id, type: 'processNode', position: { x: 70 + (index % 2) * 310, y: 70 + Math.floor(index / 2) * 180 },
    selected: process.id === selectedId,
    data: { label: process.name, score: scores.find((score) => score.process_id === process.id)?.score, traces: process.metrics.trace_count },
  })), [processes, scores, selectedId]);

  async function runDiscovery() {
    if (!mounted.current || discovery.current) return;
    const token = Symbol();
    discovery.current = token;
    // Initial reads no longer describe the state being rebuilt, even if they finish first.
    loadSequence.current += 1;
    const current = () => mounted.current && discovery.current === token;
    setRunning(true); setLoading(true); setError(''); setNotice('');
    try {
      const result = await api.discover();
      if (!current()) return;
      const refreshed = await load(true);
      if (current() && refreshed) setNotice(`${result.processes} workflows rebuilt from ${result.activities} source-linked activities.`);
    } catch (reason) {
      if (current()) setError(reason instanceof Error ? reason.message : 'Discovery failed');
    } finally {
      if (current()) {
        discovery.current = null;
        setRunning(false);
        setLoading(false);
      }
    }
  }

  return (
    <div className="page-stack">
      <PageHeader title="Process map" description="Inspect repeated work and the source evidence behind each candidate workflow." actions={
        <button onClick={runDiscovery} disabled={running} className="button-primary min-w-[154px]">{running ? <Loader2 className="animate-spin motion-reduce:animate-none" size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}{running ? 'Discovering' : 'Run discovery'}</button>
      } />
      {notice && <div role="status" className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--success)]">{notice}</div>}
      {error && <ErrorState>{error}</ErrorState>}
      {loading && <p role="status" className="muted text-sm">Loading workflows…</p>}
      <div className="workspace-grid items-start" aria-busy={loading}>
        <section className="surface min-w-0" aria-labelledby="workflow-register">
          <div className="surface-pad border-b border-[var(--border)]">
            <div className="flex flex-wrap items-center justify-between gap-2"><h2 id="workflow-register" className="text-lg font-semibold">Discovered workflows</h2><SourceLabel>{processes.length} workflows</SourceLabel></div>
            <p className="metadata mt-2">Select a row or a node to inspect the same evidence.</p>
          </div>
          <ul aria-label="Workflow selection" className="divide-y divide-[var(--border)]">
            {processes.map(process => <li key={process.id}>
              <button type="button" aria-pressed={selectedId === process.id} aria-controls="workflow-evidence" onClick={() => setSelectedId(process.id)} className={`flex min-h-12 w-full items-center justify-between gap-3 border-l-2 px-5 py-3 text-left transition-colors ${selectedId === process.id ? 'border-[var(--accent)] bg-[var(--accent-soft)]' : 'border-transparent hover:bg-[var(--surface-subtle)]'}`}>
                <span className="min-w-0 break-words text-sm font-medium">{process.name}</span>{' '}<span className="metadata shrink-0 tabular-nums">{process.metrics.trace_count} cases</span>
              </button>
            </li>)}
          </ul>
          <div className="border-t border-[var(--border)] px-5 py-3"><p className="metadata">Workflow selection map · positions are illustrative; no dependencies are implied.</p></div>
          <div className="map-frame h-[360px] min-w-0 sm:h-[420px]" aria-label="Workflow selection map">
            <ReactFlow nodes={nodes} edges={[]} nodeTypes={nodeTypes} onNodeClick={(_, node) => setSelectedId(node.id)} nodesConnectable={false} fitView className="bg-[var(--canvas-deep)]"><Background color="#d9ddd1" gap={22} /><Controls /></ReactFlow>
          </div>
        </section>
        <aside id="workflow-evidence" className="inspector surface surface-pad min-w-0">
          {selected ? <>
            <SourceLabel>Selected workflow</SourceLabel><h2 className="mt-3 text-xl font-semibold">{selected.name}</h2><p className="mono metadata mt-2 break-all">{selected.id}</p><p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">{selected.description}</p>
            <div className="mt-5 grid grid-cols-2 border-y border-[var(--border)]"><Metric label="Observed cases" value={selected.metrics.trace_count} /><Metric label="Evidence items" value={selected.metrics.evidence_count} /><Metric label="Pattern match" value={`${Math.round(selected.metrics.pattern_consistency * 100)}%`} /><Metric label="Opportunity" value={selectedScore?.score ?? '—'} /></div>
            <h3 className="mt-6 text-base font-semibold">Evidence-linked steps</h3>
            <ol className="evidence-list mt-4">{selected.activities.map((activity, index) => <li key={activity.id} className="grid min-w-0 grid-cols-[24px_minmax(0,1fr)] gap-3 pb-5">
              <span className="mono flex h-6 w-6 items-center justify-center rounded-full border border-[var(--border-control)] text-xs text-[var(--text-muted)]">{index + 1}</span>
              <div className="min-w-0"><p className="text-sm font-semibold">{activity.name}</p><p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">“{activity.evidence}”</p><div className="metadata mt-2 space-y-1"><p className="mono break-all">Case {activity.case_id}</p>{activity.source_messages.length > 0 && <p className="mono break-all">Sources: {activity.source_messages.join(', ')}</p>}</div></div>
            </li>)}</ol>
            {!selected.activities.length && <p className="muted mt-3 text-sm">No activity evidence was returned for this workflow.</p>}
          </> : <p className="muted text-sm leading-6">{loading ? 'Loading workflow evidence…' : !hasLoaded ? 'Workflow evidence could not be loaded. Run discovery to try again.' : !processes.length ? 'No workflows discovered yet. Run discovery to inspect source-linked evidence.' : 'Select a process to inspect its evidence.'}</p>}
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) { return <div className="py-3 pr-3"><p className="metadata">{label}</p><p className="mt-1 text-xl font-semibold tabular-nums">{value}</p></div>; }
