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
    <div className="bg-gray-800/50 backdrop-blur-sm border border-slate-700/50 rounded-xl p-6 shadow-sm flex flex-col">
      <div className="flex justify-between items-start">
        <div className="bg-slate-800/80 p-3 rounded-lg text-cyan-500">
          <Icon size={24} />
        </div>
        {trend && (
          <span className={`text-sm font-medium px-2 py-1 rounded-full ${trendUp ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
            {trend}
          </span>
        )}
      </div>
      <div className="mt-4">
        <h3 className="text-slate-400 text-sm font-medium">{label}</h3>
        <p className="text-3xl font-semibold text-white mt-1 tracking-tight">{value}</p>
      </div>
    </div>
  );
};

export default StatsCard;
