"""The E2E launcher must not mutate an existing developer workspace."""

from pathlib import Path

import pytest

from scripts import run_browser_test_backend as runner


@pytest.mark.parametrize("fails", [False, True])
def test_browser_runner_uses_disposable_state_and_restores_cwd(tmp_path, monkeypatch, fails):
    existing_db = tmp_path / "existing.db"
    existing_db.write_text("preserve existing data")
    monkeypatch.setattr(runner.database, "DB_PATH", existing_db)
    before = Path.cwd()
    observed = []

    def fake_run(app, *, host, port):
        assert app is runner.app
        assert host == "127.0.0.1" and port == 8000
        temporary = Path.cwd()
        observed.append(temporary)
        assert temporary != before
        assert runner.database.DB_PATH == temporary / "autopilot.db"
        assert not runner.database.DB_PATH.exists()
        (temporary / "runs").mkdir()
        (temporary / "runs" / "synthetic-output.txt").write_text("test output")
        if fails:
            raise RuntimeError("synthetic startup failure")

    monkeypatch.setattr(runner.uvicorn, "run", fake_run)
    if fails:
        with pytest.raises(RuntimeError, match="synthetic startup failure"):
            runner.main()
    else:
        runner.main()
    assert Path.cwd() == before
    assert len(observed) == 1 and not observed[0].exists()
    assert existing_db.read_text() == "preserve existing data"
