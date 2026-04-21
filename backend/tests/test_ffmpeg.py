from __future__ import annotations

import json
import subprocess
from pathlib import Path

from backend.app.adapters import ffmpeg


def test_video_orientation_uses_height_greater_than_width(monkeypatch):
    def fake_run(cmd, capture_output=False, text=False, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="720,1280\n", stderr="")

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)

    assert ffmpeg.get_video_orientation(Path("video.mp4")) == "portrait"


def test_video_orientation_defaults_to_landscape_when_probe_fails(monkeypatch):
    def fake_run(cmd, capture_output=False, text=False, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="ffprobe failed")

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)

    assert ffmpeg.get_video_orientation(Path("video.mp4")) == "landscape"


def test_subtitle_styles_match_backend_orientation_rules():
    portrait = ffmpeg.subtitle_style_for_orientation("portrait")
    landscape = ffmpeg.subtitle_style_for_orientation("landscape")

    assert "FontSize=12" in portrait
    assert "MarginV=70" in portrait
    assert "FontSize=24" in landscape
    assert "MarginV=5" in landscape


def test_merge_video_burns_portrait_subtitles(monkeypatch, tmp_path):
    session = tmp_path / "session"
    metadata_dir = session / "metadata"
    metadata_dir.mkdir(parents=True)
    translation = metadata_dir / "translation.zh.json"
    translation.write_text(
        json.dumps(
            {
                "translation": [
                    {"start_time": 0, "end_time": 1200, "zh": "你好"},
                ]
            }
        ),
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_run(cmd, capture_output=False, text=False, check=False, **kwargs):
        commands.append(cmd)
        if cmd[0] == "ffprobe":
            return subprocess.CompletedProcess(cmd, 0, stdout="720,1280\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(ffmpeg.subprocess, "run", fake_run)

    final_video = ffmpeg.merge_video(
        tmp_path / "video.mp4",
        tmp_path / "dubbing.wav",
        tmp_path / "bgm.wav",
        translation,
        session,
    )

    assert final_video == session / "media" / "video_final.mp4"
    assert len(commands) == 3
    final_command = commands[-1]
    filter_arg = final_command[final_command.index("-vf") + 1]
    assert filter_arg.startswith("subtitles=filename='")
    assert "FontSize=12" in filter_arg
    assert "MarginV=70" in filter_arg
    assert "-c:s" not in final_command
