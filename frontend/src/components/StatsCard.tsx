import React from 'react';

interface StatsCardProps {
  label: string;
  value: string | number;
  icon: React.ElementType;
  trend?: string;
  trendUp?: boolean;
}

const StatsCard: React.FC<StatsCardProps> = ({ label, value, icon: Icon, trend, trendUp }) => {
  return (
    <div className="ledger-stat min-w-0">
      <div className="flex items-center justify-between gap-3">
        <span className="ledger-icon" aria-hidden="true"><Icon size={16} /></span>
        {trend && <span className={`metadata ${trendUp ? 'text-[var(--success)]' : 'text-[var(--text-muted)]'}`}>{trend}</span>}
      </div>
      <div className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-[.06em] text-[var(--text-muted)]">{label}</h3>
        <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      </div>
    </div>
  );
};

export default StatsCard;
