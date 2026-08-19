from typing import Any

from backend.models.schema import Process


class BusinessProcessGraph:
    """Serialization helper for an inspectable process map."""

    def __init__(self) -> None:
        self.processes: dict[str, Process] = {}

    def add_process(self, process: Process) -> None:
        self.processes[process.id] = process

    def remove_process(self, process_id: str) -> None:
        self.processes.pop(process_id, None)

    def to_visualization(self) -> dict[str, list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for process_index, process in enumerate(self.processes.values()):
            base_x = 80 + (process_index % 2) * 380
            base_y = 80 + (process_index // 2) * 280
            nodes.append({"id": process.id, "type": "processNode", "data": {"label": process.name, "traces": process.metrics.trace_count}, "position": {"x": base_x, "y": base_y}})
            for step_index, activity in enumerate(process.activities):
                node_id = f"{process.id}:{activity.name}"
                nodes.append({"id": node_id, "type": "activityNode", "data": {"label": activity.name, "evidence": activity.evidence}, "position": {"x": base_x + step_index * 35, "y": base_y + 110}})
            for edge in process.edges:
                edges.append({"id": f"{process.id}:{edge.source}:{edge.target}", "source": f"{process.id}:{edge.source}", "target": f"{process.id}:{edge.target}", "label": f"{edge.probability:.0%}", "data": {"duration_minutes": edge.avg_duration_minutes}})
        return {"nodes": nodes, "edges": edges}

    def find_bottlenecks(self, threshold_minutes: float = 60.0) -> list[dict[str, Any]]:
        return [
            {"process_id": process.id, "process_name": process.name, "source": edge.source, "target": edge.target, "duration_minutes": edge.avg_duration_minutes}
            for process in self.processes.values() for edge in process.edges if edge.avg_duration_minutes > threshold_minutes
        ]
