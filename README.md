# sub-checker: Subtitle Translation Fidelity Checker

Checks how faithful an anime's official English subtitles are to the
original Japanese dialogue. Extracts the subtitle track and audio from a
video, transcribes the audio locally with faster-whisper, then aligns the
two by timestamp so the divergences can be reviewed line by line.

## Requirements

- `ffmpeg` and `ffprobe` on PATH.
- Python 3 with `faster-whisper` installed (`pip install -r requirements.txt`).
- A video file with an embedded (soft) English subtitle track.

## Workflow

**1. Extract the subtitle and audio from the episode:**

```bash
python sub-checker/extract.py /path/to/episode.mkv
```

This writes two files next to the video (or into `--out-dir DIR` if
given):

- `episode.eng.srt` — the official subtitle track, converted to plain
  SRT with ASS styling/override codes stripped.
- `episode.audio.mp3` — mono, 16kHz audio, small enough for any upload
  tool.

If the video has no subtitle track tagged `eng`, it falls back to the
first subtitle track present and prints a warning — check that the
extracted `.eng.srt` is actually dialogue and not signs/songs before
continuing.

**2. Transcribe the audio locally:**

```bash
python sub-checker/transcribe.py episode.audio.mp3
```

Runs faster-whisper on CPU in Japanese **transcribe mode, not
translate** — we want the original Japanese, not Whisper's own
translation, since the whole point is comparing the official subs
against the true original, not against a second translation. Writes
`episode.transcript.srt` next to the audio file. Takes several minutes
per episode on CPU with the default `medium` model; the model weights
(~1.5GB) download from Hugging Face and cache locally on first run.

Use `--model large-v3` for higher accuracy at the cost of more runtime,
or `--model small` for a faster/lower-accuracy pass.

**3. Align the subtitle against the transcript:**

```bash
python sub-checker/align.py episode.eng.srt episode.transcript.srt
```

Writes `episode.aligned.json`: a list of entries, one per official
subtitle line —

```json
{
  "start": 12.5,
  "end": 15.0,
  "official_subtitle": "I'm not doing this for you.",
  "original_transcript": "betsu ni anata no tame ja nai"
}
```

Lines with no overlapping transcript segment (silent-scene subs, sound
effects) get `"original_transcript": null` and `"no_transcript_match":
true` instead — expected, not an error.

**4. Get the divergence report.**

Hand `episode.aligned.json` to Claude Code in a session and ask for a
review. There's no script for this step — it's a judgment call on
meaning changes, omissions, censorship, and tone shifts, referenced by
timestamp so you can jump to that point in the episode.

## Notes

- One episode at a time — no batch mode yet.
- Output filenames are derived from the video's base name (e.g.
  `Show.S01E01.mkv` → `Show.S01E01.eng.srt` / `Show.S01E01.audio.mp3` /
  `Show.S01E01.aligned.json`), so different episodes of the same show
  won't collide.
- `align.py` accepts `-o /custom/path.json` to override the default
  output path.

## Testing

```bash
cd sub-checker && python -m pytest -v
```

34 tests, all pure unit tests (no ffmpeg/model calls) except that
`extract.py` was manually verified against a real anime file with
embedded ASS softsubs during development, and `transcribe.py` against a
real extracted audio file.
