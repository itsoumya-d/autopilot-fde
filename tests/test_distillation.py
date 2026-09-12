"""Tests for Model Distillation Studio, PII scrubber, and legal compliance."""

from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient

import backend.database as database
import backend.main as main_mod
from backend.distillation.engine import DistillationEngine
from backend.distillation.pii_scrubber import PIIScrubber
from backend.distillation.trainer import RecipeExporter
from backend.models.schema import (
    Activity,
    DistillationJob,
    DistillationStatus,
    Message,
    Process,
    StudentModel,
    TeacherModel,
)


class TestDistillationSuite(unittest.TestCase):
    def setUp(self):
        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._tmp.name) / "test.db"
        self.client = TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._db.close_db())
        finally:
            loop.close()
        self._tmp.cleanup()

    def test_pii_scrubber_masks_sensitive_data(self):
        raw_text = (
            "Contact CEO Alice at alice@acme-corp.com or +1 (555) 234-5678. "
            "Her SSN is 000-12-3456 and CC is 4532-1234-5678-9012. "
            "Server IP is 192.168.1.100 with key sk-abcdef1234567890abcdef123456."
        )
        scrubbed, count = PIIScrubber.scrub_text(raw_text)

        assert "[REDACTED_EMAIL]" in scrubbed
        assert "[REDACTED_PHONE]" in scrubbed
        assert "[REDACTED_SSN]" in scrubbed
        assert "[REDACTED_CC]" in scrubbed
        assert "[REDACTED_IP]" in scrubbed
        assert "[REDACTED_SECRET]" in scrubbed
        assert count >= 6

    def test_pii_scrubber_dict_recursively(self):
        payload = {
            "user": {"email": "bob@example.com", "phone": "555-123-4567"},
            "tags": ["normal", "send to admin@test.org", {"nested_email": "nested@test.com"}, 123],
            "num": 42,
        }
        scrubbed_dict, count = PIIScrubber.scrub_dict(payload)
        assert scrubbed_dict["user"]["email"] == "[REDACTED_EMAIL]"
        assert scrubbed_dict["user"]["phone"] == "[REDACTED_PHONE]"
        assert scrubbed_dict["tags"][1] == "send to [REDACTED_EMAIL]"
        assert scrubbed_dict["tags"][2]["nested_email"] == "[REDACTED_EMAIL]"
        assert scrubbed_dict["tags"][3] == 123
        assert scrubbed_dict["num"] == 42
        assert count >= 4

    def test_cost_savings_calculation(self):
        savings = DistillationEngine.calculate_cost_savings(sample_volume_monthly=10000, avg_tokens_per_call=1000)
        assert savings["monthly_volume"] == 10000
        assert savings["teacher_monthly_cost"] > 0
        assert savings["student_annual_cost"] > 0
        assert "net_annual_savings" in savings

        # Test keyword argument alias
        savings2 = DistillationEngine.calculate_cost_savings(monthly_volume=20000)
        assert savings2["monthly_volume"] == 20000

    def test_recipe_exporter_generates_valid_scripts(self):
        tmp_path = Path(self._tmp.name) / "export_test"
        job = DistillationJob(
            id="DISTILL-TEST",
            teacher_model=TeacherModel.GPT_4O,
            student_model=StudentModel.QWEN_2_5_7B,
            output_dir=str(tmp_path),
        )
        dataset_path = str(tmp_path / "dataset.jsonl")
        tmp_path.mkdir(parents=True, exist_ok=True)
        Path(dataset_path).write_text('{"text": "sample"}', encoding="utf-8")

        files = RecipeExporter.export_all(job, dataset_path, tmp_path)
        assert len(files) == 3
        for f in files:
            assert Path(f).exists()
            content = Path(f).read_text(encoding="utf-8")
            assert len(content) > 50

    def test_distillation_engine_with_matched_and_missing_sources(self):
        tmp_path = Path(self._tmp.name) / "engine_run"
        msg = Message(id="M1", sender="Alice", content="Approve vendor invoice", timestamp=datetime.now(UTC))
        act_matched = Activity(
            id="A1",
            name="approve_invoice",
            category="finance",
            actors=["Alice"],
            timestamp=datetime.now(UTC),
            source_messages=["M1"],
            confidence=0.95,
        )
        act_missing = Activity(
            id="A2",
            name="missing_activity",
            category="finance",
            actors=["Bob"],
            timestamp=datetime.now(UTC),
            source_messages=["NONEXISTENT_MSG"],
            confidence=0.5,
        )
        proc = Process(id="P1", name="Finance Invoicing", activities=[act_matched, act_missing], category="finance")

        job = DistillationJob(
            id="DISTILL-MATCHED",
            teacher_model=TeacherModel.DEEPSEEK_R1,
            student_model=StudentModel.MISTRAL_7B,
            training_format="openai",
        )

        completed = DistillationEngine.execute_job(job, [proc], [msg], base_dir=tmp_path)
        assert completed.status == DistillationStatus.COMPLETED
        assert completed.sample_count >= 1

    def test_distillation_engine_fallback_synthetic_and_attestation_failure(self):
        tmp_path = Path(self._tmp.name) / "engine_fallback"
        job_fallback = DistillationJob(
            id="DISTILL-FALLBACK",
            teacher_model=TeacherModel.DEEPSEEK_R1,
            student_model=StudentModel.QWEN_2_5_7B,
            training_format="alpaca",
        )
        # Empty processes triggers synthetic fallback generation
        completed = DistillationEngine.execute_job(job_fallback, [], [], base_dir=tmp_path)
        assert completed.status == DistillationStatus.COMPLETED
        assert completed.sample_count >= 3

        # Attestation failure directly in execute_job
        job_fail = DistillationJob(
            id="DISTILL-FAIL",
            teacher_model=TeacherModel.GPT_4O,
            student_model=StudentModel.LLAMA_3_1_8B,
            attest_internal_use_only=False,
        )
        res = DistillationEngine.execute_job(job_fail, [], [])
        assert res.status == DistillationStatus.FAILED

    def test_distillation_api_endpoints(self):
        # 1. Models
        resp = self.client.get("/api/distillation/models")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["teachers"]) >= 4
        assert len(data["students"]) >= 4

        # 2. Cost savings
        resp = self.client.get("/api/distillation/cost-savings?monthly_volume=20000")
        assert resp.status_code == 200
        assert resp.json()["monthly_volume"] == 20000

        # 3. Scrub preview
        resp = self.client.post("/api/distillation/scrub-preview", json={"text": "Hello john@test.com"})
        assert resp.status_code == 200
        assert resp.json()["redactions_count"] == 1

        # 4. Job creation with legal attestation
        resp = self.client.post(
            "/api/distillation/jobs",
            json={
                "teacher_model": "gpt-4o",
                "student_model": "Qwen/Qwen2.5-7B-Instruct",
                "attest_internal_use_only": True,
                "commercial_foundation_competition_waiver": True,
            },
        )
        assert resp.status_code == 200
        job_data = resp.json()
        assert job_data["status"] == "completed"
        assert job_data["sample_count"] > 0
        job_id = job_data["id"]

        # 5. Get job
        resp = self.client.get(f"/api/distillation/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

        # 6. List jobs
        resp = self.client.get("/api/distillation/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # 7. Get unknown job returns 404
        resp_404 = self.client.get("/api/distillation/jobs/UNKNOWN-JOB")
        assert resp_404.status_code == 404

        # 8. Rejection without legal attestation
        resp_fail = self.client.post(
            "/api/distillation/jobs",
            json={
                "teacher_model": "gpt-4o",
                "student_model": "Qwen/Qwen2.5-7B-Instruct",
                "attest_internal_use_only": False,
                "commercial_foundation_competition_waiver": False,
            },
        )
        assert resp_fail.status_code == 400
