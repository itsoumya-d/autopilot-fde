import React from 'react';
import { Handle, Position } from '@xyflow/react';

const ProcessNode = ({ data }: { data: { label: string; score: number; traces: number } }) => {
  const color = data.score >= 65 ? 'border-cyan-400' : data.score >= 45 ? 'border-amber-400' : 'border-slate-500';
  return (
    <div className={`min-w-48 px-4 py-3 shadow-xl rounded-xl bg-slate-900 border ${color}`}>
      <Handle type="target" position={Position.Top} className="!bg-slate-500" />
      <p className="text-sm font-bold text-white">{data.label}</p>
      <p className="mt-1 text-xs text-slate-400">Opportunity {data.score} · {data.traces} observed cases</p>
      <Handle type="source" position={Position.Bottom} className="!bg-slate-500" />
    </div>
  );
};

export default ProcessNode;
