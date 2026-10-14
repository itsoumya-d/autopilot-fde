import React from 'react';

interface DeploySliderProps {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  label?: string;
}

const DeploySlider: React.FC<DeploySliderProps> = ({ value, onChange, disabled = false, label = 'Pilot traffic percentage' }) => (
  <div className="w-full pt-4">
    <input aria-label={label} aria-valuetext={`${value}% configured traffic`} disabled={disabled} type="range" min="0" max="50" value={value} onChange={event => onChange(parseInt(event.target.value))} className="h-6 w-full cursor-pointer accent-[var(--accent)] disabled:cursor-not-allowed" />
    <div aria-hidden="true" className="metadata mt-1 flex justify-between tabular-nums"><span>0%</span><span>12.5%</span><span>25%</span><span>37.5%</span><span>50%</span></div>
  </div>
);

export default DeploySlider;
