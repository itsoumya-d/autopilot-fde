'use client';

import React, { useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, MessageSquare, Activity, BarChart2, Rocket, TrendingUp, FlaskConical, Share2, Boxes, Menu, PanelLeftClose, PanelLeftOpen, X, Cpu } from 'lucide-react';

export const navigationGroups = [
  { label: 'Workspace', links: [
    { href: '/', label: 'Overview', icon: LayoutDashboard },
    { href: '/channels', label: 'Sources', icon: MessageSquare },
    { href: '/processes', label: 'Workflows', icon: Activity },
    { href: '/objects', label: 'Object Lens', icon: Boxes },
    { href: '/scores', label: 'Opportunities', icon: BarChart2 },
  ] },
  { label: 'Operate', links: [
    { href: '/deploy', label: 'Pilots', icon: Rocket },
    { href: '/performance', label: 'Performance', icon: TrendingUp },
  ] },
  { label: 'Studio', links: [
    { href: '/archetypes', label: 'Workflow Lab', icon: FlaskConical },
    { href: '/distillation', label: 'Model Recipes', icon: Cpu },
    { href: '/showcase', label: 'Simulation', icon: Activity },
    { href: '/social-deck', label: 'Social Studio', icon: Share2 },
  ] },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  const closeDrawer = () => { dialogRef.current?.close(); setDrawerOpen(false); menuRef.current?.focus(); };
  const openDrawer = () => { setDrawerOpen(true); dialogRef.current?.showModal(); };
  const current = navigationGroups.flatMap(group => group.links).find(link => link.href === pathname)?.label;
  const links = (mobile = false) => <nav id={mobile ? 'mobile-navigation' : 'primary-navigation'} aria-label={mobile ? 'Mobile navigation' : 'Primary navigation'} className="rail-navigation">
    {navigationGroups.map(group => <div className="nav-group" key={group.label}><p className="nav-group-label">{group.label}</p><ul>{group.links.map(link => {
      const Icon = link.icon;
      return <li key={link.href}><Link href={link.href} aria-label={link.label} title={link.label} aria-current={pathname === link.href ? 'page' : undefined} onClick={mobile ? closeDrawer : undefined} className="rail-link"><Icon size={17} aria-hidden="true" /><span>{link.label}</span></Link></li>;
    })}</ul></div>)}
  </nav>;
  return <>
    <div className="mobile-header"><button ref={menuRef} type="button" aria-label="Open navigation" aria-haspopup="dialog" aria-expanded={drawerOpen} aria-controls="mobile-drawer" onClick={openDrawer}><Menu size={20} aria-hidden="true" /></button><span>AutoPilot <span className="muted">/ {current}</span></span></div>
    <aside className={`app-rail ${collapsed ? 'is-collapsed' : ''}`}>
      <div className="rail-brand"><span className="brand-word">AutoPilot<span className="brand-sub">FDE</span></span><button type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} aria-controls="primary-navigation" onClick={() => setCollapsed(value => !value)}>{collapsed ? <PanelLeftOpen size={18} aria-hidden="true" /> : <PanelLeftClose size={18} aria-hidden="true" />}</button></div>
      {links()}
      <div className="rail-footnote"><span className="rail-footnote-dot" aria-hidden="true" /><span>Evidence before action</span></div>
    </aside>
    <dialog id="mobile-drawer" ref={dialogRef} aria-label="Workspace navigation" className="mobile-drawer" onCancel={event => { event.preventDefault(); closeDrawer(); }} onClick={event => { if (event.target === event.currentTarget) closeDrawer(); }} onClose={() => { setDrawerOpen(false); menuRef.current?.focus(); }}>
      <div className="drawer-content"><div className="rail-brand"><span className="brand-word">AutoPilot<span className="brand-sub">FDE</span></span><button type="button" aria-label="Close navigation" onClick={closeDrawer}><X size={20} aria-hidden="true" /></button></div>{links(true)}<p className="drawer-note">Local-first workflow prototype</p></div>
    </dialog>
  </>;
}
