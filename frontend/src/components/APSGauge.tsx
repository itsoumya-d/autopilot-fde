import React from 'react';

interface APSGaugeProps {
  score: number;
}

const APSGauge: React.FC<APSGaugeProps> = ({ score }) => {
  const getColor = (score: number) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 50) return 'text-yellow-500';
    return 'text-red-500';
  };

  return (
    <div className="relative w-32 h-32 flex items-center justify-center">
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="10" className="text-gray-700" />
        <circle 
          cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="10" 
          strokeDasharray="283" strokeDashoffset={283 - (283 * score) / 100} 
          className={`${getColor(score)} transition-all duration-1000 ease-out`} 
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold text-white">{score}</span>
        <span className="text-xs text-slate-400">APS</span>
      </div>
    </div>
  );
};

export default APSGauge;
