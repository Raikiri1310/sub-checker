from types import SimpleNamespace

from transcribe import _format_timestamp, main, segments_to_srt


def _seg(start, end, text):
    return SimpleNamespace(start=start, end=end, text=text)


def test_format_timestamp_pads_and_rounds():
    assert _format_timestamp(0) == "00:00:00,000"
    assert _format_timestamp(3725.4) == "01:02:05,400"


def test_segments_to_srt_renders_standard_blocks():
    segments = [_seg(1.0, 2.5, "hello"), _seg(3.0, 4.0, "world")]

    result = segments_to_srt(segments)

    assert result == (
        "1\n00:00:01,000 --> 00:00:02,500\nhello\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nworld\n"
    )


def test_segments_to_srt_skips_blank_segments_and_renumbers():
    segments = [_seg(1.0, 2.0, "  "), _seg(3.0, 4.0, "real line")]

    result = segments_to_srt(segments)

    assert result == "1\n00:00:03,000 --> 00:00:04,000\nreal line\n"


def test_segments_to_srt_empty_input_returns_empty_string():
    assert segments_to_srt([]) == ""


def test_main_errors_on_missing_audio_file(tmp_path):
    exit_code = main([str(tmp_path / "missing.audio.mp3")])

    assert exit_code == 1


def test_main_derives_output_path_and_writes_srt(tmp_path, monkeypatch):
    audio_path = tmp_path / "episode.audio.mp3"
    audio_path.write_bytes(b"fake audio")

    fake_segments = [_seg(1.0, 2.0, "konnichiwa")]
    monkeypatch.setattr("transcribe.transcribe", lambda path, model: iter(fake_segments))

    exit_code = main([str(audio_path)])

    assert exit_code == 0
    output_path = tmp_path / "episode.transcript.srt"
    assert output_path.exists()
    assert "konnichiwa" in output_path.read_text(encoding="utf-8")


def test_main_errors_when_no_segments_produced(tmp_path, monkeypatch, capsys):
    audio_path = tmp_path / "episode.audio.mp3"
    audio_path.write_bytes(b"fake audio")

    monkeypatch.setattr("transcribe.transcribe", lambda path, model: iter([]))

    exit_code = main([str(audio_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "no segments" in captured.err
