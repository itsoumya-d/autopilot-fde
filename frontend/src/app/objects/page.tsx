'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { ErrorState, PageHeader, SourceLabel } from '@/components/Workspace';
import { objectsOfType, totalEvents, totalObjects, traceFor, type ObjectLog } from '@/lib/objectLens';

export default function Objects() {
  const [log, setLog] = useState<ObjectLog | null>(null);
  const [error, setError] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedId, setSelectedId] = useState('');

  useEffect(() => {
    let current = true;
    api.objectLog()
      .then(response => { if (current) setLog(response as unknown as ObjectLog); })
      .catch((reason: Error) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, []);

  const typeNames = useMemo(() => log ? log.objectTypes.map(type => type.name) : [], [log]);
  const visibleObjects = useMemo(() => objectsOfType(log, typeFilter), [log, typeFilter]);
  const trace = useMemo(() => traceFor(log, selectedId), [log, selectedId]);
  const selectedObject = log?.objects.find(object => object.id === selectedId);

  function filterByType(type: string) {
    setTypeFilter(type);
    // A detail view must never outlive the filter that made its object visible.
    if (!objectsOfType(log, type).some(object => object.id === selectedId)) setSelectedId('');
  }

  return <div className="page-stack">
    <PageHeader title="Object Lens" description="Follow one object across connected events. Inspect its relationships, chronology, and source evidence together." />
    {error && <ErrorState>{error}</ErrorState>}
    {log && <>
      <div className="ledger">
        <Stat label="Objects" value={totalObjects(log)} /><Stat label="Events" value={totalEvents(log)} /><Stat label="Object types" value={log.objectTypes.length} /><Stat label="Event types" value={log.eventTypes.length} />
      </div>
      <section aria-labelledby="object-type-filter">
        <h2 id="object-type-filter" className="metadata mb-3">Filter by object type</h2>
        <div className="flex flex-wrap gap-2">
          <TypeChip label="all" active={typeFilter === 'all'} onClick={() => filterByType('all')} count={totalObjects(log)} />
          {typeNames.map(name => <TypeChip key={name} label={name} active={typeFilter === name} onClick={() => filterByType(name)} count={log.summaries[name]?.objects ?? 0} />)}
        </div>
      </section>
      <div className="workspace-grid items-start">
        <section className="surface min-w-0 overflow-hidden" aria-labelledby="object-register">
          <header className="surface-pad border-b border-[var(--border)]"><h2 id="object-register" className="text-lg font-semibold">Objects</h2><p className="metadata mt-1">Sorted by relationship count. Select an ID to inspect its trace.</p></header>
          <div role="region" aria-label="Objects table" tabIndex={0} className="overflow-x-auto">
            <table className="w-full min-w-[24rem] text-left text-sm">
              <thead className="bg-[var(--surface-subtle)] text-xs text-[var(--text-muted)]"><tr><th scope="col" className="px-5 py-3 font-medium">Object</th><th scope="col" className="px-4 py-3 font-medium">Type</th><th scope="col" className="px-4 py-3 text-right font-medium">Links</th></tr></thead>
              <tbody className="divide-y divide-[var(--border)]">
                {visibleObjects.map(object => <tr key={object.id} onClick={() => setSelectedId(object.id)} className={`cursor-pointer transition-colors ${selectedId === object.id ? 'bg-[var(--accent-soft)]' : 'hover:bg-[var(--canvas)]'}`}>
                  <td className="px-5 py-4"><button type="button" onClick={() => setSelectedId(object.id)} aria-pressed={selectedId === object.id} aria-controls="object-trace" title={object.id} className="mono max-w-[18rem] break-all rounded-sm text-left text-xs font-medium text-[var(--accent)]">{object.id}</button></td>
                  <td className="px-4 py-4 text-[var(--text-muted)]">{object.type}</td><td className="px-4 py-4 text-right tabular-nums">{object.relationships.length}</td>
                </tr>)}
                {!visibleObjects.length && <tr><td colSpan={3} className="p-6 text-sm text-[var(--text-muted)]">No objects of this type yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
        <aside id="object-trace" className="surface min-w-0">
          <header className="surface-pad border-b border-[var(--border)]">
            <SourceLabel>Object trace</SourceLabel>
            <h2 className="mt-3 break-all text-lg font-semibold">{selectedId || 'Select an object'}</h2>
            {selectedObject && <p className="metadata mt-2">{selectedObject.type} · {selectedObject.relationships.length} relationships · {trace.length} events</p>}
          </header>
          <div className="surface-pad">
            {!selectedId && <p className="muted text-sm leading-6">Select an object to see its chronological events.</p>}
            {selectedId && <>
              {selectedObject && selectedObject.relationships.length > 0 && <section className="mb-6" aria-label="Object relationships">
                <h3 className="metadata mb-2">Related objects</h3>
                <div className="space-y-2">{selectedObject.relationships.map((relation, index) => <p key={`${relation.objectId}-${relation.qualifier}-${index}`} className="text-xs"><span className="mono break-all">{relation.objectId}</span><span className="muted ml-2">{relation.qualifier}</span></p>)}</div>
              </section>}
              <h3 className="mb-4 text-sm font-semibold">Chronological events</h3>
              <ol className="evidence-list">
                {trace.map((event, index) => <li key={event.id} className="grid min-w-0 grid-cols-[24px_minmax(0,1fr)] gap-3 pb-6">
                  <span className="mono flex h-6 w-6 items-center justify-center rounded-full border border-[var(--border-control)] text-xs text-[var(--text-muted)]">{index + 1}</span>
                  <div className="min-w-0"><p className="text-sm font-semibold">{event.type}</p><time dateTime={event.time} className="mono metadata mt-1 block break-all">{event.time}</time>
                    {event.attributes.some(attribute => attribute.name === 'evidence') && <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">{String(event.attributes.find(attribute => attribute.name === 'evidence')?.value)}</p>}
                    <p className="mono metadata mt-3 break-all">Event {event.id}</p>
                    {event.relationships.filter(relation => relation.objectId !== selectedId).map((relation, relationIndex) => <p key={`${relation.objectId}-${relation.qualifier}-${relationIndex}`} className="metadata mt-1 break-all"><span className="mono">{relation.objectId}</span> · {relation.qualifier}</p>)}
                  </div>
                </li>)}
                {!trace.length && <li className="muted text-sm">No events touch this object.</li>}
              </ol>
            </>}
          </div>
        </aside>
      </div>
    </>}
    {!log && !error && <p role="status" className="muted">Loading object log…</p>}
  </div>;
}

function Stat({ label, value }: { label: string; value: number }) {
  return <div className="ledger-stat"><p className="metadata">{label}</p><p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p></div>;
}
function TypeChip({ label, count, active, onClick }: { label: string; count: number; active: boolean; onClick: () => void }) {
  return <button type="button" aria-pressed={active} onClick={onClick} className={`inline-flex min-h-11 items-center sm:min-h-9 gap-3 rounded-md border px-3 py-2 text-sm transition-colors ${active ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]' : 'border-[var(--border-control)] bg-[var(--surface)] text-[var(--text-muted)] hover:bg-[var(--surface-subtle)]'}`}>{label}<span className="text-xs tabular-nums">{count}</span></button>;
}
