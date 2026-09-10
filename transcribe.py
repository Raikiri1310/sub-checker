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


def transcribe(audio_path: str, model_size: str, initial_prompt: str | None = None):
    """Run faster-whisper in Japanese transcribe mode. Returns the segments iterable."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        audio_path, language="ja", task="transcribe", initial_prompt=initial_prompt
    )
    return segments


NAMES_CACHE_FILENAME = "names_places_nouns.txt"


def names_cache_path(out_dir: Path) -> Path:
    return out_dir / NAMES_CACHE_FILENAME


def _is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def load_cached_names(out_dir: Path) -> str | None:
    """Read names_places_nouns.txt, ignoring blank lines and '#'-prefixed comments."""
    path = names_cache_path(out_dir)
    if not path.exists():
        return None

    values = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if not _is_comment_or_blank(line)
    ]
    return ", ".join(values) or None


def save_cached_names(out_dir: Path, names: str) -> None:
    """Write the resolved names line to the cache file, preserving any '#' comments/blank lines."""
    path = names_cache_path(out_dir)
    names = names.strip()

    if not path.exists():
        path.write_text(names + "\n", encoding="utf-8")
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    inserted = False
    for line in lines:
        if _is_comment_or_blank(line):
            new_lines.append(line)
            continue
        if not inserted:
            new_lines.append(names)
            inserted = True
        # subsequent non-comment lines are consolidated into the one above

    if not inserted:
        new_lines.append(names)

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def prompt_for_names(cli_value: str | None, cached_value: str | None = None) -> str | None:
    """Return the proper-noun hint to bias transcription.

    Prompts interactively if not given on the CLI, pre-filling with cached_value
    (from a prior run's names_places_nouns.txt) as the default on blank input.
    """
    if cli_value is not None:
        return cli_value.strip() or None

    suffix = f" [{cached_value}]" if cached_value else ""
    entered = input(
        f"Names/places/proper nouns to help transcription (comma-separated, blank to skip){suffix}: "
    ).strip()
    return entered or cached_value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe extracted audio to a timestamped Japanese SRT using a local Whisper model."
    )
    parser.add_argument("audio", help="Path to the extracted audio file (e.g. <name>.audio.mp3)")
    parser.add_argument(
        "--model", default="medium", help="faster-whisper model size (default: medium)"
    )
    parser.add_argument("--out-dir", help="Output directory (default: same directory as the audio)")
    parser.add_argument(
        "--names",
        help="Comma-separated names/places/proper nouns to bias transcription toward "
        "(skips the interactive prompt if given)",
    )
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

    cached_names = load_cached_names(out_dir)
    initial_prompt = prompt_for_names(args.names, cached_names)
    if initial_prompt:
        save_cached_names(out_dir, initial_prompt)

    print(f"Transcribing {audio_path} (this can take several minutes on CPU)...")
    segments = transcribe(str(audio_path), args.model, initial_prompt)

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
