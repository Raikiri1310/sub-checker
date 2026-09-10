from pathlib import Path

from srt_parser import SrtEntry, parse_srt


def _write_srt(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "test.srt"
    path.write_text(content, encoding="utf-8")
    return path


def test_parses_basic_entries(tmp_path):
    content = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Hello there.\n"
        "\n"
        "2\n"
        "00:00:05,500 --> 00:00:07,250\n"
        "General Kenobi.\n"
    )
    path = _write_srt(tmp_path, content)

    entries = parse_srt(str(path))

    assert entries == [
        SrtEntry(start=1.0, end=4.0, text="Hello there."),
        SrtEntry(start=5.5, end=7.25, text="General Kenobi."),
    ]


def test_joins_multiline_text(tmp_path):
    content = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Line one\n"
        "Line two\n"
    )
    path = _write_srt(tmp_path, content)

    entries = parse_srt(str(path))

    assert entries == [SrtEntry(start=1.0, end=4.0, text="Line one Line two")]


def test_skips_malformed_block_and_warns(tmp_path, capsys):
    content = (
        "1\n"
        "not a timestamp\n"
        "Broken entry\n"
        "\n"
        "2\n"
        "00:00:05,000 --> 00:00:06,000\n"
        "Valid entry\n"
    )
    path = _write_srt(tmp_path, content)

    entries = parse_srt(str(path))

    assert entries == [SrtEntry(start=5.0, end=6.0, text="Valid entry")]
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()


def test_empty_file_returns_empty_list(tmp_path):
    path = _write_srt(tmp_path, "")

    entries = parse_srt(str(path))

    assert entries == []
