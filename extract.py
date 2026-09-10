"""Extract the English subtitle track and audio from a video for transcription."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


class NoSubtitleStreamError(Exception):
    pass


def pick_subtitle_stream(streams: list[dict]) -> dict:
    """Pick the first English-tagged subtitle stream, falling back to the first stream present."""
    if not streams:
        raise NoSubtitleStreamError("no subtitle streams found in video file")

    for stream in streams:
        if stream.get("tags", {}).get("language") == "eng":
            return stream

    print(
        "warning: no subtitle stream tagged 'eng', falling back to first subtitle stream",
        file=sys.stderr,
    )
    return streams[0]


def check_binaries() -> None:
    for binary in ("ffmpeg", "ffprobe"):
        if shutil.which(binary) is None:
            print(f"error: '{binary}' not found on PATH", file=sys.stderr)
            sys.exit(1)


def probe_subtitle_streams(video_path: str) -> list[dict]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_streams", "-select_streams", "s", video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout).get("streams", [])


_ASS_OVERRIDE_RE = re.compile(r"\{\\[^}\n]*\}")
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>\n]*>")


def _strip_subtitle_styling(path: str) -> None:
    """Strip ASS override codes and residual HTML styling tags.

    ffmpeg's ASS->SRT conversion carries over per-line font/color overrides
    as HTML <font>/<i> tags (SRT supports a small HTML subset) and can leave
    literal ASS override codes like {\\an7} in the text. The srt encoder has
    no flag to suppress this, so strip it here to leave plain dialogue text.
    """
    content = Path(path).read_text(encoding="utf-8")
    cleaned = _ASS_OVERRIDE_RE.sub("", content)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    Path(path).write_text(cleaned, encoding="utf-8")


def extract_subtitle(video_path: str, stream_index: int, output_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", video_path,
            "-map", f"0:{stream_index}", "-c:s", "srt", output_path,
        ],
        check=True, capture_output=True, text=True,
    )
    _strip_subtitle_styling(output_path)


def extract_audio(video_path: str, output_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", video_path,
            "-vn", "-ac", "1", "-ar", "16000", "-codec:a", "libmp3lame",
            output_path,
        ],
        check=True, capture_output=True, text=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract the English subtitle track and audio from a video for transcription."
    )
    parser.add_argument("video", help="Path to the video file")
    parser.add_argument("--out-dir", help="Output directory (default: same directory as the video)")
    args = parser.parse_args(argv)

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"error: video file not found: {video_path}", file=sys.stderr)
        return 1

    check_binaries()

    out_dir = Path(args.out_dir) if args.out_dir else video_path.parent
    base_name = video_path.stem

    try:
        streams = probe_subtitle_streams(str(video_path))
        stream = pick_subtitle_stream(streams)
    except NoSubtitleStreamError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"error: ffprobe failed on {video_path}:\n{e.stderr}", file=sys.stderr)
        return 1

    subtitle_out = out_dir / f"{base_name}.eng.srt"
    audio_out = out_dir / f"{base_name}.audio.mp3"

    try:
        extract_subtitle(str(video_path), stream["index"], str(subtitle_out))
        extract_audio(str(video_path), str(audio_out))
    except subprocess.CalledProcessError as e:
        print(
            f"error: ffmpeg failed extracting subtitle/audio from {video_path}:\n{e.stderr}",
            file=sys.stderr,
        )
        return 1

    print(f"Wrote {subtitle_out}")
    print(f"Wrote {audio_out}")
    print(f"Next: python transcribe.py {audio_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
