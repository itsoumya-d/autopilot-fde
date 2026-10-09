"""Local dataset and training-recipe generation for AutoPilot FDE.

No teacher model is called, and no training or deployment is performed here.
"""

from .engine import DistillationEngine
from .pii_scrubber import PIIScrubber
from .trainer import RecipeExporter

__all__ = ["DistillationEngine", "PIIScrubber", "RecipeExporter"]
