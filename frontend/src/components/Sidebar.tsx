'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, MessageSquare, Activity, BarChart2, Rocket, TrendingUp, Sparkles, Share2, Boxes, Menu, Shield, Cpu } from 'lucide-react';

const Sidebar = () => {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);

  const links = [
    { href: '/', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/archetypes', label: '5 Archetypes', icon: Shield },
    { href: '/distillation', label: 'Distill Studio', icon: Cpu },
    { href: '/social-deck', label: 'Social Studio', icon: Share2 },
    { href: '/showcase', label: 'Motion Showcase', icon: Sparkles },
    { href: '/channels', label: 'Channels', icon: MessageSquare },
    { href: '/processes', label: 'Processes', icon: Activity },
    { href: '/objects', label: 'Object Lens', icon: Boxes },
    { href: '/scores', label: 'Scores', icon: BarChart2 },
    { href: '/deploy', label: 'Deploy', icon: Rocket },
    { href: '/performance', label: 'Performance', icon: TrendingUp },
  ];

  return (
    <aside className={`bg-gray-900 border-b border-slate-800 transition-all duration-300 w-full min-w-0 shrink-0 md:border-b-0 md:border-r ${collapsed ? 'md:w-20' : 'md:w-64'} flex flex-col md:h-full`}>
      <div className="p-4 flex shrink-0 items-center justify-between">
        {!collapsed && <span className="text-xl font-bold text-white tracking-wide">AutoPilot <span className="text-cyan-500">FDE</span></span>}
        <button type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} aria-controls="primary-navigation" onClick={() => setCollapsed(!collapsed)} className="text-gray-400 hover:text-white p-2 rounded-md hover:bg-gray-800">
          <Menu size={20} aria-hidden="true" />
        </button>
      </div>
      <nav id="primary-navigation" aria-label="Primary navigation" className="min-h-0 min-w-0 overflow-auto md:flex-1 md:mt-6">
        <ul className="flex gap-2 px-3 pb-3 md:block md:space-y-2">
          {links.map((link) => {
            const Icon = link.icon;
            const active = pathname === link.href;
            return (
              <li key={link.href} className="shrink-0">
                <Link href={link.href} aria-label={link.label} aria-current={active ? 'page' : undefined} title={collapsed ? link.label : undefined} className={`flex items-center p-3 rounded-lg transition-colors ${active ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}>
                  <Icon size={20} aria-hidden="true" className="shrink-0" />
                  {!collapsed && <span className="ml-3 whitespace-nowrap font-medium">{link.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
};

export default Sidebar;
