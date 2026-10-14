"""Offline smoke checks for the repository-root MCP publishing steps.

Only the version-stamp and publisher command steps run. The real publisher,
network download, OIDC authentication and registry are never contacted.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/publish-mcp.yml"


def step(name):
    """Read one named step's literal run block from this fixed workflow format."""
    text = WORKFLOW.read_text()
    block = text.split(f"      - name: {name}\n", 1)[1].split("\n      - ", 1)[0]
    directory = re.search(r"^        working-directory: (.+)$", block, re.MULTILINE)
    run = block.split("        run: ", 1)[1]
    if run.startswith("|\n"):
        run = "\n".join(line[10:] for line in run.splitlines()[1:] if line.strip())
    return directory.group(1) if directory else ".", run.strip()


class PublishWorkflowTests(unittest.TestCase):
    def test_publisher_steps_use_root_manifest_and_preserve_metadata(self):
        self.assertIsNotNone(shutil.which("jq"), "jq is required by the workflow")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = json.loads((ROOT / "server.json").read_text())
            (root / "server.json").write_text(json.dumps(manifest))
            publisher = root / "mcp-publisher"
            publisher.write_text('#!/bin/sh\nset -eu\ntest -f server.json\nprintf "%s\\n" "$*" >> calls.txt\n')
            publisher.chmod(0o700)
            for name in ("Stamp version from tag into server.json", "Authenticate via GitHub OIDC", "Publish"):
                working_directory, command = step(name)
                subprocess.run(["bash", "-e", "-o", "pipefail", "-c", command],
                               cwd=root / working_directory,
                               env={**os.environ, "GITHUB_REF_NAME": "v9.8.7"},
                               check=True, capture_output=True, text=True, timeout=10)
            self.assertEqual(json.loads((root / "server.json").read_text()), {**manifest, "version": "9.8.7"})
            self.assertEqual((root / "calls.txt").read_text().splitlines(), ["login github-oidc", "publish"])


if __name__ == "__main__":
    unittest.main()
