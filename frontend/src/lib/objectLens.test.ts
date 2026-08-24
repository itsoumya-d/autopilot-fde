import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  colorFor,
  objectsOfType,
  totalEvents,
  totalObjects,
  traceFor,
  type ObjectLog,
} from './objectLens';

const log: ObjectLog = {
  ocel_version: '2.0-inspired',
  eventTypes: [{ name: 'Invoice reconciled' }],
  events: [
    { id: 'e2', type: 'Payment confirmed', time: '2026-08-24T10:05:00Z', attributes: [], relationships: [{ objectId: 'case:c2', qualifier: 'case' }] },
    { id: 'e1', type: 'Invoice received', time: '2026-08-24T10:00:00Z', attributes: [], relationships: [{ objectId: 'vendor:acme', qualifier: 'vendor' }, { objectId: 'case:c1', qualifier: 'case' }] },
    { id: 'e3', type: 'Invoice reconciled', time: '2026-08-24T10:02:00Z', attributes: [], relationships: [{ objectId: 'vendor:acme', qualifier: 'vendor' }] },
  ],
  objectTypes: [{ name: 'vendor' }, { name: 'case' }],
  objects: [
    { id: 'vendor:acme', type: 'vendor', relationships: [{ objectId: 'case:c1', qualifier: 'co' }, { objectId: 'case:c2', qualifier: 'x' }] },
    { id: 'case:c1', type: 'case', relationships: [] },
    { id: 'case:c2', type: 'case', relationships: [] },
  ],
  summaries: { vendor: { objects: 1, events_touching: 2 } },
};

describe('objectLens helpers', () => {
  afterEach(() => vi.restoreAllMocks());

  it('colorFor falls back to slate for unknown types', () => {
    expect(colorFor('vendor')).toBe('bg-emerald-400');
    expect(colorFor('spaceship')).toBe('bg-slate-400');
  });

  it('objectsOfType filters and sorts by relationship count desc', () => {
    const cases = objectsOfType(log, 'case');
    expect(cases.map((o) => o.id)).toEqual(['case:c1', 'case:c2']);
    const all = objectsOfType(log, 'all');
    expect(all[0].id).toBe('vendor:acme'); // 2 links beats 0
  });

  it('traceFor returns only touching events, chronologically sorted', () => {
    const trace = traceFor(log, 'vendor:acme');
    expect(trace.map((e) => e.id)).toEqual(['e1', 'e3']); // e2 excluded; e1 before e3
  });

  it('totals are zero-safe for null logs', () => {
    expect(totalObjects(null)).toBe(0);
    expect(totalEvents(null)).toBe(0);
    expect(objectsOfType(null, 'all')).toEqual([]);
    expect(traceFor(null, 'x')).toEqual([]);
  });
});
