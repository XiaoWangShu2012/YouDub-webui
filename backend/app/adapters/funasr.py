from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydub import AudioSegment

from ..config import device

_ASR_MODEL = None
_VAD_MODEL = None


def _load_vad_model():
    global _VAD_MODEL
    if _VAD_MODEL is None:
        from funasr import AutoModel

        _VAD_MODEL = AutoModel(model=os.getenv("FUNASR_VAD_MODEL", "fsmn-vad"), device=device())
    return _VAD_MODEL


def _load_asr_model():
    global _ASR_MODEL
    if _ASR_MODEL is None:
        from funasr import AutoModel

        _ASR_MODEL = AutoModel(model=os.getenv("FUNASR_MODEL", "iic/SenseVoiceSmall"), device=device())
    return _ASR_MODEL


def _vad_segments(audio_file: Path, audio: AudioSegment) -> list[tuple[int, int]]:
    model = _load_vad_model()
    result = model.generate(input=str(audio_file))
    raw_value = result[0].get("value") if result else None
    if not raw_value:
        return [(0, len(audio))]
    return [(int(start), int(end)) for start, end in raw_value if int(end) > int(start)]


def _recognize_segment(segment_file: Path) -> str:
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    model = _load_asr_model()
    result = model.generate(
        input=str(segment_file),
        cache={},
        language="auto",
        use_itn=True,
        batch_size_s=60,
    )
    text = result[0].get("text", "") if result else ""
    return rich_transcription_postprocess(text).strip()


def recognize_speech(vocals_file: Path, session: Path) -> Path:
    metadata_dir = session / "metadata"
    output_file = metadata_dir / "asr.json"
    if output_file.exists():
        return output_file

    tmp_dir = session / "tmp" / "asr_segments"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    audio = AudioSegment.from_file(vocals_file)
    utterances: list[dict[str, Any]] = []

    for index, (start, end) in enumerate(_vad_segments(vocals_file, audio), start=1):
        segment = audio[start:end]
        if len(segment) < 250:
            continue
        segment_file = tmp_dir / f"{index:04d}.wav"
        segment.export(segment_file, format="wav")
        text = _recognize_segment(segment_file)
        if not text:
            continue
        utterances.append({"text": text, "start_time": start, "end_time": end})

    if not utterances:
        raise RuntimeError("FunASR did not return any utterances.")

    result = {
        "result": {
            "text": " ".join(item["text"] for item in utterances),
            "utterances": utterances,
        }
    }
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_file

