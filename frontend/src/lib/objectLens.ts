// Object Lens: typed helpers over the OCEL-shaped object log (v0.9 backend).
// Pure functions so the page stays thin and the logic is unit-testable.

export interface EventRelationship {
  objectId: string;
  qualifier: string;
}

export interface OcelEvent {
  id: string;
  type: string;
  time: string;
  attributes: Array<{ name: string; type: string; value: unknown }>;
  relationships: EventRelationship[];
}

export interface OcelObject {
  id: string;
  type: string;
  relationships: EventRelationship[];
}

export interface ObjectTypeSpec {
  name: string;
}

export interface TypeSummary {
  objects: number;
  events_touching: number;
}

export interface ObjectLog {
  ocel_version: string;
  eventTypes: ObjectTypeSpec[];
  events: OcelEvent[];
  objectTypes: ObjectTypeSpec[];
  objects: OcelObject[];
  summaries: Record<string, TypeSummary>;
}

export const TYPE_COLORS: Record<string, string> = {
  case: 'bg-cyan-400',
  actor: 'bg-violet-400',
  ticket: 'bg-amber-400',
  vendor: 'bg-emerald-400',
  amount: 'bg-fuchsia-400',
  'email-domain': 'bg-sky-400',
};

export function colorFor(type: string): string {
  return TYPE_COLORS[type] || 'bg-slate-400';
}

export function objectsOfType(log: ObjectLog | null, type: string): OcelObject[] {
  if (!log) return [];
  const filtered = type === 'all' ? log.objects : log.objects.filter((o) => o.type === type);
  return [...filtered].sort(
    (a, b) => b.relationships.length - a.relationships.length || a.id.localeCompare(b.id),
  );
}

export function traceFor(log: ObjectLog | null, objectId: string): OcelEvent[] {
  if (!log) return [];
  return log.events
    .filter((event) => event.relationships.some((rel) => rel.objectId === objectId))
    .sort((a, b) => a.time.localeCompare(b.time));
}

export function totalObjects(log: ObjectLog | null): number {
  return log ? log.objects.length : 0;
}

export function totalEvents(log: ObjectLog | null): number {
  return log ? log.events.length : 0;
}
