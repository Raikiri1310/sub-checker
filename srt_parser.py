"""Parse SubRip (.srt) subtitle files into structured entries."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass


@dataclass
class SrtEntry:
    start: float
    end: float
    text: str


_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def _timestamp_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(path: str) -> list[SrtEntry]:
    """Parse an SRT file into a list of SrtEntry, skipping malformed blocks."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    entries: list[SrtEntry] = []
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().splitlines()

        timestamp_line_idx = None
        for i, line in enumerate(lines):
            if _TIMESTAMP_RE.search(line):
                timestamp_line_idx = i
                break

        if timestamp_line_idx is None:
            print(
                f"warning: skipping malformed SRT block (no timestamp line): {block[:60]!r}",
                file=sys.stderr,
            )
            continue

        match = _TIMESTAMP_RE.search(lines[timestamp_line_idx])
        start = _timestamp_to_seconds(*match.group(1, 2, 3, 4))
        end = _timestamp_to_seconds(*match.group(5, 6, 7, 8))

        text_lines = lines[timestamp_line_idx + 1:]
        text = " ".join(line.strip() for line in text_lines if line.strip())

        if not text:
            print(
                f"warning: skipping malformed SRT block (no text): {block[:60]!r}",
                file=sys.stderr,
            )
            continue

        entries.append(SrtEntry(start=start, end=end, text=text))

    return entries
