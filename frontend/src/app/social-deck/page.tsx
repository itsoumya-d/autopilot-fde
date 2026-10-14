'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Copy, Check, Globe, Smartphone, Terminal, Monitor } from 'lucide-react';
import { ErrorState, PageHeader, SectionHeader, SourceLabel } from '@/components/Workspace';

const infographicPost = `UI Generation is NOT just Web Code.

Computer-use interfaces span Web DOM, SwiftUI, Jetpack Compose, and terminal UI. A cross-host evaluation concept can compare state, accessibility, visual parity, and interaction behavior.

HostShift concept preview. Any benchmark numbers shown in this studio are static examples, not current verified results.`;

const pitchSlides = [
  { num: '01', title: 'Begin with the evidence.', tag: 'Observe', desc: 'Reconstruct repeatable work from source-linked communication, then inspect the activities and confidence behind each workflow.', stat: '158 traces / static showcase example', tweet: 'Start with the evidence. AutoPilot explores source-linked workflow discovery and review. The 158-trace figure in this concept deck is a static example, not a current production result.' },
  { num: '02', title: 'Understand the variation.', tag: 'Review', desc: 'Use graph transition entropy as one input when examining operational unpredictability. An opportunity score is not permission to automate.', stat: '58.3–74.4 score range / example data', tweet: 'An automation score is a starting point for review. Explore graph transition entropy alongside workflow evidence and risk. Scores of 58.3–74.4 in this deck are static examples, not validated forecasts.' },
  { num: '03', title: 'Explore before expanding.', tag: 'Simulate', desc: 'Compare illustrative confidence thresholds and estimated straight-through rates. Local sandbox formulas do not establish real-world reliability.', stat: '56.2% straight-through rate / example', tweet: 'Explore before expanding. A simulation can make assumptions visible, but it cannot establish real-world safety. The 56.2% straight-through rate in this deck is illustrative example data.' },
  { num: '04', title: 'Keep a person in the loop.', tag: 'Pilot', desc: 'Prepare draft pilot records with explicit enabled steps and review policies. Creating or approving a record does not launch a live worker.', stat: 'Draft record → human review', tweet: 'Keep a person in the loop. AutoPilot prepares draft pilot records with enabled steps and review policies. Creating or approving a record does not launch a live worker. Review the evidence before any rollout.' },
  { num: '05', title: 'Make the proof inspectable.', tag: 'Measure', desc: 'Separate recorded activity from example charts. Check actual test artifacts, provenance, and operational outcomes before publishing performance claims.', stat: '142/142 tests / historical showcase claim', tweet: 'Make the proof inspectable. Separate recorded activity from example charts, and link claims to actual evidence. The 142/142 test count in this concept deck is a historical showcase claim, not a current verified CI result.' },
];

const formats = [
  { id: 'infographic', label: '1. HostShift: Multi-Host Infographic', short: 'Infographic' },
  { id: 'editorial', label: '2. AutoPilot FDE: 4-Panel Editorial', short: '4-panel editorial' },
  { id: 'carousel', label: '3. 5-Slide Master Pitch Deck', short: 'Pitch deck' },
] as const;

