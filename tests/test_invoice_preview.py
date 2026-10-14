"""Keep the visual sample document synchronized with the validated backend fixture."""
import json
from pathlib import Path

from backend.archetypes.project3_document_intel import DocumentIntelligenceEngine


def test_workflow_lab_invoice_preview_matches_backend_fixture():
    preview_path = Path(__file__).parents[1] / "frontend/src/lib/invoice-preview.json"
    preview = json.loads(preview_path.read_text())
    invoice = DocumentIntelligenceEngine.parse_raw_text("").model_dump(mode="json")
    assert preview == invoice
