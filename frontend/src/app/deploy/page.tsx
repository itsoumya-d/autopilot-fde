'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Clock3, Loader2, Pause, Play, Rocket, ShieldAlert, ShieldCheck, Trash2 } from 'lucide-react';
import DeploySlider from '@/components/DeploySlider';
import { api, type APScore, type Agent, type AgentStatus, type Process } from '@/lib/api';

const statusLabels: Record<AgentStatus, string> = {
  pending_approval: 'Pending approval', deploying: 'Deploying', running: 'Running',
  paused: 'Paused', stopped: 'Stopped', failed: 'Failed',
};
type Action = 'approve' | 'pause' | 'resume' | 'remove';
const actionStates: Record<Exclude<Action, 'remove'>, AgentStatus> = {
  approve: 'pending_approval', pause: 'running', resume: 'paused',
};
const resultStates: Record<Exclude<Action, 'remove'>, AgentStatus> = {
  approve: 'running', pause: 'paused', resume: 'running',
};
const canActivate = (agent: Agent) => agent.config.approval_required && agent.config.mode !== 'autonomous';
const errorMessage = (reason: unknown) => reason instanceof Error ? reason.message : 'Request failed';
const isRecord = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
const isText = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const isTextList = (value: unknown): value is string[] => Array.isArray(value) && value.every(isText);

// Validate the fields this page consumes before treating a 2xx response as data.
function isAgent(value: unknown): value is Agent {
  if (!isRecord(value) || !isText(value.id) || !isText(value.process_id) || !isText(value.name)
    || !isText(value.status) || !Object.hasOwn(statusLabels, value.status) || !isText(value.created_at)
    || !isRecord(value.config) || !isRecord(value.metrics)) return false;
  const { config, metrics } = value;
  return isNumber(config.traffic_percentage) && config.traffic_percentage >= 0 && config.traffic_percentage <= 100
    && isTextList(config.enabled_steps) && typeof config.approval_required === 'boolean'
    && isText(config.mode) && ['draft', 'assisted', 'autonomous'].includes(config.mode)
    && isNumber(config.confidence_threshold) && config.confidence_threshold >= 0.5 && config.confidence_threshold <= 0.99
    && (metrics.drafts_created == null || (isNumber(metrics.drafts_created) && metrics.drafts_created >= 0));
}
function assertAgent(value: unknown, expected: { status: AgentStatus; id?: string; processId: string }): asserts value is Agent {
  if (!isAgent(value) || value.status !== expected.status || value.process_id !== expected.processId
    || (expected.id !== undefined && value.id !== expected.id)) {
    throw new Error('The backend returned an invalid agent result.');
  }
}
function assertList<T>(value: unknown, valid: (item: unknown) => boolean, key: keyof T, name: string): asserts value is T[] {
  if (!Array.isArray(value) || !value.every(valid) || new Set(value.map(item => item[key])).size !== value.length) {
    throw new Error(`The backend returned invalid ${name}.`);
  }
}

