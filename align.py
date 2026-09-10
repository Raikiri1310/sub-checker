"""Align official subtitles to a Whisper transcript by timestamp overlap."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from srt_parser import parse_srt


def align_subtitles(subs: list, transcript: list) -> list[dict]:
    aligned = []

    for sub in subs:
        overlaps = []
        for seg in transcript:
            overlap = min(sub.end, seg.end) - max(sub.start, seg.start)
            if overlap > 0:
                overlaps.append((max(sub.start, seg.start), seg.text))

        entry = {
            "start": sub.start,
            "end": sub.end,
            "official_subtitle": sub.text,
        }

        if overlaps:
            overlaps.sort(key=lambda pair: pair[0])
            entry["original_transcript"] = " ".join(text for _, text in overlaps)
        else:
            entry["original_transcript"] = None
            entry["no_transcript_match"] = True

        aligned.append(entry)

    return aligned


def build_output_path(subs_path: Path, explicit_output: str | None) -> Path:
    if explicit_output:
        return Path(explicit_output)
    # Match extract.py's base_name derivation (video_path.stem) so that
    # "Show.S01E01.eng.srt" -> "Show.S01E01", not just "Show". Strip the
    # ".srt" suffix, then strip a trailing ".eng" component if present --
    # using Path.stem rather than splitting on the first dot keeps this
    # correct for release names with extra dots elsewhere (e.g. "S01E01").
    base_name = subs_path.stem
    if Path(base_name).suffix == ".eng":
        base_name = Path(base_name).stem
    return subs_path.parent / f"{base_name}.aligned.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Align official subtitles to a Whisper transcript by timestamp overlap."
    )
    parser.add_argument("subs", help="Path to the official subtitle SRT file")
    parser.add_argument("transcript", help="Path to the Whisper transcript SRT file")
    parser.add_argument(
        "-o", "--output", help="Output path for aligned JSON (default: <name>.aligned.json)"
    )
    args = parser.parse_args(argv)

    subs_path = Path(args.subs)
    transcript_path = Path(args.transcript)

    if not subs_path.exists():
        print(f"error: subtitle file not found: {subs_path}", file=sys.stderr)
        return 1
    if not transcript_path.exists():
        print(f"error: transcript file not found: {transcript_path}", file=sys.stderr)
        return 1

    subs = parse_srt(str(subs_path))
    transcript = parse_srt(str(transcript_path))

    if not subs:
        print(f"error: no valid entries parsed from subtitle file: {subs_path}", file=sys.stderr)
        return 1
    if not transcript:
        print(f"error: no valid entries parsed from transcript file: {transcript_path}", file=sys.stderr)
        return 1

    aligned = align_subtitles(subs, transcript)
    output_path = build_output_path(subs_path, args.output)
    output_path.write_text(json.dumps(aligned, indent=2, ensure_ascii=False), encoding="utf-8")

    matched = sum(1 for e in aligned if not e.get("no_transcript_match"))
    print(f"Aligned {matched}/{len(aligned)} subtitle lines. Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
