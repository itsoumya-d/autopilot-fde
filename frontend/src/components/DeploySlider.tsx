import React from 'react';

interface DeploySliderProps {
  value: number;
  onChange: (value: number) => void;
}

const DeploySlider: React.FC<DeploySliderProps> = ({ value, onChange }) => {
  return (
    <div className="w-full py-4">
      <input 
        type="range" 
        min="0" 
        max="50" 
        value={value} 
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-cyan-500" 
      />
      <div className="flex justify-between text-xs text-slate-400 mt-2 px-1">
        <span>0%</span>
        <span>12.5%</span>
        <span>25%</span>
        <span>37.5%</span>
        <span>50%</span>
      </div>
    </div>
  );
};

export default DeploySlider;
