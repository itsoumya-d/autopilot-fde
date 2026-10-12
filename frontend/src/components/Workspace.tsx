'use client';

import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: React.ReactNode; actions?: React.ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p className="page-kicker">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>{actions && <div className="page-actions">{actions}</div>}</header>;
}
export function SectionHeader({ title, description, actions }: { title: string; description?: React.ReactNode; actions?: React.ReactNode }) {
  return <div className="section-header"><div><h2>{title}</h2>{description && <p className="muted mt-1">{description}</p>}</div>{actions}</div>;
}
export function StatusBadge({ tone = 'neutral', children }: { tone?: 'neutral' | 'success' | 'warning' | 'danger'; children: React.ReactNode }) {
  return <span className={`status-badge ${tone}`}>{children}</span>;
}
export function SourceLabel({ children }: { children: React.ReactNode }) { return <span className="source-label">{children}</span>; }
export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) { return <div className="empty-state"><h3>{title}</h3>{children && <div className="muted mt-2">{children}</div>}</div>; }
export function ErrorState({ children }: { children: React.ReactNode }) { return <div role="alert" className="error-state">{children}</div>; }
export function Reveal({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  return <motion.div initial={{ opacity: reduced ? 1 : 0, y: reduced ? 0 : 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : 0.18, ease: [0.2, 0.8, 0.2, 1] }} className={className}>{children}</motion.div>;
}