export default function Deploy() {
  const [processes, setProcesses] = useState<Process[]>([]);
  const [scores, setScores] = useState<APScore[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [traffic, setTraffic] = useState(10);
  const [working, setWorking] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [refreshRequired, setRefreshRequired] = useState(false);
  const mounted = useRef(false);
  const loadSequence = useRef(0);
  const isLoading = useRef(true);
  const needsRefresh = useRef(false);
  // One synchronous lock protects creation and every row, even before React rerenders.
  const mutation = useRef<symbol | null>(null);

  const load = useCallback(async (afterMutation = false) => {
    const sequence = ++loadSequence.current;
    const current = () => mounted.current && sequence === loadSequence.current;
    isLoading.current = true;
    setLoading(true);
    setLoadError('');
    try {
      const [processItems, scoreItems, agentItems] = await Promise.all([api.processes(), api.scores(), api.agents()]);
      if (!current()) return;
      assertList<Process>(processItems, item => isRecord(item) && isText(item.id) && isText(item.name), 'id', 'workflows');
      assertList<APScore>(scoreItems, item => isRecord(item) && isText(item.process_id) && isNumber(item.score)
        && typeof item.recommendation === 'string' && isTextList(item.eligible_steps) && isTextList(item.blocked_steps), 'process_id', 'workflow scores');
      assertList<Agent>(agentItems, isAgent, 'id', 'agent records');
      setProcesses(processItems);
      setScores(scoreItems);
      setAgents(agentItems);
      const eligible = scoreItems.filter(item => item.eligible_steps.length && processItems.some(process => process.id === item.process_id));
      setSelectedId(selected => eligible.some(item => item.process_id === selected) ? selected : eligible[0]?.process_id || '');
      setHasLoaded(true);
      setError('');
      needsRefresh.current = false;
      setRefreshRequired(false);
    } catch (reason) {
      if (!current()) return;
      setLoadError(afterMutation
        ? `The change was saved, but records could not be refreshed: ${errorMessage(reason)} Showing the confirmed change. Retry refresh before making another change.`
        : `Could not load deployment records: ${errorMessage(reason)} Retry refresh to get the current records.`);
      needsRefresh.current = true;
      setRefreshRequired(true);
    } finally {
      if (current()) {
        isLoading.current = false;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
      loadSequence.current += 1;
      mutation.current = null;
    };
  }, [load]);

  const score = scores.find(item => item.process_id === selectedId);
  const process = processes.find(item => item.id === selectedId);
  const eligibleSteps = score?.eligible_steps || [];
  const proposedName = process ? `${process.name} · draft assistant` : 'Draft assistant';
  const disabled = loading || Boolean(working) || refreshRequired;

  async function mutate(action: Action | 'deploy', agent?: Agent) {
    if (!mounted.current || mutation.current || isLoading.current || needsRefresh.current) return;
    if (action === 'deploy' ? !score || !process || !eligibleSteps.length
      : !agent || (action !== 'remove' && agent.status !== actionStates[action])) return;
    if ((action === 'approve' || action === 'resume') && !canActivate(agent!)) return;
    const token = Symbol();
    mutation.current = token;
    loadSequence.current += 1; // An older load must never overwrite a confirmed mutation.
    const current = () => mounted.current && mutation.current === token;
    setWorking(action === 'deploy' ? 'deploy' : `${action}:${agent!.id}`);
    setError('');
    setLoadError('');
    setNotice('');
    try {
      let result: Agent | null = null;
      if (action === 'deploy') {
        const config: Agent['config'] = { traffic_percentage: traffic, enabled_steps: eligibleSteps.slice(0, 1), approval_required: true, mode: 'draft', confidence_threshold: 0.85 };
        result = await api.deploy({ process_id: process!.id, name: proposedName, config });
        if (!current()) return;
        assertAgent(result, { status: 'pending_approval', processId: process!.id });
        if (agents.some(item => item.id === result!.id) || result.name !== proposedName
          || result.config.traffic_percentage !== config.traffic_percentage || result.config.mode !== config.mode
          || result.config.approval_required !== config.approval_required || result.config.confidence_threshold !== config.confidence_threshold
          || JSON.stringify(result.config.enabled_steps) !== JSON.stringify(config.enabled_steps)) {
          throw new Error('The backend returned an invalid pilot configuration.');
        }
      } else if (action === 'remove') {
        const result = await api.removeAgent(agent!.id);
        if (!current()) return;
        if (!isRecord(result) || !isText(result.message)) throw new Error('The backend returned an invalid removal result.');
      } else {
        result = await ({ approve: api.approveAgent, pause: api.pauseAgent, resume: api.resumeAgent })[action](agent!.id);
        if (!current()) return;
        assertAgent(result, { status: resultStates[action], id: agent!.id, processId: agent!.process_id });
        if ((action === 'approve' || action === 'resume') && !canActivate(result)) {
          throw new Error('The backend returned an invalid agent result: activation requires human approval and draft or assisted mode.');
        }
      }
      if (!current()) return;
      const confirmed = result;
      setAgents(items => action === 'remove' ? items.filter(item => item.id !== agent!.id)
        : action === 'deploy' ? [...items, confirmed!] : items.map(item => item.id === confirmed!.id ? confirmed! : item));
      setNotice(action === 'deploy' ? 'Pilot record created. Pending human approval; no worker was started.'
        : action === 'remove' ? 'Agent record removed.'
        : `${action === 'approve' ? 'Approval' : action === 'pause' ? 'Pause' : 'Resume'} saved. Agent record status: ${statusLabels[confirmed!.status]}.`);
      // A refresh failure is separate from a successful, validated mutation.
      await load(true);
    } catch (reason) {
      if (!current()) return;
      setError(`Could not confirm the change: ${errorMessage(reason)} Refresh records before trying again.`);
      needsRefresh.current = true;
      setRefreshRequired(true);
    } finally {
      if (current()) {
        mutation.current = null;
        setWorking('');
      }
    }
  }

  return <div className="max-w-6xl mx-auto space-y-7">
    <div>
      <div className="flex items-center gap-2 text-sm text-cyan-300"><ShieldCheck size={16} aria-hidden="true" /> Policy-constrained deployment</div>
      <h1 className="mt-2 text-3xl font-bold">Create a draft pilot</h1>
      <p className="mt-1 text-slate-400">Save agent configuration and lifecycle records. This page does not start a hosted worker or route live traffic.</p>
    </div>
    <div role="status" aria-live="polite" aria-atomic="true">
      {notice && <p className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-green-200">{notice}</p>}
      {loading && <p className="mt-2 text-sm text-slate-400">Loading deployment records…</p>}
    </div>
    {(error || loadError) && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error && <p>{error}</p>}{loadError && <p>{loadError}</p>}</div>}
    <div className="grid gap-7 lg:grid-cols-[1fr_1.1fr]">
      <section aria-labelledby="pilot-configuration" className="glass-card rounded-2xl p-6">
        <div className="flex items-center gap-2"><Rocket className="text-cyan-300" size={20} aria-hidden="true" /><h2 id="pilot-configuration" className="text-xl font-semibold">Pilot configuration</h2></div>
        <fieldset disabled={disabled}>
          <label className="mt-6 block text-sm font-medium text-slate-300">Evidence-backed workflow
            <select value={selectedId} onChange={event => setSelectedId(event.target.value)} disabled={disabled || !selectedId} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 p-3 text-white focus:border-cyan-400 focus:outline-none disabled:opacity-50">
              {!selectedId && <option value="">{loading ? 'Loading workflows…' : !hasLoaded ? 'Workflows unavailable' : 'No eligible workflows'}</option>}
              {scores.map(item => {
                const workflow = processes.find(processItem => processItem.id === item.process_id);
                return <option value={item.process_id} key={item.process_id} disabled={!item.eligible_steps.length || !workflow}>{workflow?.name || item.process_id} {workflow ? item.eligible_steps.length ? `(${item.score})` : '(observe only)' : '(workflow unavailable)'}</option>;
              })}
            </select>
          </label>
          <div className="mt-6 rounded-xl border border-slate-700 bg-slate-900/70 p-4">
            <div className="flex items-center justify-between"><div><p className="font-medium">Configured pilot traffic</p><p className="mt-1 text-xs text-slate-500">Saved configuration, capped at 50% in this form.</p></div><p className="text-2xl font-bold text-cyan-300">{traffic}%</p></div>
            <DeploySlider value={traffic} onChange={setTraffic} disabled={disabled} label="Configured traffic percentage" />
          </div>
          <div className="mt-5 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-cyan-100"><ShieldAlert size={16} aria-hidden="true" /> Pilot request policy</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-300"><li>• Output mode: <strong>draft only</strong></li><li>• Human approval: <strong>required</strong></li><li>• Confidence threshold: <strong>85%</strong></li><li>• Creation selects the <strong>first eligible step</strong></li></ul>
          </div>
          <button onClick={() => void mutate('deploy')} disabled={disabled || !process || !eligibleSteps.length} className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-500 py-3 font-medium text-slate-950 hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50">
            {working === 'deploy' ? <Loader2 size={18} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <Rocket size={18} aria-hidden="true" />}{working === 'deploy' ? 'Creating pilot…' : 'Create draft pilot'}
          </button>
        </fieldset>
      </section>
      <section aria-labelledby="approval-boundary" className="glass-card rounded-2xl p-6">
        <h2 id="approval-boundary" className="text-xl font-semibold">Approval boundary</h2>
        {score ? <>
          <p className="mt-2 text-sm text-slate-400">{score.recommendation}</p>
          <div className="mt-6"><p className="text-sm font-medium text-slate-300">Available draft steps</p><div className="mt-3 flex flex-wrap gap-2">{eligibleSteps.map(step => <span key={step} className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1.5 text-sm text-cyan-100">{step}</span>)}</div></div>
          <div className="mt-5"><p className="text-sm font-medium text-slate-300">Human-owned steps</p><div className="mt-3 flex flex-wrap gap-2">{score.blocked_steps.map(step => <span key={step} className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-sm text-amber-100">{step}</span>)}</div></div>
        </> : <p className="mt-3 text-slate-400">{loading ? 'Loading policy…' : !hasLoaded ? 'Policy could not be loaded.' : !scores.length ? 'No scored workflows are available. Discover and score a workflow before creating a pilot.' : 'No eligible workflow is available for a draft pilot.'}</p>}
      </section>
    </div>
    <section aria-labelledby="agent-records" aria-busy={loading || Boolean(working)} className="glass-card rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between gap-4 border-b border-slate-800 p-6">
        <div><h2 id="agent-records" className="text-xl font-semibold">Agent records</h2><p className="mt-1 text-sm text-slate-400">Statuses come from the backend lifecycle record. Running does not confirm a live worker.</p></div>
        <button onClick={() => { if (!mutation.current) void load(); }} disabled={Boolean(working)} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm disabled:opacity-50"><Clock3 size={16} aria-hidden="true" />{refreshRequired ? 'Retry refresh' : 'Refresh records'}</button>
      </div>
      <div className="divide-y divide-slate-800">
        {agents.length ? agents.map(agent => <div key={agent.id} role="group" aria-label={agent.name} className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2"><p className="font-medium">{agent.name}</p><span className={`rounded-full border px-2 py-0.5 text-xs ${agent.status === 'running' ? 'border-green-400/30 bg-green-400/10 text-green-200' : agent.status === 'failed' ? 'border-red-400/30 bg-red-400/10 text-red-200' : 'border-slate-400/30 bg-slate-400/10 text-slate-200'}`}>{statusLabels[agent.status]}</span></div>
            <p className="mt-1 text-sm text-slate-400">{agent.config.traffic_percentage}% configured traffic · {agent.config.mode} mode · {agent.config.enabled_steps.join(', ') || 'Default step selection'} · {agent.metrics.drafts_created ?? 0} recorded drafts</p>
            {(agent.status === 'pending_approval' || agent.status === 'paused') && !canActivate(agent) && <p className="mt-1 text-sm text-amber-200">Approval and resume require draft or assisted mode with human approval enabled.</p>}
          </div>
          <div className="flex gap-2">
            {agent.status === 'pending_approval' && <ActionButton label="Approve" icon={<Play size={15} aria-hidden="true" />} onClick={() => void mutate('approve', agent)} loading={working === `approve:${agent.id}`} disabled={disabled || !canActivate(agent)} />}
            {agent.status === 'running' && <ActionButton label="Pause" icon={<Pause size={15} aria-hidden="true" />} onClick={() => void mutate('pause', agent)} loading={working === `pause:${agent.id}`} disabled={disabled} muted />}
            {agent.status === 'paused' && <ActionButton label="Resume" icon={<Play size={15} aria-hidden="true" />} onClick={() => void mutate('resume', agent)} loading={working === `resume:${agent.id}`} disabled={disabled || !canActivate(agent)} />}
            <button aria-label={`Remove ${agent.name}`} onClick={() => void mutate('remove', agent)} disabled={disabled} className="rounded-lg border border-slate-700 p-2.5 text-slate-400 hover:border-red-400 hover:text-red-300 disabled:opacity-50">{working === `remove:${agent.id}` ? <Loader2 size={16} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}</button>
          </div>
        </div>) : <p className="p-6 text-sm text-slate-400">{loading ? 'Loading agent records…' : !hasLoaded ? 'Agent records could not be loaded.' : 'No pilot records have been created.'}</p>}
      </div>
    </section>
  </div>;
}

function ActionButton({ label, icon, onClick, loading, disabled, muted = false }: { label: string; icon: ReactNode; onClick: () => void; loading: boolean; disabled: boolean; muted?: boolean }) {
  return <button onClick={onClick} disabled={disabled} aria-busy={loading} className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-50 ${muted ? 'border border-slate-700 text-slate-200 hover:bg-slate-800' : 'bg-cyan-500 text-slate-950 hover:bg-cyan-400'}`}>{loading ? <Loader2 size={15} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : icon}{label}</button>;
}