export default function SocialDeckPage() {
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);
  const [copyingIndex, setCopyingIndex] = useState<string | null>(null);
  const [copyError, setCopyError] = useState('');
  const copyRequest = useRef(0);
  const copyTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    copyRequest.current += 1;
    if (copyTimeout.current !== null) clearTimeout(copyTimeout.current);
  }, []);
  const [activeTheme, setActiveTheme] = useState<'infographic' | 'editorial' | 'carousel'>('infographic');

  const copyToClipboard = async (text: string, id: string) => {
    const request = ++copyRequest.current;
    if (copyTimeout.current !== null) clearTimeout(copyTimeout.current);
    setCopiedIndex(null);
    setCopyError('');
    setCopyingIndex(id);
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(text);
      if (request !== copyRequest.current) return;
      setCopiedIndex(id);
      copyTimeout.current = setTimeout(() => {
        setCopiedIndex(null);
        copyTimeout.current = null;
      }, 2000);
    } catch {
      if (request === copyRequest.current) setCopyError('Could not copy to the clipboard. Try again or copy the text manually.');
    } finally {
      if (request === copyRequest.current) setCopyingIndex(null);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Studio / Social Studio" title="Social Studio" description="Preview three content layouts and copy their accompanying text. Review example claims before sharing." />
      <div className="flex flex-wrap items-center justify-between gap-4 border-y border-[var(--border)] py-4">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Content format">{formats.map(tab => <button key={tab.id} type="button" aria-label={tab.label} aria-pressed={activeTheme === tab.id} onClick={() => setActiveTheme(tab.id)} className={activeTheme === tab.id ? 'button-primary' : 'button-secondary'}>{tab.short}</button>)}</div>
        <SourceLabel>Local content preview · No publishing</SourceLabel>
      </div>
      {copyError && <ErrorState>{copyError}</ErrorState>}
      <p role="status" className="sr-only">{copyingIndex ? 'Copying to clipboard…' : copiedIndex ? 'Copied to clipboard.' : ''}</p>

      {activeTheme === 'infographic' && <div className="workspace-grid">
        <section className="surface surface-pad" aria-label="Infographic preview">
          <div className="flex flex-wrap justify-between gap-3 border-b border-[var(--border)] pb-4"><span className="font-semibold tracking-tight">HostShift</span><SourceLabel>Concept / 01</SourceLabel></div>
          <h2 className="my-8 max-w-lg text-3xl font-semibold leading-tight tracking-tight">UI Generation is <span className="text-[var(--accent)]">NOT</span> just Web Code.</h2>
          <p className="muted max-w-xl text-sm">A cross-host evaluation concept: inspect how an interface behaves across the environments people actually use.</p>
          <div className="mt-8 grid grid-cols-1 gap-0 min-[480px]:grid-cols-2">
            {[
              { title: 'Web', language: 'DOM / HTML / CSS', icon: Globe },
              { title: 'iOS & macOS', language: 'SwiftUI', icon: Monitor },
              { title: 'Android', language: 'Jetpack Compose', icon: Smartphone },
              { title: 'Terminal', language: 'CLI / TUI', icon: Terminal },
            ].map((host, index) => <div key={host.title} className="border-t border-[var(--border)] py-5 pr-4"><div className="mb-4 flex items-center gap-3"><host.icon size={19} className="text-[var(--accent)]" aria-hidden="true" /><span className="mono metadata">0{index + 1}</span></div><h3 className="text-lg">{host.title}</h3><p className="mono metadata mt-1">{host.language}</p></div>)}
          </div>
          <div className="mt-3 border-t-2 border-[var(--text)] pt-5"><h3 className="mb-3">What to compare</h3><ul className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2"><li>State oracles</li><li>Accessibility trees</li><li>Visual parity</li><li>Interaction behavior</li><li>Deterministic grading</li><li>Task coverage</li></ul></div>
          <p className="metadata mt-6 border-t border-[var(--border)] pt-4">Source: static concept content. This preview does not verify benchmark coverage or test results.</p>
        </section>
        <aside className="inspector" aria-label="Post copy tools">
          <SectionHeader title="Accompanying post" actions={<button type="button" disabled={copyingIndex === 'infographic-text'} onClick={() => copyToClipboard(infographicPost, 'infographic-text')} className="button-secondary shrink-0">{copiedIndex === 'infographic-text' ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}<span>{copyingIndex === 'infographic-text' ? 'Copying…' : copiedIndex === 'infographic-text' ? 'Copied!' : 'Copy Post'}</span></button>} />
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{infographicPost}</p>
          <p className="metadata mt-6 border-t border-[var(--border)] pt-4">Copies text only. Nothing is exported, scheduled, or posted.</p>
        </aside>
      </div>}

      {activeTheme === 'editorial' && <section aria-label="Four-panel editorial preview">
        <SectionHeader title="Evidence before automation" description="A four-panel narrative, arranged as a single editorial sequence." actions={<SourceLabel>AutoPilot / concept layout</SourceLabel>} />
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">{[
          { num: '01', title: 'Bring the work into focus.', body: 'Start with the recurring requests and handoffs in operational communication.', caption: 'Observe / source-linked records' },
          { num: '02', title: 'Make evidence the priority.', body: 'Inspect the activities, relationships, and confidence behind a workflow before judging its automation potential.', caption: 'Review / inspect the source' },
          { num: '03', title: 'Keep assumptions visible.', body: 'Use illustrative simulations to explore a scenario. Keep example rates and estimated savings separate from measured outcomes.', caption: 'Explore / example data is labeled' },
          { num: '04', title: 'Prepare a reviewed pilot.', body: 'Choose eligible steps and review policies. A draft record does not start a live worker or authorize an external action.', caption: 'Pilot / permission stays explicit' },
        ].map(panel => <article key={panel.num} className="surface flex min-h-[280px] flex-col p-6 sm:p-8"><div className="flex justify-between gap-4 border-b border-[var(--border)] pb-4"><span className="text-xs font-semibold">AutoPilot</span><span className="mono metadata">{panel.num} / 04</span></div><h3 className="mb-4 mt-7 max-w-sm text-3xl font-semibold leading-tight tracking-tight">{panel.title}</h3><p className="muted max-w-sm text-sm">{panel.body}</p><p className="mt-auto pt-6 text-xs font-medium text-[var(--accent)]">{panel.caption}</p></article>)}</div>
        <p className="metadata mt-4">Static editorial concept. No current benchmark, customer outcome, or production deployment is represented.</p>
      </section>}

      {activeTheme === 'carousel' && <section aria-label="Five-slide carousel preview" className="space-y-5">
        <SectionHeader title="A five-slide operating story" description="Each slide has an accompanying short post. Example metrics are labeled in both the preview and copied text." actions={<SourceLabel>Concept deck / 5 slides</SourceLabel>} />
        {pitchSlides.map((slide, idx) => <article key={slide.num} className="surface overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-3"><span className="metadata"><span className="mono mr-2">{slide.num} / 05</span>{slide.tag}</span><button type="button" disabled={copyingIndex === `slide-${idx}`} onClick={() => copyToClipboard(slide.tweet, `slide-${idx}`)} className="button-secondary">{copiedIndex === `slide-${idx}` ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}<span>{copyingIndex === `slide-${idx}` ? 'Copying…' : copiedIndex === `slide-${idx}` ? 'Copied Tweet!' : 'Copy 280-char Tweet'}</span></button></div>
          <div className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] sm:p-8"><div><p className="page-kicker">AutoPilot / concept preview</p><h3 className="mb-4 text-3xl font-semibold leading-tight tracking-tight">{slide.title}</h3><p className="muted max-w-xl text-sm">{slide.desc}</p><p className="mono mt-6 border-t border-[var(--border)] pt-4 text-xs">{slide.stat}</p></div><div className="border-t border-[var(--border)] pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0"><p className="metadata mb-3">Accompanying post · {slide.tweet.length}/280 characters</p><p className="text-sm leading-relaxed">{slide.tweet}</p></div></div>
        </article>)}
      </section>}
    </div>
  );
}
