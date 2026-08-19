import json
from typing import Dict, Any, List

class Calibrator:
    """Score calibration from expert feedback."""
    
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.configs: Dict[str, Dict[str, float]] = {
            "default": {"R": 0.25, "S": 0.20, "V": 0.20, "D": 0.15, "C": 0.20},
            "risk_averse": {"R": 0.20, "S": 0.25, "V": 0.15, "D": 0.10, "C": 0.30},
            "volume_focused": {"R": 0.20, "S": 0.15, "V": 0.40, "D": 0.15, "C": 0.10}
        }
        
    def calibrate(self, feedback: Dict[str, Any]) -> Dict[str, float]:
        """Calibrate weights based on feedback."""
        # Record feedback
        self.history.append(feedback)
        
        # Simple heuristic calibration for demonstration
        new_weights = self.configs["default"].copy()
        
        if feedback.get("too_complex_errors", False):
            new_weights["C"] += 0.05
            new_weights["R"] -= 0.05
            
        # Normalize
        total = sum(new_weights.values())
        return {k: v / total for k, v in new_weights.items()}
        
    def get_config(self, config_name: str) -> Dict[str, float]:
        """Get A/B testing configs."""
        return self.configs.get(config_name, self.configs["default"])
        
    def save_history(self, filepath: str):
        with open(filepath, 'w') as f:
            json.dump(self.history, f)
