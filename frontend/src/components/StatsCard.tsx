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
      <div className="mb-4 flex items-center justify-between gap-3">
        <Icon size={17} className="text-[var(--text-muted)]" aria-hidden="true" />
        {trend && <span className={`metadata ${trendUp ? 'text-[var(--success)]' : 'text-[var(--text-muted)]'}`}>{trend}</span>}
      </div>
      <div>
        <h3 className="text-sm text-[var(--text-muted)]">{label}</h3>
        <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      </div>
    </div>
  );
};

export default StatsCard;
