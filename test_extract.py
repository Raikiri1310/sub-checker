import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from extract import NoSubtitleStreamError, pick_subtitle_stream


def test_picks_eng_tagged_stream_when_present():
    streams = [
        {"index": 2, "tags": {"language": "spa"}},
        {"index": 3, "tags": {"language": "eng"}},
    ]

    result = pick_subtitle_stream(streams)

    assert result["index"] == 3


def test_falls_back_to_first_stream_with_warning(capsys):
    streams = [
        {"index": 2, "tags": {"language": "spa"}},
        {"index": 4, "tags": {}},
    ]

    result = pick_subtitle_stream(streams)

    assert result["index"] == 2
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()


def test_handles_missing_tags_key():
    streams = [{"index": 5}]

    result = pick_subtitle_stream(streams)

    assert result["index"] == 5


def test_raises_on_empty_stream_list():
    with pytest.raises(NoSubtitleStreamError):
        pick_subtitle_stream([])


from extract import (
    _strip_subtitle_styling,
    check_binaries,
    extract_audio,
    extract_subtitle,
    main,
    probe_subtitle_streams,
)


def test_probe_subtitle_streams_parses_ffprobe_json():
    fake_result = MagicMock()
    fake_result.stdout = json.dumps({"streams": [{"index": 3, "tags": {"language": "eng"}}]})

    with patch("extract.subprocess.run", return_value=fake_result) as mock_run:
        streams = probe_subtitle_streams("video.mkv")

    assert streams == [{"index": 3, "tags": {"language": "eng"}}]
    args = mock_run.call_args[0][0]
    assert args[0] == "ffprobe"
    assert "video.mkv" in args


def test_extract_subtitle_builds_correct_ffmpeg_command(tmp_path):
    out_path = tmp_path / "out.srt"

    def fake_run(cmd, **kwargs):
        out_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
        return MagicMock()

    with patch("extract.subprocess.run", side_effect=fake_run) as mock_run:
        extract_subtitle("video.mkv", 3, str(out_path))

    args = mock_run.call_args[0][0]
    assert args[0] == "ffmpeg"
    assert "-map" in args
    assert "0:3" in args
    assert args[-1] == str(out_path)


def test_extract_subtitle_strips_ass_styling_junk(tmp_path):
    # Real-world ffmpeg ASS->SRT conversion carries over per-line font/color
    # overrides as HTML <font> tags and leaves alignment override codes like
    # {\an7} in place. Confirmed against a real BD-rip file in manual
    # verification (Task 5 Step 6) -- ffmpeg's srt encoder has no flag to
    # suppress this, so extract_subtitle must strip it itself.
    out_path = tmp_path / "out.srt"
    srt_with_styling = (
        "1\n"
        "00:00:01,000 --> 00:00:02,000\n"
        '<font face="Franklin Gothic Demi Cond" size="68" color="#fffdf3">'
        "{\\an7}Hello there</font>\n\n"
    )

    def fake_run(cmd, **kwargs):
        out_path.write_text(srt_with_styling, encoding="utf-8")
        return MagicMock()

    with patch("extract.subprocess.run", side_effect=fake_run):
        extract_subtitle("video.mkv", 3, str(out_path))

    cleaned = out_path.read_text(encoding="utf-8")
    assert "<font" not in cleaned
    assert "</font>" not in cleaned
    assert "{\\an7}" not in cleaned
    assert "Hello there" in cleaned


def test_strip_subtitle_styling_does_not_cross_newlines(tmp_path):
    # An unclosed "<b" tag (no closing '>' on the same line) must not let
    # the tag-stripping regex eat through subsequent lines looking for the
    # next '>' -- which, in a real SRT file, is the arrow in the next
    # entry's "-->" timestamp line. That would corrupt/drop the following
    # subtitle entry entirely.
    path = tmp_path / "out.srt"
    content = (
        "1\n"
        "00:00:01,000 --> 00:00:02,000\n"
        "<b broken tag with no close\n"
        "First line\n\n"
        "2\n"
        "00:00:03,000 --> 00:00:04,000\n"
        "Second line\n\n"
    )
    path.write_text(content, encoding="utf-8")

    _strip_subtitle_styling(str(path))

    cleaned = path.read_text(encoding="utf-8")
    assert "00:00:03,000 --> 00:00:04,000" in cleaned
    assert "Second line" in cleaned


def test_extract_audio_builds_correct_ffmpeg_command():
    with patch("extract.subprocess.run") as mock_run:
        extract_audio("video.mkv", "out.mp3")

    args = mock_run.call_args[0][0]
    assert args[0] == "ffmpeg"
    assert "-ar" in args
    assert "16000" in args
    assert args[-1] == "out.mp3"


def test_check_binaries_exits_when_ffmpeg_missing(capsys):
    with patch(
        "extract.shutil.which",
        side_effect=lambda b: None if b == "ffmpeg" else "/usr/bin/ffprobe",
    ):
        with pytest.raises(SystemExit) as exc_info:
            check_binaries()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "ffmpeg" in captured.err


def test_main_errors_on_missing_video_file(tmp_path):
    exit_code = main([str(tmp_path / "missing.mkv")])

    assert exit_code == 1


def test_main_reports_ffprobe_failure_clearly(tmp_path, capsys):
    video_path = tmp_path / "video.mkv"
    video_path.write_text("not really a video", encoding="utf-8")

    error = subprocess.CalledProcessError(
        returncode=1, cmd=["ffprobe"], stderr="Invalid data found when processing input"
    )

    with patch("extract.shutil.which", return_value="/usr/bin/ffmpeg"):
        with patch("extract.subprocess.run", side_effect=error):
            exit_code = main([str(video_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Invalid data found when processing input" in captured.err


def test_main_reports_ffmpeg_extraction_failure_clearly(tmp_path, capsys):
    video_path = tmp_path / "video.mkv"
    video_path.write_text("not really a video", encoding="utf-8")

    probe_result = MagicMock()
    probe_result.stdout = json.dumps({"streams": [{"index": 3, "tags": {"language": "eng"}}]})

    extraction_error = subprocess.CalledProcessError(
        returncode=1, cmd=["ffmpeg"], stderr="Subtitle codec pgssub is not supported for srt"
    )

    def fake_run(cmd, **kwargs):
        if cmd[0] == "ffprobe":
            return probe_result
        raise extraction_error

    with patch("extract.shutil.which", return_value="/usr/bin/ffmpeg"):
        with patch("extract.subprocess.run", side_effect=fake_run):
            exit_code = main([str(video_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Subtitle codec pgssub is not supported for srt" in captured.err
