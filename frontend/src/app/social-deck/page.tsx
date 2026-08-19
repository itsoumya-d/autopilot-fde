'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { 
  Share2, 
  Copy, 
  Check, 
  ArrowRight, 
  Sparkles, 
  Layers, 
  Terminal, 
  Activity, 
  ShieldCheck, 
  CheckCircle2, 
  XCircle,
  Smartphone,
  Globe,
  Monitor,
  Code2
} from 'lucide-react';

export default function SocialDeckPage() {
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);
  const [activeTheme, setActiveTheme] = useState<'infographic' | 'editorial' | 'carousel'>('infographic');

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(id);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="max-w-7xl mx-auto py-10 px-4 sm:px-6 lg:px-8 text-slate-900 bg-slate-50 min-h-screen">
      {/* Top Header */}
      <div className="text-center max-w-4xl mx-auto mb-12">
        <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-1.5 text-sm text-blue-700 font-semibold mb-4 shadow-sm">
          <Sparkles size={16} className="text-blue-600" />
          <span>Vector-Sharp Social Media Design Studio</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-black tracking-tight text-slate-900 mb-4">
          Pixel-Perfect Social Carousel & Infographics
        </h1>
        <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto">
          Clean vector graphics, sharp typography, zero AI image glitches. Ready for high-resolution screenshots, LinkedIn posts, and 280-char X tweets.
        </p>
      </div>

      {/* Theme Switcher Tabs */}
      <div className="flex justify-center gap-3 mb-12">
        {[
          { id: 'infographic', label: '1. HostShift: Multi-Host Infographic' },
          { id: 'editorial', label: '2. AutoPilot FDE: 4-Panel Editorial' },
          { id: 'carousel', label: '3. 5-Slide Master Pitch Deck' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTheme(tab.id as any)}
            className={`px-5 py-3 rounded-xl font-bold text-sm transition shadow-sm ${
              activeTheme === tab.id
                ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20 scale-105'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* THEME 1: HOSTSHIFT MULTI-HOST BALLOON INFOGRAPHIC */}
      {activeTheme === 'infographic' && (
        <div className="space-y-12 max-w-4xl mx-auto">
          {/* Card Frame (Exact Replica of Reference 2) */}
          <div className="bg-white rounded-3xl p-10 border-2 border-slate-200 shadow-2xl relative overflow-hidden">
            {/* Header */}
            <div className="text-center mb-10">
              <h2 className="text-4xl sm:text-6xl font-black tracking-tight text-slate-950">
                UI Generation is <span className="text-blue-600">NOT</span> just Web Code.
              </h2>
              <div className="w-24 h-1.5 bg-blue-600 rounded-full mx-auto mt-4" />
            </div>

            {/* Main Visual Comparison */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-end py-8 border-b border-slate-100">
              {/* Left Side: Single Web Balloon */}
              <div className="flex flex-col items-center">
                {/* Blue Balloon */}
                <div className="w-36 h-44 rounded-[50%] bg-gradient-to-b from-blue-500 to-blue-600 text-white flex flex-col items-center justify-center p-4 shadow-lg text-center relative mb-4">
                  <Globe size={28} className="mb-2 text-white/90" />
                  <span className="font-bold text-sm leading-tight">Basic Web DOM</span>
                  <span className="text-[10px] text-blue-100 mt-1">HTML / CSS</span>
                  {/* Balloon String */}
                  <div className="w-0.5 h-16 bg-slate-400 absolute -bottom-16 left-1/2 -translate-x-1/2" />
                  <div className="w-3 h-2 bg-blue-700 absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-b-sm" />
                </div>

                {/* Left 3D Label */}
                <div className="mt-16 text-center">
                  <div className="text-5xl font-black tracking-widest text-slate-800 border-b-4 border-slate-300 pb-1">
                    WEB
                  </div>
                  <div className="mt-4 flex items-center justify-center gap-1 text-slate-500 font-bold text-sm">
                    <XCircle size={16} className="text-rose-500" />
                    <span>Just Surface DOM</span>
                  </div>
                </div>
              </div>

              {/* Right Side: Rich Multi-Host Balloon Bouquet */}
              <div className="flex flex-col items-center">
                {/* Bouquet Grid */}
                <div className="relative w-full max-w-sm h-64 flex flex-wrap justify-center items-center gap-2 p-2">
                  {[
                    { label: 'SwiftUI Native', color: 'bg-blue-600 text-white', icon: Smartphone },
                    { label: 'Jetpack Compose', color: 'bg-lime-400 text-slate-900', icon: Smartphone },
                    { label: 'Terminal CLI / TUI', color: 'bg-slate-800 text-white', icon: Terminal },
                    { label: 'State Oracle', color: 'bg-blue-500 text-white', icon: Activity },
                    { label: 'Accessibility Tree', color: 'bg-blue-700 text-white', icon: ShieldCheck },
                    { label: 'Visual Parity', color: 'bg-slate-600 text-white', icon: Monitor },
                    { label: 'Interaction Harness', color: 'bg-lime-500 text-slate-950', icon: Layers },
                    { label: '100 Tasks Suite', color: 'bg-blue-600 text-white', icon: CheckCircle2 },
                    { label: 'Deterministic Grading', color: 'bg-lime-400 text-slate-950', icon: Sparkles },
                  ].map((balloon, i) => {
                    const Icon = balloon.icon;
                    return (
                      <div
                        key={i}
                        className={`px-3 py-2 rounded-full font-bold text-xs flex items-center gap-1.5 shadow-md transform hover:scale-110 transition cursor-default ${balloon.color}`}
                      >
                        <Icon size={12} />
                        <span>{balloon.label}</span>
                      </div>
                    );
                  })}
                  {/* Tie Strings to bottom */}
                  <div className="w-0.5 h-12 bg-slate-400 absolute -bottom-12 left-1/2 -translate-x-1/2" />
                </div>

                {/* Right 3D Label */}
                <div className="mt-12 text-center">
                  <div className="text-5xl font-black tracking-widest text-blue-600 border-b-4 border-blue-600 pb-1">
                    MULTI-HOST
                  </div>
                  <div className="mt-4 flex items-center justify-center gap-1 text-emerald-600 font-bold text-sm">
                    <CheckCircle2 size={16} className="text-emerald-500" />
                    <span>HostShift: True Cross-Host Parity</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Insight Footer */}
            <div className="mt-8 text-center text-sm font-medium text-slate-700 leading-relaxed max-w-2xl mx-auto">
              Real computer-use AI models are evaluated on <strong className="text-blue-600">SwiftUI</strong>, <strong className="text-lime-600">Jetpack Compose</strong>, <strong className="text-slate-900">Terminal CLI</strong>, <strong className="text-blue-600">State Oracles</strong>, <strong className="text-lime-600">Accessibility</strong>, and <strong className="text-blue-600">Deterministic Parity</strong> — not just isolated browser HTML.
            </div>
          </div>

          {/* Ready-to-Copy Post Text */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-md">
            <div className="flex justify-between items-center mb-3">
              <span className="font-bold text-sm text-slate-800">Copy Post for LinkedIn / X</span>
              <button
                onClick={() => copyToClipboard(
                  `UI Generation is NOT just Web Code.\n\nMost benchmarks evaluate AI on basic HTML/CSS. But real computer-use agents must operate across:\n- SwiftUI (iOS & macOS)\n- Jetpack Compose (Android)\n- Terminal CLI / TUI\n- Web DOM\n\nIntroducing HostShift: 100 UI tasks, 142/142 CI unit tests, deterministic state oracles.\n\nCode: https://github.com/your-username/hostshift\n\n@sama @OriolVinyalsML @demishassabis`,
                  'infographic-text'
                )}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 text-blue-600 font-semibold text-xs hover:bg-blue-100 transition"
              >
                {copiedIndex === 'infographic-text' ? <Check size={14} /> : <Copy size={14} />}
                <span>{copiedIndex === 'infographic-text' ? 'Copied!' : 'Copy Post'}</span>
              </button>
            </div>
            <p className="text-xs text-slate-600 font-mono bg-slate-50 p-4 rounded-xl border border-slate-200">
              UI Generation is NOT just Web Code.<br/><br/>
              Most benchmarks evaluate AI on basic HTML/CSS. But real computer-use agents must operate across:<br/>
              • SwiftUI (iOS & macOS)<br/>
              • Jetpack Compose (Android)<br/>
              • Terminal CLI / TUI<br/>
              • Web DOM<br/><br/>
              Introducing HostShift: 100 UI tasks, 142/142 CI unit tests, deterministic state oracles.<br/><br/>
              Code: https://github.com/your-username/hostshift<br/>
              @sama @OriolVinyalsML @demishassabis
            </p>
          </div>
        </div>
      )}

      {/* THEME 2: AUTOPILOT FDE 4-PANEL EDITORIAL STORYBOARD */}
      {activeTheme === 'editorial' && (
        <div className="space-y-12 max-w-4xl mx-auto">
          {/* 4-Panel Grid (Exact Replica of Reference 1) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Panel 1: Top-Left (Chaos & Stress) */}
            <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-xl flex flex-col justify-between min-h-[340px] relative overflow-hidden">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full border-2 border-indigo-600 flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-indigo-600" />
                </div>
                <span className="font-bold text-xs tracking-wider text-slate-800">AutoPilot FDE</span>
              </div>

              <div className="my-6">
                <h3 className="text-3xl font-black text-slate-900 leading-tight">
                  Take the <span className="relative inline-block px-2 text-indigo-700 border-2 border-indigo-500 rounded-full">chaos</span> out of your Operations.
                </h3>
                <p className="text-xs text-slate-500 mt-3">Drowning in hundreds of manual Slack, WhatsApp, and email requests every day?</p>
              </div>

              {/* Stress Character Line Art */}
              <div className="flex justify-center">
                <div className="w-20 h-20 rounded-full bg-indigo-100 flex items-center justify-center text-3xl">
                  🤯
                </div>
              </div>
            </div>

            {/* Panel 2: Top-Right (Inverted Dark Contrast) */}
            <div className="bg-slate-950 rounded-3xl p-8 border border-slate-800 shadow-xl text-white flex flex-col justify-between min-h-[340px] relative overflow-hidden">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full border-2 border-indigo-400 flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-indigo-400" />
                </div>
                <span className="font-bold text-xs tracking-wider text-slate-200">AutoPilot FDE</span>
              </div>

              <div className="my-6">
                <h3 className="text-3xl font-black leading-tight text-white">
                  Make <span className="text-indigo-400 border-b-2 border-indigo-400">evidence</span> your priority.
                </h3>
                <p className="text-xs text-slate-400 mt-3">We quantify operational readiness using Graph Shannon Transition Entropy, not guesswork.</p>
              </div>

              <div className="flex justify-center">
                <div className="px-4 py-2 rounded-xl bg-indigo-950/80 border border-indigo-800/60 font-mono text-xs text-indigo-300">
                  H(p) = -∑ P(u→v) log2 P(u→v)
                </div>
              </div>
            </div>

            {/* Panel 3: Bottom-Left (Solid Lavender Accent) */}
            <div className="bg-indigo-600 rounded-3xl p-8 shadow-xl text-white flex flex-col justify-between min-h-[340px]">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full border-2 border-white flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-white" />
                </div>
                <span className="font-bold text-xs tracking-wider text-white">AutoPilot FDE</span>
              </div>

              <div className="my-6 text-center">
                <h3 className="text-4xl font-black leading-tight">
                  Automation comes after proof.
                </h3>
                <p className="text-xs text-indigo-100 mt-3">1,000 Monte Carlo execution runs forecast Straight-Through Rates before any deployment.</p>
              </div>

              <div className="flex justify-center text-3xl">
                🛡️ ➔ 🚀
              </div>
            </div>

            {/* Panel 4: Bottom-Right (Peaceful Relief) */}
            <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-xl flex flex-col justify-between min-h-[340px]">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full border-2 border-indigo-600 flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-indigo-600" />
                </div>
                <span className="font-bold text-xs tracking-wider text-slate-800">AutoPilot FDE</span>
              </div>

              <div className="my-6">
                <h3 className="text-3xl font-black text-slate-900 leading-tight">
                  Get the <span className="border-b-2 border-slate-900">autonomous help</span> you need.
                </h3>
                <p className="text-xs text-slate-500 mt-3">Self-deploying LangGraph copilots with Human-in-the-Loop review gates.</p>
              </div>

              <div className="flex justify-center">
                <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center text-3xl">
                  😌✨
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* THEME 3: 5-SLIDE MASTER PITCH DECK */}
      {activeTheme === 'carousel' && (
        <div className="space-y-8 max-w-4xl mx-auto">
          {[
            {
              num: '01',
              title: 'Autonomous Process Discovery',
              desc: 'Mines messy Slack, WhatsApp, and email streams to extract business workflows without predefined templates.',
              stat: '158 Multi-Turn Traces Extracted',
              tag: 'Phase 1 // Ingestion',
              tweet: 'Can an AI act as a Forward Deployed Engineer?\n\nAutoPilot FDE 2.0 mines Slack/WhatsApp chat, scores automation potential via Graph Entropy, & compiles runnable LangGraph agents with HITL gates.\n\nDemo: https://github.com/your-username/autopilot-fde\n\n@sama @hwchase17',
            },
            {
              num: '02',
              title: 'Graph Transition Entropy',
              desc: 'Formalizes operational unpredictability using Shannon entropy to score automation feasibility across 8 enterprise departments.',
              stat: '16.1 pt Score Spread (58.3 - 74.4)',
              tag: 'Phase 2 // Mathematics',
              tweet: 'Most AI agents fail because they lack entropy models.\n\nOur APS metric uses Graph Transition Entropy: H = -∑ P(u→v) log2 P(u→v).\n\nPredicts agent feasibility with 91% confidence.\n\nPaper: [Link]\n\n@markchen90 @chrs_olah',
            },
            {
              num: '03',
              title: 'Monte Carlo Pre-Flight Simulator',
              desc: 'Simulates 1,000 executions per workflow to forecast Straight-Through Rates (STR) and block 100% of critical safety risks.',
              stat: '56.2% STR • 480m ➔ 15.8m Resolution',
              tag: 'Phase 3 // Simulation',
              tweet: 'Never deploy an agent blindly.\n\nAutoPilot FDE runs 1,000 Monte Carlo simulation runs before deployment:\n• Onboarding: 480m ➔ 15.8m ($44k/yr ROI)\n• DevOps: 100% safety intercept rate.\n\nDemo: https://github.com/your-username/autopilot-fde\n\n@ssankar @PalantirTech',
            },
            {
              num: '04',
              title: 'Self-Synthesizing LangGraph Agents',
              desc: 'Compiles discovered workflows directly into type-safe Python LangGraph state machines with Human-in-the-Loop approval checkpoints.',
              stat: 'Zero Drag-and-Drop • 100% Python Code',
              tag: 'Phase 4 // Deployment',
              tweet: 'The future isn\'t software for humans. It\'s AI that discovers what to build.\n\nAutoPilot FDE 2.0 connects to Slack/WhatsApp, extracts workflows, & writes verified LangGraph Python code with HITL gates.\n\nShowcase: https://github.com/your-username/autopilot-fde\n\n@sama @joaomdmoura',
            },
            {
              num: '05',
              title: 'Empirical Benchmark & Frontier Pitch',
              desc: 'Tested across 7 enterprise departments generating $232k/yr net ROI. Seeking frontier research opportunities at DeepMind, OpenAI, Anthropic.',
              stat: '142/142 CI Tests Passed • 10 Research Blueprints',
              tag: 'Phase 5 // Frontier Lab Selection',
              tweet: 'Looking to join frontier agent research @DeepMind @OpenAI @AnthropicAI.\n\nBuilt AutoPilot FDE + HostShift benchmark (142/142 CI tests passed) + 10 theoretical blueprints on test-time reasoning entropy.\n\nRepo: https://github.com/your-username\n\n@demishassabis @JeffDean',
            },
          ].map((slide, idx) => (
            <div key={idx} className="bg-white rounded-3xl p-8 border border-slate-200 shadow-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
              <div className="space-y-2 max-w-xl">
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-black text-blue-600">{slide.num}</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400 bg-slate-100 px-2.5 py-0.5 rounded-full">{slide.tag}</span>
                </div>
                <h3 className="text-2xl font-black text-slate-900">{slide.title}</h3>
                <p className="text-sm text-slate-600">{slide.desc}</p>
                <div className="inline-block font-mono text-xs font-bold text-emerald-600 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-lg mt-2">
                  {slide.stat}
                </div>
              </div>

              <button
                onClick={() => copyToClipboard(slide.tweet, `slide-${idx}`)}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 text-white font-bold text-xs hover:bg-blue-600 transition shadow-md shrink-0"
              >
                {copiedIndex === `slide-${idx}` ? <Check size={16} /> : <Copy size={16} />}
                <span>{copiedIndex === `slide-${idx}` ? 'Copied Tweet!' : 'Copy 280-char Tweet'}</span>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
