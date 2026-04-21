from __future__ import annotations

import json
import subprocess
from pathlib import Path

LANDSCAPE_SUBTITLE_STYLE = (
    "FontName=Arial,"
    "FontSize=24,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BorderStyle=1,"
    "Outline=2,"
    "Alignment=2,"
    "MarginV=5"
)
PORTRAIT_SUBTITLE_STYLE = (
    "FontName=Arial,"
    "FontSize=12,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BorderStyle=1,"
    "Outline=2,"
    "Alignment=2,"
    "MarginV=70"
)


def _srt_time(ms: int) -> str:
    hours = ms // 3_600_000
    ms -= hours * 3_600_000
    minutes = ms // 60_000
    ms -= minutes * 60_000
    seconds = ms // 1000
    millis = ms - seconds * 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def write_srt(translation_file: Path, session: Path) -> Path:
    output_file = session / "metadata" / "subtitles.zh.srt"
    data = json.loads(translation_file.read_text(encoding="utf-8"))
    lines: list[str] = []
    for index, item in enumerate(data["translation"], start=1):
        lines.append(str(index))
        lines.append(f"{_srt_time(int(item['start_time']))} --> {_srt_time(int(item['end_time']))}")
        lines.append(item["zh"])
        lines.append("")
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def probe_video_size(video_file: Path) -> tuple[int, int] | None:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(video_file),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    lines = result.stdout.strip().splitlines()
    if not lines:
        return None
    parts = lines[0].split(",", maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def get_video_orientation(video_file: Path) -> str:
    size = probe_video_size(video_file)
    if size is None:
        return "landscape"
    width, height = size
    return "portrait" if height > width else "landscape"


def subtitle_style_for_orientation(orientation: str) -> str:
    if orientation == "portrait":
        return PORTRAIT_SUBTITLE_STYLE
    return LANDSCAPE_SUBTITLE_STYLE


def subtitle_filter(video_file: Path, subtitle_file: Path) -> str:
    style = subtitle_style_for_orientation(get_video_orientation(video_file))
    sub_path = subtitle_file.as_posix()
    return f"subtitles=filename='{sub_path}':force_style='{style}'"


def merge_video(video_file: Path, dubbing_file: Path, bgm_file: Path, translation_file: Path, session: Path) -> Path:
    tmp_dir = session / "tmp"
    media_dir = session / "media"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    final_video = media_dir / "video_final.mp4"
    if final_video.exists():
        return final_video

    subtitles = write_srt(translation_file, session)
    mixed_audio = tmp_dir / "audio_mixed.m4a"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(dubbing_file),
            "-i",
            str(bgm_file),
            "-filter_complex",
            "[0:a]volume=1.0[a0];[1:a]volume=0.30[a1];[a0][a1]amix=inputs=2:duration=longest:normalize=0[aout]",
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            str(mixed_audio),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_file),
            "-i",
            str(mixed_audio),
            "-vf",
            subtitle_filter(video_file, subtitles),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-shortest",
            str(final_video),
        ],
        check=True,
    )
    return final_video
