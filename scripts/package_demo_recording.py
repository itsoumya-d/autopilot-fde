"""Package one verified recording; enforce the exact upload bytes before upload."""
import json
import shutil
import subprocess
from pathlib import Path
import zipfile

MAX_ARCHIVE_BYTES = 5_000_000


def package_recording(results: Path, output: Path) -> int:
    videos = list(results.rglob('video.webm'))
    evidence_files = list(results.rglob('demonstration-evidence.json'))
    if len(videos) != 1 or len(evidence_files) != 1:
        raise ValueError('Expected exactly one demo video and one evidence file')
    evidence = json.loads(evidence_files[0].read_text())
    if not (evidence.get('recording') is True and evidence.get('synthetic') is True
            and evidence.get('finalStatus') == 'resolved'
            and evidence.get('externalActions') is False
            and len(evidence.get('shots', [])) == 6):
        raise ValueError('Recording evidence did not confirm the completed synthetic flow')
    raw_size = videos[0].stat().st_size
    print(f'Raw recording size: {raw_size} bytes')
    if raw_size == 0:
        raise ValueError('Video is empty; upload is forbidden')
    video = videos[0]
    archive_name = 'demo.webm'
    if raw_size > MAX_ARCHIVE_BYTES:
        encoder = shutil.which('ffmpeg')
        if encoder is None:
            raise ValueError(f'Raw video is {raw_size} bytes, above the {MAX_ARCHIVE_BYTES} bound; no installed ffmpeg')
        video = videos[0].with_name('demo-compressed.mp4')
        # Only an already-installed standard encoder; no download or install.
        # Preserve the full captured frame, duration and genuine action order.
        subprocess.run([encoder, '-hide_banner', '-loglevel', 'error', '-y',
                        '-i', str(videos[0]), '-an', '-c:v', 'libx264', '-preset', 'medium',
                        '-crf', '22', '-maxrate', '300k', '-bufsize', '600k',
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)],
                       check=True, timeout=180)
        archive_name = 'demo.mp4'
        print(f'Compressed recording size: {video.stat().st_size} bytes')
        if not 0 < video.stat().st_size <= MAX_ARCHIVE_BYTES:
            raise ValueError('Compressed recording exceeds approved bound; no upload')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exact ZIP is constructed here. upload-artifact archive:false uploads these
    # bytes without wrapping them in another archive or including any other file.
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(video, archive_name)
        archive.write(evidence_files[0], 'evidence.json')
    size = output.stat().st_size
    if not 0 < size <= MAX_ARCHIVE_BYTES:
        output.unlink()
        raise ValueError('Complete ZIP exceeds 5,000,000 bytes; upload is forbidden')
    return size


if __name__ == '__main__':
    size = package_recording(Path('frontend/browser-test-results'), Path('demo-capture/AutoPilot-recording.zip'))
    print(f'Approved recording ZIP size: {size} bytes (limit {MAX_ARCHIVE_BYTES})')
