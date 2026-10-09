"""Dataset and recipe generation endpoints; no model training or provider calls."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_messages, get_processes
from ..distillation.engine import DistillationEngine, MissingSourceEvidenceError
from ..distillation.pii_scrubber import PIIScrubber
from ..models.schema import DistillationJob, StudentModel, TeacherModel

router = APIRouter()

_JOBS: dict[str, DistillationJob] = {}


class ScrubPreviewRequest(BaseModel):
    text: str


class CreateJobRequest(BaseModel):
    teacher_model: TeacherModel = TeacherModel.GPT_4O
    student_model: StudentModel = StudentModel.QWEN_2_5_7B
    training_format: Literal["alpaca", "openai"] = "alpaca"
    attest_internal_use_only: bool = False
    commercial_foundation_competition_waiver: bool = False
    allow_synthetic_samples: bool = False
    epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 2e-4
    quantization: str = "4bit"


@router.get("/models", summary="List supported Teacher and Student models")
async def list_models() -> dict[str, Any]:
    """Returns supported recipe model references. Selection grants no usage rights."""
    return {
        "teachers": [
            {
                "id": TeacherModel.GPT_4O.value,
                "name": "OpenAI GPT-4o",
                "compliance_mode": "Metadata only; review current provider terms before using model outputs",
                "recommended_for": "Complex reasoning, tool calling, and high-entropy extraction",
            },
            {
                "id": TeacherModel.CLAUDE_3_5_SONNET.value,
                "name": "Anthropic Claude 3.5 Sonnet",
                "compliance_mode": "Metadata only; review current provider terms before using model outputs",
                "recommended_for": "Coding, state machine logic, and regulatory analysis",
            },
            {
                "id": TeacherModel.DEEPSEEK_R1.value,
                "name": "DeepSeek-R1 (Open Frontier)",
                "compliance_mode": "Metadata only; verify the selected model license and permitted use",
                "recommended_for": "Open model recipe exploration; no teacher call is performed",
            },
            {
                "id": TeacherModel.LLAMA_3_1_405B.value,
                "name": "Meta Llama 3.1 405B Instruct",
                "compliance_mode": "Metadata only; review applicable model license and usage restrictions",
                "recommended_for": "Enterprise data sovereignty and private cloud hosting",
            },
        ],
        "students": [
            {
                "id": StudentModel.QWEN_2_5_7B.value,
                "name": "Qwen 2.5 7B Instruct (Recommended)",
                "size": "7 Billion Parameters (4.2 GB quantized)",
                "vram_required": "6 GB (fits on Mac M-series or RTX 3060)",
                "strengths": "Multilingual reasoning, JSON structured outputs, function calling",
            },
            {
                "id": StudentModel.LLAMA_3_1_8B.value,
                "name": "Meta Llama 3.1 8B Instruct",
                "size": "8 Billion Parameters (4.8 GB quantized)",
                "vram_required": "8 GB",
                "strengths": "Broad tool ecosystem, community support, Ollama compatibility",
            },
            {
                "id": StudentModel.MISTRAL_7B.value,
                "name": "Mistral 7B Instruct v0.3",
                "size": "7 Billion Parameters (4.1 GB quantized)",
                "vram_required": "6 GB",
                "strengths": "Ultra-fast latency, Apache 2.0 license, high throughput",
            },
            {
                "id": StudentModel.GEMMA_2_9B.value,
                "name": "Google Gemma 2 9B Instruct",
                "size": "9 Billion Parameters (5.4 GB quantized)",
                "vram_required": "10 GB",
                "strengths": "Compact footprint, strong benchmark accuracy",
            },
        ],
    }


@router.get("/cost-savings", summary="Calculate ROI of small in-VPC model vs cloud APIs")
async def calculate_cost_savings(monthly_volume: int = 50000, avg_tokens: int = 1500) -> dict[str, Any]:
    return DistillationEngine.calculate_cost_savings(monthly_volume, avg_tokens)


@router.post("/scrub-preview", summary="Preview automated PII scrubbing on sample text")
async def scrub_preview(req: ScrubPreviewRequest) -> dict[str, Any]:
    cleaned, count = PIIScrubber.scrub_text(req.text)
    return {"original": req.text, "scrubbed": cleaned, "redactions_count": count}


@router.post("/jobs", summary="Create and execute model distillation data and recipe generation")
async def create_distillation_job(req: CreateJobRequest) -> DistillationJob:
    if not req.attest_internal_use_only or not req.commercial_foundation_competition_waiver:
        raise HTTPException(
            status_code=400,
            detail="Both usage attestations are required. They do not grant a license or establish legal compliance.",
        )

    job_id = f"DISTILL-{uuid.uuid4().hex[:6].upper()}"
    job = DistillationJob(
        id=job_id,
        teacher_model=req.teacher_model,
        student_model=req.student_model,
        training_format=req.training_format,
        attest_internal_use_only=req.attest_internal_use_only,
        commercial_foundation_competition_waiver=req.commercial_foundation_competition_waiver,
        epochs=req.epochs,
        batch_size=req.batch_size,
        learning_rate=req.learning_rate,
        quantization=req.quantization,
        allow_synthetic_samples=req.allow_synthetic_samples,
    )

    processes = await get_processes()
    messages = await get_messages()

    try:
        job = DistillationEngine.execute_job(job, processes, messages)
    except MissingSourceEvidenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _JOBS[job_id] = job
    return job


@router.get("/jobs/{job_id}", summary="Get distillation job status and recipe files")
async def get_distillation_job(job_id: str) -> DistillationJob:
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Distillation job {job_id} not found")
    return job


@router.get("/jobs", summary="List all distillation jobs")
async def list_distillation_jobs() -> list[DistillationJob]:
    return list(_JOBS.values())
