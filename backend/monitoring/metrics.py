from typing import Dict, Any, List
from datetime import datetime
from collections import defaultdict

class MetricsCollector:
    """Performance monitoring metrics collector."""
    
    def __init__(self):
        self.agent_metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "tasks_completed": 0,
            "tasks_escalated": 0,
            "total_response_time": 0.0,
            "tokens_used": 0,
            "cost": 0.0
        })
        
        self.process_metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_instances": 0,
            "errors": 0,
            "time_saved_seconds": 0.0
        })
        
        self.time_series: List[Dict[str, Any]] = []
        
    def record_agent_action(self, agent_id: str, action_type: str, response_time: float, tokens: int = 0, cost: float = 0.0):
        """Track per-agent metrics."""
        m = self.agent_metrics[agent_id]
        if action_type == "processed":
            m["tasks_completed"] += 1
        elif action_type == "escalated":
            m["tasks_escalated"] += 1
            
        m["total_response_time"] += response_time
        m["tokens_used"] += tokens
        m["cost"] += cost
        
    def record_process_execution(self, process_id: str, success: bool, time_saved: float = 0.0):
        """Track per-process metrics."""
        m = self.process_metrics[process_id]
        m["total_instances"] += 1
        if not success:
            m["errors"] += 1
        m["time_saved_seconds"] += time_saved
        
        # Save point in time series
        self.time_series.append({
            "timestamp": datetime.now(),
            "process_id": process_id,
            "success": success,
            "time_saved": time_saved
        })
        
    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get stats for an agent."""
        m = self.agent_metrics.get(agent_id, {})
        if not m:
            return {}
            
        total_tasks = m["tasks_completed"] + m["tasks_escalated"]
        avg_response = m["total_response_time"] / total_tasks if total_tasks > 0 else 0
        
        return {
            "tasks_completed": m["tasks_completed"],
            "tasks_escalated": m["tasks_escalated"],
            "avg_response_time": avg_response,
            "tokens_used": m["tokens_used"],
            "cost": m["cost"]
        }
        
    def get_process_stats(self, process_id: str) -> Dict[str, Any]:
        """Get stats for a process including STR and ROI."""
        m = self.process_metrics.get(process_id, {})
        if not m or m["total_instances"] == 0:
            return {}
            
        str_rate = (m["total_instances"] - m["errors"]) / m["total_instances"]
        error_rate = m["errors"] / m["total_instances"]
        
        return {
            "str": str_rate,
            "error_rate": error_rate,
            "time_saved_seconds": m["time_saved_seconds"]
        }
        
    def compute_roi(self, process_id: str, agent_id: str, hourly_rate: float = 50.0) -> float:
        """Compute ROI: (time_saved * hourly_rate) - cost."""
        pm = self.process_metrics.get(process_id, {})
        am = self.agent_metrics.get(agent_id, {})
        
        if not pm or not am:
            return 0.0
            
        hours_saved = pm["time_saved_seconds"] / 3600.0
        gross_value = hours_saved * hourly_rate
        net_roi = gross_value - am["cost"]
        
        return net_roi
