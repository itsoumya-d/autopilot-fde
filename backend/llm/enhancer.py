"""Optional LLM enhancement layer.

AutoPilot FDE's discovery/scoring pipeline is fully deterministic and works
with zero external dependencies. When an ``LLM_API_KEY`` is present in the
environment, ``HttpxLLMEnhancer`` enriches discovered processes with
human-readable summaries and per-step rationale via any OpenAI-compatible
chat endpoint. Any failure — missing key, network error, malformed response,
timeout — silently falls back to :class:`RuleBasedEnhancer`, so the product
degrades to exactly its pre-LLM behavior, never to an error page.
"""

import logging
import os
from typing import Any, Dict, List, Protocol

logger = logging.getLogger(__name__)

_ENHANCE_TIMEOUT_SECONDS = 12.0


class LLMEnhancer(Protocol):
    def enhance_process(self, process: Dict[str, Any]) -> Dict[str, Any]:
        """Returns the process dict, optionally enriched. Must never raise."""
        ...


class RuleBasedEnhancer:
    """Deterministic fallback: composes summaries from signals already computed."""

    def enhance_process(self, process: Dict[str, Any]) -> Dict[str, Any]:
        steps = [activity.get("name", "") for activity in process.get("activities", [])]
        metrics = process.get("metrics", {})
        summary = (
            f"{process.get('name', 'Workflow')}: a {len(steps)}-step process executed by "
            f"{metrics.get('unique_actors_count', 1)} actor(s) across "
            f"{metrics.get('trace_count', 0)} observed trace(s)."
        )
        enriched = dict(process)
        enriched["llm_summary"] = summary
        enriched["step_rationale"] = {
            step: "Classified by the deterministic risk table (no LLM configured)."
            for step in steps
        }
        return enriched


class HttpxLLMEnhancer:
    """Calls an OpenAI-compatible /chat/completions endpoint. Never raises."""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _prompt(self, process: Dict[str, Any]) -> str:
        steps = [activity.get("name", "") for activity in process.get("activities", [])]
        metrics = process.get("metrics", {})
        return (
            "You are a business-process analyst. Given this discovered workflow, reply with "
            "ONLY compact JSON: {\"summary\": one sentence, \"rationale\": {step: one short phrase}}.\n"
            f"Process: {process.get('name')}\n"
            f"Steps: {steps}\n"
            f"Traces: {metrics.get('trace_count')}, Actors: {metrics.get('unique_actors_count')}, "
            f"Entropy: {metrics.get('entropy_score')}\n"
        )

    def _call(self, prompt: str) -> str | None:
        import httpx

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 500,
                },
                timeout=_ENHANCE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as error:  # noqa: BLE001 — any failure must fall back, not propagate
            logger.warning("LLM enhancement unavailable (%s); using rule-based summary.", type(error).__name__)
            return None

    def enhance_process(self, process: Dict[str, Any]) -> Dict[str, Any]:
        content = self._call(self._prompt(process))
        if not content:
            return RuleBasedEnhancer().enhance_process(process)
        parsed = _extract_json(content)
        if not parsed or "summary" not in parsed:
            return RuleBasedEnhancer().enhance_process(process)
        enriched = dict(process)
        enriched["llm_summary"] = str(parsed["summary"])
        rationale = parsed.get("rationale")
        enriched["step_rationale"] = rationale if isinstance(rationale, dict) else {}
        return enriched


def _extract_json(text: str) -> Dict[str, Any] | None:
    """Pulls the first JSON object out of an LLM reply (handles ```json fences)."""
    import json

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def get_enhancer() -> LLMEnhancer:
    """Activates the LLM path only when LLM_API_KEY is set; otherwise rule-based."""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        return RuleBasedEnhancer()
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    logger.info("LLM enhancement active (model=%s)", model)
    return HttpxLLMEnhancer(api_key=api_key, base_url=base_url, model=model)


def enhance_processes(processes: List[Any]) -> None:
    """Best-effort enrichment of mined Process models before persistence."""
    enhancer = get_enhancer()
    for process in processes:
        try:
            payload = process.model_dump()
            enhanced = enhancer.enhance_process(payload)
            process.description = enhanced.get("llm_summary") or process.description
        except Exception as error:  # noqa: BLE001 — enrichment is strictly additive
            logger.debug("Enhancement skipped for %s: %s", getattr(process, "id", "?"), error)
