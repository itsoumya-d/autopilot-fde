'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, MessageSquare, Activity, BarChart2, Rocket, TrendingUp, Sparkles, Share2, Menu } from 'lucide-react';

const Sidebar = () => {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);

  const links = [
    { href: '/', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/social-deck', label: 'Social Studio', icon: Share2 },
    { href: '/showcase', label: 'Motion Showcase', icon: Sparkles },
    { href: '/channels', label: 'Channels', icon: MessageSquare },
    { href: '/processes', label: 'Processes', icon: Activity },
    { href: '/scores', label: 'Scores', icon: BarChart2 },
    { href: '/deploy', label: 'Deploy', icon: Rocket },
    { href: '/performance', label: 'Performance', icon: TrendingUp },
  ];

  return (
    <aside className={`bg-gray-900 border-r border-slate-800 transition-all duration-300 ${collapsed ? 'w-20' : 'w-64'} flex flex-col h-screen`}>
      <div className="p-4 flex items-center justify-between">
        {!collapsed && <span className="text-xl font-bold text-white tracking-wide">AutoPilot <span className="text-cyan-500">FDE</span></span>}
        <button onClick={() => setCollapsed(!collapsed)} className="text-gray-400 hover:text-white p-2 rounded-md hover:bg-gray-800">
          <Menu size={20} />
        </button>
      </div>
      <nav className="flex-1 mt-6">
        <ul className="space-y-2 px-3">
          {links.map((link) => {
            const Icon = link.icon;
            const active = pathname === link.href;
            return (
              <li key={link.href}>
                <Link href={link.href} className={`flex items-center p-3 rounded-lg transition-colors ${active ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}>
                  <Icon size={20} className="shrink-0" />
                  {!collapsed && <span className="ml-3 font-medium">{link.label}</span>}
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
