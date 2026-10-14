"""Run the real API with disposable synthetic data for browser regression tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# The checkout remains the import source while all mutable test output is local
# to this run. Never mutate or delete a developer's existing database/runs.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn

from backend import database
from backend.main import app


def main() -> None:
    original_directory = Path.cwd()
    with TemporaryDirectory(prefix="autopilot-browser-test-") as directory:
        database.DB_PATH = Path(directory) / "autopilot.db"
        os.chdir(directory)
        try:
            uvicorn.run(app, host="127.0.0.1", port=8000)
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    main()
