from types import SimpleNamespace

from transcribe import (
    _format_timestamp,
    load_cached_names,
    main,
    names_cache_path,
    prompt_for_names,
    save_cached_names,
    segments_to_srt,
)


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
    monkeypatch.setattr(
        "transcribe.transcribe", lambda path, model, initial_prompt=None: iter(fake_segments)
    )

    exit_code = main([str(audio_path), "--names", ""])

    assert exit_code == 0
    output_path = tmp_path / "episode.transcript.srt"
    assert output_path.exists()
    assert "konnichiwa" in output_path.read_text(encoding="utf-8")


def test_main_errors_when_no_segments_produced(tmp_path, monkeypatch, capsys):
    audio_path = tmp_path / "episode.audio.mp3"
    audio_path.write_bytes(b"fake audio")

    monkeypatch.setattr("transcribe.transcribe", lambda path, model, initial_prompt=None: iter([]))

    exit_code = main([str(audio_path), "--names", ""])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "no segments" in captured.err


def test_main_passes_names_through_as_initial_prompt(tmp_path, monkeypatch):
    audio_path = tmp_path / "episode.audio.mp3"
    audio_path.write_bytes(b"fake audio")

    captured_prompt = {}

    def fake_transcribe(path, model, initial_prompt=None):
        captured_prompt["value"] = initial_prompt
        return iter([_seg(1.0, 2.0, "hi")])

    monkeypatch.setattr("transcribe.transcribe", fake_transcribe)

    exit_code = main([str(audio_path), "--names", "Kitahara, Kotegawa, Palau"])

    assert exit_code == 0
    assert captured_prompt["value"] == "Kitahara, Kotegawa, Palau"


def test_prompt_for_names_returns_cli_value_without_prompting(monkeypatch):
    monkeypatch.setattr(
        "builtins.input", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not prompt"))
    )

    assert prompt_for_names("Kitahara, Palau") == "Kitahara, Palau"


def test_prompt_for_names_returns_none_for_blank_cli_value():
    assert prompt_for_names("   ") is None


def test_prompt_for_names_prompts_when_no_cli_value_given(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "Kebako, Aina")

    assert prompt_for_names(None) == "Kebako, Aina"


def test_prompt_for_names_prompt_returns_none_when_left_blank(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "   ")

    assert prompt_for_names(None) is None


def test_prompt_for_names_falls_back_to_cached_value_on_blank_input(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    assert prompt_for_names(None, cached_value="Kitahara, Palau") == "Kitahara, Palau"


def test_prompt_for_names_typed_value_overrides_cached_value(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "Kebako")

    assert prompt_for_names(None, cached_value="Kitahara, Palau") == "Kebako"


def test_prompt_for_names_shows_cached_value_in_prompt_text(monkeypatch):
    seen = {}

    def fake_input(prompt=""):
        seen["prompt"] = prompt
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    prompt_for_names(None, cached_value="Kitahara, Palau")

    assert "[Kitahara, Palau]" in seen["prompt"]


def test_load_cached_names_returns_none_when_file_missing(tmp_path):
    assert load_cached_names(tmp_path) is None


def test_save_and_load_cached_names_round_trip(tmp_path):
    save_cached_names(tmp_path, "Kitahara, Kotegawa, Palau")

    assert load_cached_names(tmp_path) == "Kitahara, Kotegawa, Palau"
    assert names_cache_path(tmp_path).exists()


def test_load_cached_names_ignores_comment_and_blank_lines(tmp_path):
    names_cache_path(tmp_path).write_text(
        "# Characters\n"
        "Kitahara, Kotegawa\n"
        "\n"
        "# Places\n"
        "Palau, Guam\n",
        encoding="utf-8",
    )

    assert load_cached_names(tmp_path) == "Kitahara, Kotegawa, Palau, Guam"


def test_load_cached_names_returns_none_when_only_comments(tmp_path):
    names_cache_path(tmp_path).write_text("# nothing here yet\n", encoding="utf-8")

    assert load_cached_names(tmp_path) is None


def test_save_cached_names_preserves_comment_lines(tmp_path):
    names_cache_path(tmp_path).write_text(
        "# Characters and places for Grand Blue\nKitahara, Kotegawa\n", encoding="utf-8"
    )

    save_cached_names(tmp_path, "Kitahara, Kotegawa, Palau, Guam")

    content = names_cache_path(tmp_path).read_text(encoding="utf-8")
    assert "# Characters and places for Grand Blue" in content
    assert "Kitahara, Kotegawa, Palau, Guam" in content
    assert load_cached_names(tmp_path) == "Kitahara, Kotegawa, Palau, Guam"


def test_save_cached_names_consolidates_multiple_existing_name_lines(tmp_path):
    names_cache_path(tmp_path).write_text(
        "# Characters\nKitahara\n# Places\nPalau\n", encoding="utf-8"
    )

    save_cached_names(tmp_path, "Kitahara, Palau, Guam")

    content = names_cache_path(tmp_path).read_text(encoding="utf-8")
    assert content.count("Kitahara, Palau, Guam") == 1
    assert "# Characters" in content
    assert "# Places" in content
    assert load_cached_names(tmp_path) == "Kitahara, Palau, Guam"


def test_main_writes_names_cache_after_run(tmp_path, monkeypatch):
    audio_path = tmp_path / "episode.audio.mp3"
    audio_path.write_bytes(b"fake audio")
    monkeypatch.setattr(
        "transcribe.transcribe", lambda path, model, initial_prompt=None: iter([_seg(1.0, 2.0, "hi")])
    )

    main([str(audio_path), "--names", "Kitahara, Palau"])

    assert load_cached_names(tmp_path) == "Kitahara, Palau"


def test_main_prefills_prompt_from_existing_cache(tmp_path, monkeypatch):
    audio_path = tmp_path / "episode.audio.mp3"
    audio_path.write_bytes(b"fake audio")
    save_cached_names(tmp_path, "Kitahara, Palau")
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    monkeypatch.setattr(
        "transcribe.transcribe", lambda path, model, initial_prompt=None: iter([_seg(1.0, 2.0, "hi")])
    )

    exit_code = main([str(audio_path)])

    assert exit_code == 0
    assert load_cached_names(tmp_path) == "Kitahara, Palau"


def test_main_does_not_write_cache_when_names_blank(tmp_path, monkeypatch):
    audio_path = tmp_path / "episode.audio.mp3"
    audio_path.write_bytes(b"fake audio")
    monkeypatch.setattr(
        "transcribe.transcribe", lambda path, model, initial_prompt=None: iter([_seg(1.0, 2.0, "hi")])
    )

    main([str(audio_path), "--names", ""])

    assert not names_cache_path(tmp_path).exists()
