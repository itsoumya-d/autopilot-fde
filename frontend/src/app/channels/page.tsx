'use client';

import { useEffect, useState } from 'react';
import { api, Channel } from '@/lib/api';
import { EmptyState, ErrorState, PageHeader, SectionHeader, SourceLabel, StatusBadge } from '@/components/Workspace';

const channelStatuses = {
  active: { label: 'Active', tone: 'success' as const },
  inactive: { label: 'Inactive', tone: 'neutral' as const },
  error: { label: 'Error', tone: 'danger' as const },
};
const serviceNames: Record<Channel['type'], string> = { slack: 'Slack', whatsapp: 'WhatsApp', email: 'Email', call: 'Call' };

export default function Channels() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    api.channels()
      .then(items => { if (active) setChannels(items); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Unable to load channel information.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return <div className="page-stack">
    <PageHeader eyebrow="Workspace / Sources" title="Observation sources" description="Review the sources behind discovery. Connection status and access mode are reported separately." />
    {error && <ErrorState>{error}</ErrorState>}
    <section className="surface" aria-label="Source register" aria-busy={loading}>
      <div className="surface-pad border-b border-[var(--border)]">
        <SectionHeader title="Source register" description="Available observations and reported access" />
      </div>
      {channels.length > 0 && <div className="register divide-y divide-[var(--border)]">
        {channels.map(channel => {
          const status = channelStatuses[channel.status];
          // ChannelPublic currently omits scope; do not infer it from connection status.
          const scope = channel.read_only === true ? 'Read-only' : channel.read_only === false ? 'Not read-only' : 'Not reported';
          return <article key={channel.id} aria-label={channel.name} className="register-row grid min-w-0 gap-x-6 gap-y-4 p-5 sm:grid-cols-2 xl:grid-cols-[minmax(0,1.8fr)_1fr_1fr_1fr]">
            <div className="min-w-0">
              <p className="metadata mb-1">{serviceNames[channel.type] ?? channel.type}</p>
              <h3 className="break-words text-base font-semibold">{channel.name}</h3>
              <p className="mono metadata mt-2 break-all">{channel.id}</p>
            </div>
            <div><p className="metadata mb-2">Status</p><StatusBadge tone={status.tone}>{status.label}</StatusBadge></div>
            <div><p className="metadata mb-1">Observed messages</p><p className="text-lg font-semibold tabular-nums">{channel.message_count}</p></div>
            <div><p className="metadata mb-2">Access mode</p><p className="text-sm">{scope}</p></div>
          </article>;
        })}
      </div>}
      {loading && <p role="status" className="surface-pad muted">Loading channel information…</p>}
      {!loading && !channels.length && !error && <EmptyState title="No observation sources connected yet.">Configure a source before running workflow discovery.</EmptyState>}
      {!loading && error && !channels.length && <p className="surface-pad muted">Source details are unavailable. Reload this page to try again.</p>}
    </section>
    <div className="grid gap-8 lg:grid-cols-2">
      <section className="border-t border-[var(--border)] pt-5">
        <SourceLabel>Read-only discovery</SourceLabel>
        <h2 className="mt-3 text-lg font-semibold">Data handling boundary</h2>
        <p className="mt-2 max-w-prose text-sm leading-6 text-[var(--text-muted)]">The MVP reads Slack messages and thread relationships. Discovery retains source IDs and evidence snippets for review. Agents receive no Slack write permissions; the register shows access information only when the API reports it.</p>
      </section>
      <section className="border-t border-[var(--border)] pt-5">
        <SourceLabel>Planned · unavailable</SourceLabel>
        <h2 className="mt-3 text-lg font-semibold">Next integrations</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">Shared inbox and CRM connectors are deferred until the Slack evidence and approval workflow are validated.</p>
        <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-[var(--text-muted)]">{['Shared Gmail / Outlook', 'CRM webhooks', 'Call transcripts'].map(item => <li key={item}>{item}</li>)}</ul>
      </section>
    </div>
  </div>;
}
