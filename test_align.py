from srt_parser import SrtEntry
from align import align_subtitles


def test_exact_overlap_pairs_lines():
    subs = [SrtEntry(start=1.0, end=4.0, text="Official line")]
    transcript = [SrtEntry(start=1.0, end=4.0, text="Original line")]

    result = align_subtitles(subs, transcript)

    assert result == [{
        "start": 1.0,
        "end": 4.0,
        "official_subtitle": "Official line",
        "original_transcript": "Original line",
    }]


def test_partial_overlap_pairs_lines():
    subs = [SrtEntry(start=2.0, end=5.0, text="Official line")]
    transcript = [SrtEntry(start=4.0, end=6.0, text="Original line")]

    result = align_subtitles(subs, transcript)

    assert result[0]["original_transcript"] == "Original line"


def test_no_overlap_flags_no_transcript_match():
    subs = [SrtEntry(start=1.0, end=2.0, text="Official line")]
    transcript = [SrtEntry(start=10.0, end=12.0, text="Unrelated line")]

    result = align_subtitles(subs, transcript)

    assert result == [{
        "start": 1.0,
        "end": 2.0,
        "official_subtitle": "Official line",
        "original_transcript": None,
        "no_transcript_match": True,
    }]


def test_multiple_transcript_segments_joined_in_time_order():
    subs = [SrtEntry(start=1.0, end=6.0, text="Official line")]
    transcript = [
        SrtEntry(start=4.0, end=6.0, text="second"),
        SrtEntry(start=1.0, end=3.0, text="first"),
    ]

    result = align_subtitles(subs, transcript)

    assert result[0]["original_transcript"] == "first second"


def test_out_of_order_input_lists_still_match():
    subs = [
        SrtEntry(start=10.0, end=12.0, text="second sub"),
        SrtEntry(start=1.0, end=2.0, text="first sub"),
    ]
    transcript = [
        SrtEntry(start=10.5, end=11.5, text="second original"),
        SrtEntry(start=1.0, end=2.0, text="first original"),
    ]

    result = align_subtitles(subs, transcript)

    assert result[0]["official_subtitle"] == "second sub"
    assert result[0]["original_transcript"] == "second original"
    assert result[1]["official_subtitle"] == "first sub"
    assert result[1]["original_transcript"] == "first original"


import json
from pathlib import Path

from align import build_output_path, main


def test_build_output_path_default_uses_first_dot_component(tmp_path):
    subs_path = tmp_path / "episode01.eng.srt"

    result = build_output_path(subs_path, None)

    assert result == tmp_path / "episode01.aligned.json"


def test_build_output_path_matches_extract_py_base_name_for_dotted_filenames(tmp_path):
    # extract.py derives base_name from video_path.stem (e.g. "Show.S01E01.mkv"
    # -> "Show.S01E01"), then writes "Show.S01E01.eng.srt". align.py must
    # derive the same base name here, or two episodes of the same show
    # (S01E01, S01E02) collapse to the same "Show.aligned.json" output and
    # silently overwrite each other.
    subs_path = tmp_path / "Show.S01E01.eng.srt"

    result = build_output_path(subs_path, None)

    assert result == tmp_path / "Show.S01E01.aligned.json"


def test_build_output_path_explicit_override(tmp_path):
    subs_path = tmp_path / "episode01.eng.srt"

    result = build_output_path(subs_path, str(tmp_path / "custom.json"))

    assert result == tmp_path / "custom.json"


def test_main_writes_aligned_json(tmp_path):
    subs_path = tmp_path / "episode01.eng.srt"
    subs_path.write_text(
        "1\n00:00:01,000 --> 00:00:04,000\nOfficial line\n", encoding="utf-8"
    )
    transcript_path = tmp_path / "episode01.transcript.srt"
    transcript_path.write_text(
        "1\n00:00:01,000 --> 00:00:04,000\nOriginal line\n", encoding="utf-8"
    )

    exit_code = main([str(subs_path), str(transcript_path)])

    assert exit_code == 0
    output_path = tmp_path / "episode01.aligned.json"
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data == [{
        "start": 1.0,
        "end": 4.0,
        "official_subtitle": "Official line",
        "original_transcript": "Original line",
    }]


def test_main_errors_on_missing_subs_file(tmp_path):
    transcript_path = tmp_path / "episode01.transcript.srt"
    transcript_path.write_text(
        "1\n00:00:01,000 --> 00:00:04,000\nOriginal line\n", encoding="utf-8"
    )

    exit_code = main([str(tmp_path / "missing.srt"), str(transcript_path)])

    assert exit_code == 1
