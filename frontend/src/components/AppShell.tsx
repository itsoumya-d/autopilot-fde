'use client';

import React from 'react';
import { MotionConfig } from 'framer-motion';
import { usePathname } from 'next/navigation';
import Sidebar, { navigationGroups } from './Sidebar';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const group = navigationGroups.find(group => group.links.some(link => link.href === pathname));
  const current = group?.links.find(link => link.href === pathname);
  return <MotionConfig reducedMotion="user" transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}>
    <div className="app-shell">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <Sidebar />
      <div className="app-stage">
        <div className="app-location"><span>{group?.label ?? 'Workspace'}</span><span aria-hidden="true">/</span><strong>{current?.label ?? 'AutoPilot'}</strong><span className="location-boundary">Local-first prototype</span></div>
        <main id="main-content" tabIndex={-1} className="app-content"><div className="app-content-inner">{children}</div></main>
      </div>
    </div>
  </MotionConfig>;
}
