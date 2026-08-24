# Training Your Own Model on AutoPilot FDE Data

Every discovery run produces supervised training signal for free: raw
operational messages in, structured workflow extraction out. This guide turns
that signal into a fine-tuned model with three provider paths.

---

## 1. Export the dataset

With discovery results present (boot the API once, or run `run_discovery()`):

```bash
cd autopilot-fde && source .venv/bin/activate

# OpenAI chat format (works on OpenAI, Together, Anyscale, vLLM)
PYTHONPATH=. python scripts/export_training_data.py \
    --format openai --out runs/training/autopilot-openai.jsonl

# Alpaca instruction format (works on axolotl, LLaMA-Factory, torchtune)
PYTHONPATH=. python scripts/export_training_data.py \
    --format alpaca --out runs/training/autopilot-alpaca.jsonl
```

Each row pairs the **raw message text** (`user`) with the **expert
extraction** the deterministic engine derived from it (`assistant`): process
name, step name, actors, category, confidence, recommended safety mode. The
deterministic extractor is the teacher; the fine-tuned model learns to do
the extraction *without* the keyword tables — including vocabulary your
tables never covered.

## 2. Pick a path

| Path | Best when | Cost profile |
|---|---|---|
| **OpenAI fine-tuning API** | You want the smallest operational lift and already have API credits | ~$ per 1M tokens, managed |
| **Together / Anyscale / Fireworks** | You want open-weight output models (Llama, Qwen, Mistral) | Similar, more control |
| **Local LoRA (axolotl / LLaMA-Factory / MLX)** | Data cannot leave your VPC, or you want unlimited re-trains | Your GPUs only |

### OpenAI fine-tuning API

```bash
export OPENAI_API_KEY=sk-...
pip install openai

python - <<'PY'
from openai import OpenAI
client = OpenAI()
file = client.files.create(
    file=open("runs/training/autopilot-openai.jsonl", "rb"),
    purpose="fine-tune",
)
job = client.fine_tuning.jobs.create(
    training_file=file.id,
    model="gpt-4.1-mini-2025-04-14",   # check current supported base models
    suffix="autopilot-extractor",
)
print(job.status, job.id)
PY
```

Evaluate before shipping: hold out 10–20% of rows (split by `case_id`, never
by row, so the same case never appears in both splits), then score exact-match
on step name and category against the deterministic engine's labels.

### Together AI (open weights)

```bash
pip install together
together files create runs/training/autopilot-openai.jsonl
together fine-tuning create \
  --training-file <file-id> \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --suffix autopilot-extractor
```

### Local LoRA, data stays in-house

```bash
pip install "unsloth[colab-new]"   # or: pip install axolotl
# Point your LoRA config at runs/training/autopilot-alpaca.jsonl,
# train 2–3 epochs, merge adapters, serve with vLLM:
#   vllm serve ./merged-model --served-model-name autopilot-extractor
# Then point AutoPilot FDE at it:
AUTOPILOT_LLM_ENHANCE=1 LLM_BASE_URL=http://localhost:8000/v1 \
LLM_MODEL=autopilot-extractor uvicorn backend.main:app --port 8000
```

### Hugging Face Inference Providers

HF Inference Providers expose an OpenAI-compatible chat endpoint, so a Hub-
hosted model can be the enrichment engine without running anything:

```bash
pip install -U "huggingface_hub[cli]"
hf auth login   # token with inference-api scope

export AUTOPILOT_LLM_ENHANCE=1 \
       LLM_BASE_URL=https://router.huggingface.co/v1 \
       LLM_MODEL=<org>/<model> \
       LLM_API_KEY=$HF_TOKEN
```

Push your dataset to the Hub directly from the exporter:

```bash
PYTHONPATH=. python scripts/export_training_data.py \
    --format openai --out runs/training/train.jsonl \
    --push-to-hub <your-org>/autopilot-extractor-train
```

The enhancer speaks the OpenAI-compatible chat protocol, so **your own
fine-tuned model — served by HF, vLLM, or any provider — becomes the
enrichment engine** for the next discovery run.

## 3. Close the loop

The flywheel that makes this interesting:

```
ingest streams → discover → export JSONL → fine-tune → serve back as
     ↑                                                  |
     └────────── better extraction next cycle ←─────────┘
```

Each cycle teaches the model your organization's actual verbs ("refund",
"churn risk", "PO approved") instead of hand-maintaining keyword tables.
Audit trails and APS outcomes stay in SQLite; export them separately if you
want to train a *scoring* model later.

## Hygiene rules

- **Split by case, not by row** — correlated rows leak.
- **Never train on another company's workspace** — exports contain message
  text; treat them like customer data (they are).
- **Keep the deterministic engine** as ground truth and fallback; the model
  augments it via `AUTOPILOT_LLM_ENHANCE=1`, it does not replace it.
- Re-export after every meaningful discovery run; version the JSONL files so
  any checkpoint can be traced to its data.
