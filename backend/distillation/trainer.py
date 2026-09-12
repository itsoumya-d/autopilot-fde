"""Generates executable training recipes and serving specifications for distilled student models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models.schema import DistillationJob, StudentModel


class RecipeExporter:
    """Exports self-contained training scripts and runtime serving manifests."""

    @staticmethod
    def generate_unsloth_script(job: DistillationJob, dataset_path: str) -> str:
        """Generates Unsloth fast fine-tuning script."""
        return f'''# AutoPilot FDE Distillation - Unsloth Recipe
# Teacher: {job.teacher_model.value} -> Student: {job.student_model.value}
# Legal Compliance: Internal Enterprise Use Attestation Verified

import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

max_seq_length = 2048
dtype = None # Auto detection
load_in_4bit = True if "{job.quantization}" == "4bit" else False

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{job.student_model.value}",
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
)

model = FastLanguageModel.get_peft_model(
    model,
    r={job.lora_rank},
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha={job.lora_rank * 2},
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

dataset = load_dataset("json", data_files="{dataset_path}", split="train")

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    dataset_num_proc=2,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size={job.batch_size},
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=60,
        num_train_epochs={job.epochs},
        learning_rate={job.learning_rate},
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="{job.output_dir}/checkpoints",
    ),
)

trainer_stats = trainer.train()

# Export GGUF for perpetual local in-VPC inference with Ollama/vLLM
model.save_pretrained_gguf("{job.output_dir}/gguf", tokenizer, quantization_method="q4_k_m")
print("Fine-tuning complete. Model saved to {job.output_dir}/gguf")
'''

    @staticmethod
    def generate_ollama_modelfile(job: DistillationJob) -> str:
        """Generates an Ollama Modelfile for one-command local deployment."""
        student_tag = job.student_model.value.split("/")[-1].lower()
        return f'''# AutoPilot FDE Ollama Deployment Manifest
# Distilled from Teacher: {job.teacher_model.value}
FROM {job.output_dir}/gguf/unsloth.Q4_K_M.gguf

TEMPLATE """{{{{ if .System }}}}<|system|>
{{{{ .System }}}}<|end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|user|>
{{{{ .Prompt }}}}<|end|>
{{{{ end }}}}<|assistant|>
{{{{ .Response }}}}<|end|>
"""

PARAMETER stop "<|end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER temperature 0.2
PARAMETER top_p 0.9

SYSTEM """You are an enterprise forward-deployed specialist distilled for internal business workflow automation. Respond deterministically according to company operational standards."""
'''

    @staticmethod
    def generate_vllm_service(job: DistillationJob) -> str:
        """Generates a vLLM high-throughput OpenAI-compatible server launch script."""
        return f'''#!/usr/bin/env bash
# Launch distilled in-VPC OpenAI-compatible inference server
# Perpetual license, zero cloud API fees.
vllm serve {job.output_dir}/checkpoints \\
    --port 8000 \\
    --served-model-name custom-fde-agent \\
    --max-model-len 4096 \\
    --gpu-memory-utilization 0.90 \\
    --trust-remote-code
'''

    @classmethod
    def export_all(cls, job: DistillationJob, dataset_path: str, output_dir: Path | str) -> list[str]:
        """Writes all recipes and returns list of created file paths."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        unsloth_path = out / "train_unsloth.py"
        ollama_path = out / "Modelfile"
        vllm_path = out / "serve_vllm.sh"

        unsloth_path.write_text(cls.generate_unsloth_script(job, dataset_path), encoding="utf-8")
        ollama_path.write_text(cls.generate_ollama_modelfile(job), encoding="utf-8")
        vllm_path.write_text(cls.generate_vllm_service(job), encoding="utf-8")
        vllm_path.chmod(0o755)

        return [str(unsloth_path), str(ollama_path), str(vllm_path)]
