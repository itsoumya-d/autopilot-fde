"""The 5 Production-Grade FDE Enterprise Archetypes.

Inspired by Aishwarya Srinivasan's 2026 masterclass:
- Project 1: Permission-Aware Enterprise Knowledge System
- Project 2: Intake-to-Resolution Orchestration Workflow
- Project 3: Dual-Stage Document Intelligence & Approval
- Project 4: Customer Data Onboarding Pipeline
- Project 5: Operations Command Center with Action Loop
"""

from .project1_knowledge_rag import PermissionAwareRAG
from .project2_intake_resolution import IntakeOrchestrator
from .project3_document_intel import DocumentIntelligenceEngine
from .project4_data_onboarding import DataOnboardingPipeline
from .project5_operations_cmd import OperationsCommandCenter

__all__ = [
    "PermissionAwareRAG",
    "IntakeOrchestrator",
    "DocumentIntelligenceEngine",
    "DataOnboardingPipeline",
    "OperationsCommandCenter",
]
