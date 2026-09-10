"""Transcribe extracted audio to a timestamped Japanese SRT using a local Whisper model."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _format_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def segments_to_srt(segments) -> str:
    """Render an iterable of faster-whisper Segment objects as SRT text."""
    blocks = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        start = _format_timestamp(segment.start)
        end = _format_timestamp(segment.end)
        blocks.append(f"{start} --> {end}\n{text}")

    if not blocks:
        return ""

    numbered = [f"{i}\n{block}" for i, block in enumerate(blocks, start=1)]
    return "\n\n".join(numbered) + "\n"


def transcribe(audio_path: str, model_size: str):
    """Run faster-whisper in Japanese transcribe mode. Returns the segments iterable."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path, language="ja", task="transcribe")
    return segments


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe extracted audio to a timestamped Japanese SRT using a local Whisper model."
    )
    parser.add_argument("audio", help="Path to the extracted audio file (e.g. <name>.audio.mp3)")
    parser.add_argument(
        "--model", default="medium", help="faster-whisper model size (default: medium)"
    )
    parser.add_argument("--out-dir", help="Output directory (default: same directory as the audio)")
    args = parser.parse_args(argv)

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"error: audio file not found: {audio_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else audio_path.parent
    base_name = audio_path.stem
    if Path(base_name).suffix == ".audio":
        base_name = Path(base_name).stem
    output_path = out_dir / f"{base_name}.transcript.srt"

    print(f"Transcribing {audio_path} (this can take several minutes on CPU)...")
    segments = transcribe(str(audio_path), args.model)

    count = 0
    written_segments = []
    for segment in segments:
        written_segments.append(segment)
        count += 1
        if count % 20 == 0:
            print(f"  ...{count} segments so far")

    srt_text = segments_to_srt(written_segments)
    if not srt_text.strip():
        print(f"error: transcription produced no segments for {audio_path}", file=sys.stderr)
        return 1

    output_path.write_text(srt_text, encoding="utf-8")
    print(f"Wrote {count} segments to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
