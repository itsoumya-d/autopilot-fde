"""Compliant Model Distillation Studio for AutoPilot FDE.

Enables distillation of business extraction, reasoning, and routing logic
from frontier teacher models (GPT-4o, Claude 3.5, DeepSeek-R1) into compact,
perpetual in-VPC student models (Qwen 2.5, Llama 3.1, Mistral).
"""

from .engine import DistillationEngine
from .pii_scrubber import PIIScrubber
from .trainer import RecipeExporter

__all__ = ["DistillationEngine", "PIIScrubber", "RecipeExporter"]
