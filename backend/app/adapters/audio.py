from __future__ import annotations

import json
from pathlib import Path

from pydub import AudioSegment


def split_audio_by_translation(vocals_file: Path, translation_file: Path, session: Path) -> Path:
    output_dir = session / "segments" / "vocals"
    output_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(translation_file.read_text(encoding="utf-8"))
    audio = AudioSegment.from_file(vocals_file)

    for index, item in enumerate(data["translation"], start=1):
        output_file = output_dir / f"{index:04d}.wav"
        if output_file.exists():
            continue
        start = max(0, int(item["start_time"]) - 80)
        end = min(len(audio), int(item["end_time"]) + 160)
        audio[start:end].export(output_file, format="wav")

    return output_dir


def merge_tts_audio(translation_file: Path, tts_dir: Path, session: Path) -> Path:
    output_file = session / "tmp" / "audio_dubbing.wav"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists():
        return output_file

    data = json.loads(translation_file.read_text(encoding="utf-8"))
    duration = max(int(item["end_time"]) for item in data["translation"]) + 3000
    canvas = AudioSegment.silent(duration=duration, frame_rate=48000)

    for index, item in enumerate(data["translation"], start=1):
        tts_file = tts_dir / f"{index:04d}.wav"
        if not tts_file.exists():
            raise FileNotFoundError(f"Missing TTS segment: {tts_file}")
        segment = AudioSegment.from_file(tts_file).set_frame_rate(48000)
        canvas = canvas.overlay(segment, position=max(0, int(item["start_time"])))

    canvas.export(output_file, format="wav")
    return output_file

