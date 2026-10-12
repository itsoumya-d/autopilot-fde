import json
from pathlib import Path
import zipfile

import pytest

from scripts import package_demo_recording as package


def fixture_files(tmp_path: Path):
    results = tmp_path / 'results'
    results.mkdir()
    (results / 'video.webm').write_bytes(b'synthetic-package-test-bytes')
    evidence = {'recording': True, 'synthetic': True, 'finalStatus': 'resolved',
                'externalActions': False, 'shots': [{}] * 6}
    (results / 'demonstration-evidence.json').write_text(json.dumps(evidence))
    return results, tmp_path / 'output' / 'demo.zip'


def test_archive_contains_only_expected_files_and_exact_size(tmp_path):
    results, output = fixture_files(tmp_path)
    size = package.package_recording(results, output)
    assert size == output.stat().st_size <= 5_000_000
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ['demo.webm', 'evidence.json']


def test_archive_overhead_is_counted_before_upload(tmp_path, monkeypatch):
    results, output = fixture_files(tmp_path)
    monkeypatch.setattr(package, 'MAX_ARCHIVE_BYTES', 100)
    with pytest.raises(ValueError, match='Complete ZIP exceeds'):
        package.package_recording(results, output)
    assert not output.exists()


@pytest.mark.parametrize('field,value', [('recording', False), ('synthetic', False),
                         ('finalStatus', 'pending_approval'), ('externalActions', True),
                         ('shots', [])])
def test_unverified_evidence_refused(tmp_path, field, value):
    results, output = fixture_files(tmp_path)
    path = results / 'demonstration-evidence.json'
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='evidence'):
        package.package_recording(results, output)
    assert not output.exists()


def test_duplicate_recordings_refused(tmp_path):
    results, output = fixture_files(tmp_path)
    nested = results / 'extra'
    nested.mkdir()
    (nested / 'video.webm').write_bytes(b'not-a-real-video')
    with pytest.raises(ValueError, match='exactly one'):
        package.package_recording(results, output)
    assert not output.exists()


def test_empty_recording_has_specific_diagnostic(tmp_path):
    results, output = fixture_files(tmp_path)
    (results / 'video.webm').write_bytes(b'')
    with pytest.raises(ValueError, match='Video is empty'):
        package.package_recording(results, output)
    assert not output.exists()


def test_large_recording_reports_exact_size(tmp_path, monkeypatch):
    results, output = fixture_files(tmp_path)
    monkeypatch.setattr(package, 'MAX_ARCHIVE_BYTES', 2)
    monkeypatch.setattr(package.shutil, 'which', lambda name: None)
    with pytest.raises(ValueError, match='Raw video is 28 bytes'):
        package.package_recording(results, output)
    assert not output.exists()


def test_existing_encoder_failure_prevents_upload(tmp_path, monkeypatch):
    results, output = fixture_files(tmp_path)
    monkeypatch.setattr(package, 'MAX_ARCHIVE_BYTES', 2)
    monkeypatch.setattr(package.shutil, 'which', lambda name: '/usr/bin/ffmpeg')
    def fail(*args, **kwargs):
        raise package.subprocess.CalledProcessError(1, 'ffmpeg')
    monkeypatch.setattr(package.subprocess, 'run', fail)
    with pytest.raises(package.subprocess.CalledProcessError):
        package.package_recording(results, output)
    assert not output.exists()
