'use client';

import { useEffect, useMemo, useState } from 'react';
import { Boxes, Clock, Link2, Network } from 'lucide-react';
import { api } from '@/lib/api';
import {
  colorFor,
  objectsOfType,
  totalEvents,
  totalObjects,
  traceFor,
  type ObjectLog,
} from '@/lib/objectLens';

export default function Objects() {
  const [log, setLog] = useState<ObjectLog | null>(null);
  const [error, setError] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedId, setSelectedId] = useState('');

  useEffect(() => {
    api
      .objectLog()
      .then((response) => setLog(response as unknown as ObjectLog))
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const typeNames = useMemo(
    () => (log ? log.objectTypes.map((t) => t.name) : []),
    [log],
  );
  const visibleObjects = useMemo(() => objectsOfType(log, typeFilter), [log, typeFilter]);
  const trace = useMemo(() => traceFor(log, selectedId), [log, selectedId]);

  return (
    <div className="max-w-7xl mx-auto space-y-7">
      <header>
        <div className="flex items-center gap-2 text-sm text-cyan-300">
          <Network size={16} /> Objects intersect where single-case views collapse
        </div>
        <h1 className="mt-2 text-3xl font-bold">Object Lens</h1>
        <p className="mt-1 text-slate-400">
          Multi-object event log: every mined event references typed objects with
          qualified relationships. Click an object to walk its chronology.
        </p>
      </header>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">
          {error}
        </div>
      )}

      {log && (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <StatCard icon={<Boxes size={18} className="text-cyan-300" />} label="Objects" value={totalObjects(log)} />
            <StatCard icon={<Clock size={18} className="text-violet-300" />} label="Events" value={totalEvents(log)} />
            <StatCard icon={<Link2 size={18} className="text-emerald-300" />} label="Object types" value={log.objectTypes.length} />
            <StatCard icon={<Network size={18} className="text-fuchsia-300" />} label="Event types" value={log.eventTypes.length} />
          </div>

          <section className="glass-card rounded-2xl p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Object types
            </h2>
            <div className="mt-3 flex flex-wrap gap-3">
              <TypeChip label="all" active={typeFilter === 'all'} onClick={() => setTypeFilter('all')} count={totalObjects(log)} />
              {typeNames.map((name) => (
                <TypeChip
                  key={name}
                  label={name}
                  dot={colorFor(name)}
                  active={typeFilter === name}
                  onClick={() => setTypeFilter(name)}
                  count={log.summaries[name]?.objects ?? 0}
                />
              ))}
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-[1.35fr_0.95fr]">
            <section className="glass-card overflow-hidden rounded-2xl">
              <header className="border-b border-slate-800 p-5">
                <h2 className="text-lg font-semibold">Objects</h2>
                <p className="text-xs text-slate-500">Sorted by relationship count.</p>
              </header>
              <table className="w-full text-left">
                <thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="p-4">Object</th>
                    <th className="p-4">Type</th>
                    <th className="p-4">Links</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {visibleObjects.map((object) => (
                    <tr
                      key={object.id}
                      onClick={() => setSelectedId(object.id)}
                      className={`cursor-pointer transition-colors hover:bg-slate-800/50 ${
                        selectedId === object.id ? 'bg-cyan-500/5' : ''
                      }`}
                    >
                      <td className="p-4 font-mono text-sm">{object.id}</td>
                      <td className="p-4">
                        <span className="inline-flex items-center gap-2 text-sm text-slate-300">
                          <span className={`inline-block h-2.5 w-2.5 rounded-full ${colorFor(object.type)}`} />
                          {object.type}
                        </span>
                      </td>
                      <td className="p-4 text-slate-300">{object.relationships.length}</td>
                    </tr>
                  ))}
                  {!visibleObjects.length && (
                    <tr><td colSpan={3} className="p-6 text-center text-slate-500">No objects of this type yet.</td></tr>
                  )}
                </tbody>
              </table>
            </section>

            <aside className="glass-card rounded-2xl p-6">
              <h2 className="text-lg font-semibold">Object trace</h2>
              {!selectedId && (
                <p className="mt-3 text-sm text-slate-400">
                  Select an object to see its chronological events.
                </p>
              )}
              {selectedId && (
                <>
                  <p className="mt-2 font-mono text-xs text-cyan-300">{selectedId}</p>
                  <ol className="mt-4 space-y-3">
                    {trace.map((event) => (
                      <li key={event.id} className="rounded-lg bg-slate-900/70 p-3">
                        <p className="font-medium">{event.type}</p>
                        <p className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                          <Clock size={12} /> {event.time}
                        </p>
                        {event.attributes.some((a) => a.name === 'evidence') && (
                          <p className="mt-2 line-clamp-2 text-xs text-slate-400">
                            {String(event.attributes.find((a) => a.name === 'evidence')?.value)}
                          </p>
                        )}
                      </li>
                    ))}
                    {!trace.length && <li className="text-sm text-slate-500">No events touch this object.</li>}
                  </ol>
                </>
              )}
            </aside>
          </div>
        </>
      )}

      {!log && !error && <p className="text-slate-400">Loading object log…</p>}
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="glass-card rounded-2xl p-5">
      <div className="flex items-center gap-2 text-slate-400">{icon}<span className="text-xs uppercase tracking-wider">{label}</span></div>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function TypeChip({ label, count, active, onClick, dot }: {
  label: string; count: number; active: boolean; onClick: () => void; dot?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors ${
        active ? 'border-cyan-400/60 bg-cyan-500/10 text-cyan-200' : 'border-slate-700 text-slate-300 hover:border-slate-500'
      }`}
    >
      {dot && <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />}
      {label}
      <span className="rounded-full bg-slate-800 px-2 text-xs">{count}</span>
    </button>
  );
}
