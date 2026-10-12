'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Clock3, Loader2, Pause, Play, Trash2 } from 'lucide-react';
import { ErrorState, PageHeader, SourceLabel, StatusBadge } from '@/components/Workspace';
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

  return <div className="page-stack">
    <PageHeader eyebrow="Operate / Pilots" title="Create a draft pilot" description="Save agent configuration and lifecycle records. This page does not start a hosted worker or route live traffic." />
    <div role="status" aria-live="polite" aria-atomic="true">
      {notice && <p className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--success)]">{notice}</p>}
      {loading && <p className="muted text-sm">Loading deployment records…</p>}
    </div>
    {(error || loadError) && <ErrorState>{error && <p>{error}</p>}{loadError && <p>{loadError}</p>}</ErrorState>}
    <div className="surface grid min-w-0 lg:grid-cols-2">
      <section aria-labelledby="pilot-configuration" className="surface-pad min-w-0">
        <SourceLabel>01 / Configure</SourceLabel>
        <h2 id="pilot-configuration" className="mt-3 text-lg font-semibold">Pilot configuration</h2>
        <fieldset disabled={disabled} className="min-w-0">
          <label className="label mt-6">Evidence-backed workflow
            <select value={selectedId} onChange={event => setSelectedId(event.target.value)} disabled={disabled || !selectedId} className="field mt-2 disabled:opacity-50">
              {!selectedId && <option value="">{loading ? 'Loading workflows…' : !hasLoaded ? 'Workflows unavailable' : 'No eligible workflows'}</option>}
              {scores.map(item => {
                const workflow = processes.find(processItem => processItem.id === item.process_id);
                return <option value={item.process_id} key={item.process_id} disabled={!item.eligible_steps.length || !workflow}>{workflow?.name || item.process_id} {workflow ? item.eligible_steps.length ? `(${item.score})` : '(observe only)' : '(workflow unavailable)'}</option>;
              })}
            </select>
          </label>
          {process && <p className="mono metadata mt-2 break-all">{process.id}</p>}
          <div className="mt-6 border-y border-[var(--border)] py-5">
            <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-medium">Configured pilot traffic</p><p className="metadata mt-1">Saved configuration, capped at 50% in this form.</p></div><p className="text-2xl font-semibold tabular-nums text-[var(--accent)]">{traffic}%</p></div>
            <DeploySlider value={traffic} onChange={setTraffic} disabled={disabled} label="Configured traffic percentage" />
          </div>
          <button onClick={() => void mutate('deploy')} disabled={disabled || !process || !eligibleSteps.length} className="button-primary mt-6 w-full">
            {working === 'deploy' && <Loader2 size={16} className="animate-spin motion-reduce:animate-none" aria-hidden="true" />}{working === 'deploy' ? 'Creating pilot…' : 'Create draft pilot'}
          </button>
          <p className="metadata mt-3 leading-5">Creating or approving a pilot saves a record only. Neither action starts a live worker.</p>
        </fieldset>
      </section>
      <section aria-labelledby="approval-boundary" className="surface-pad min-w-0 border-t border-[var(--border)] lg:border-l lg:border-t-0">
        <SourceLabel>02 / Review the boundary</SourceLabel>
        <h2 id="approval-boundary" className="mt-3 text-lg font-semibold">Approval boundary</h2>
        <section aria-labelledby="pilot-request-policy" className="mt-5">
          <h3 id="pilot-request-policy" className="text-sm font-semibold">Pilot request policy</h3>
          <dl className="mt-3 divide-y divide-[var(--border)] text-sm"><PolicyRow label="Output mode" value="Draft only" /><PolicyRow label="Human approval" value="Required" /><PolicyRow label="Confidence threshold" value="85%" /><PolicyRow label="Creation enables" value="First eligible step" /></dl>
        </section>
        {score ? <>
          <p className="mt-5 text-sm leading-6 text-[var(--text-muted)]">{score.recommendation}</p>
          <section className="mt-5"><h3 className="text-sm font-semibold">Available draft steps</h3><ul className="mt-3 space-y-3">{eligibleSteps.map((step, index) => <li key={step} className="flex flex-wrap items-start justify-between gap-2 text-sm"><span>{step}</span><StatusBadge tone={index === 0 ? 'success' : 'neutral'}>{index === 0 ? 'Enabled on creation' : 'Available'}</StatusBadge></li>)}</ul></section>
          <section className="mt-5 border-t border-[var(--border)] pt-4"><h3 className="text-sm font-semibold text-[var(--warning)]">Human-owned steps</h3><ul className="mt-3 space-y-2 text-sm text-[var(--text-muted)]">{score.blocked_steps.length ? score.blocked_steps.map(step => <li key={step}>— {step}</li>) : <li>No blocked steps were reported. Human approval is still required.</li>}</ul></section>
        </> : <p className="muted mt-5 text-sm leading-6">{loading ? 'Loading policy…' : !hasLoaded ? 'Policy could not be loaded.' : !scores.length ? 'No scored workflows are available. Discover and score a workflow before creating a pilot.' : 'No eligible workflow is available for a draft pilot.'}</p>}
      </section>
    </div>
    <section aria-labelledby="agent-records" aria-busy={loading || Boolean(working)} className="surface overflow-hidden">
      <div className="surface-pad flex flex-wrap items-start justify-between gap-4 border-b border-[var(--border)]">
        <div className="max-w-prose"><h2 id="agent-records" className="text-lg font-semibold">Agent records</h2><p className="metadata mt-2">Statuses come from the backend lifecycle record. Running does not confirm a live worker.</p></div>
        <button onClick={() => { if (!mutation.current) void load(); }} disabled={Boolean(working)} className="button-secondary shrink-0"><Clock3 size={15} aria-hidden="true" />{refreshRequired ? 'Retry refresh' : 'Refresh records'}</button>
      </div>
      <div className="divide-y divide-[var(--border)]">
        {agents.length ? agents.map(agent => <div key={agent.id} data-testid={`agent-record-${agent.id}`} role="group" aria-label={agent.name} className="surface-pad min-w-0">
          <div className="flex flex-col justify-between gap-4 sm:flex-row">
            <div className="min-w-0"><div className="flex flex-wrap items-center gap-3"><p className="font-semibold">{agent.name}</p><StatusBadge tone={agent.status === 'running' ? 'success' : agent.status === 'failed' ? 'danger' : agent.status === 'pending_approval' ? 'warning' : 'neutral'}>{statusLabels[agent.status]}</StatusBadge></div><p className="mono metadata mt-2 break-all">{agent.id}</p></div>
            <div className="flex flex-wrap items-start gap-2">
              {agent.status === 'pending_approval' && <ActionButton label="Approve" icon={<Play size={15} aria-hidden="true" />} onClick={() => void mutate('approve', agent)} loading={working === `approve:${agent.id}`} disabled={disabled || !canActivate(agent)} />}
              {agent.status === 'running' && <ActionButton label="Pause" icon={<Pause size={15} aria-hidden="true" />} onClick={() => void mutate('pause', agent)} loading={working === `pause:${agent.id}`} disabled={disabled} muted />}
              {agent.status === 'paused' && <ActionButton label="Resume" icon={<Play size={15} aria-hidden="true" />} onClick={() => void mutate('resume', agent)} loading={working === `resume:${agent.id}`} disabled={disabled || !canActivate(agent)} />}
              <button aria-label={`Remove ${agent.name}`} onClick={() => void mutate('remove', agent)} disabled={disabled} className="button-danger">{working === `remove:${agent.id}` ? <Loader2 size={16} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}</button>
            </div>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-[var(--border)] pt-4 lg:grid-cols-4"><RecordStat label="Configured traffic" value={`${agent.config.traffic_percentage}%`} /><RecordStat label="Output mode" value={`${agent.config.mode} mode`} /><RecordStat label="Human approval" value={agent.config.approval_required ? 'Required' : 'Not required'} /><RecordStat label="Recorded drafts" value={agent.metrics.drafts_created ?? 0} /></dl>
          <p className="metadata mt-4"><span className="font-medium text-[var(--text)]">Enabled steps: </span>{agent.config.enabled_steps.join(', ') || 'Default step selection'}</p>
          <p className="mono metadata mt-2 break-all">Created {agent.created_at}</p>
          {(agent.status === 'pending_approval' || agent.status === 'paused') && !canActivate(agent) && <p className="mt-3 text-sm text-[var(--warning)]">Approval and resume require draft or assisted mode with human approval enabled.</p>}
        </div>) : <p className="surface-pad muted text-sm">{loading ? 'Loading agent records…' : !hasLoaded ? 'Agent records could not be loaded.' : 'No pilot records have been created.'}</p>}
      </div>
    </section>
  </div>;
}

function PolicyRow({ label, value }: { label: string; value: string }) { return <div className="flex justify-between gap-4 py-2.5"><dt className="muted">{label}</dt><dd className="text-right font-medium">{value}</dd></div>; }
function RecordStat({ label, value }: { label: string; value: string | number }) { return <div><dt className="metadata">{label}</dt><dd className="mt-1 text-sm font-medium tabular-nums">{value}</dd></div>; }
function ActionButton({ label, icon, onClick, loading, disabled, muted = false }: { label: string; icon: ReactNode; onClick: () => void; loading: boolean; disabled: boolean; muted?: boolean }) {
  return <button onClick={onClick} disabled={disabled} aria-busy={loading} className={muted ? 'button-secondary' : 'button-primary'}>{loading ? <Loader2 size={15} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : icon}{label}</button>;
}
