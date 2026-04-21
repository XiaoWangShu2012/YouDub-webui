from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import database
from .config import WORKFOLDER, YOUTUBE_COOKIE_PATH
from .stages import STAGES


@dataclass
class PipelineArtifacts:
    session: Path | None = None
    video_file: Path | None = None
    vocals_file: Path | None = None
    bgm_file: Path | None = None
    asr_file: Path | None = None
    translation_file: Path | None = None
    vocals_dir: Path | None = None
    tts_dir: Path | None = None
    dubbing_file: Path | None = None
    final_video: Path | None = None


def _write_log(task_id: str, message: str) -> None:
    path = database.log_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _require(value, name: str):
    if value is None:
        raise RuntimeError(f"Missing pipeline artifact: {name}")
    return value


class PipelineRunner:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.artifacts = PipelineArtifacts()
        self._stage_handlers: dict[str, Callable[[dict], None]] = {
            "download": self._download,
            "separate": self._separate,
            "asr": self._asr,
            "translate": self._translate,
            "split_audio": self._split_audio,
            "tts": self._tts,
            "merge_audio": self._merge_audio,
            "merge_video": self._merge_video,
        }

    def run(self) -> None:
        task = database.get_task(self.task_id)
        if not task:
            return

        database.update_task(self.task_id, status="running", started_at=database.now_iso())
        self.log("Task started")

        try:
            for stage in STAGES:
                self._run_stage(stage.name)
            database.update_task(
                self.task_id,
                status="succeeded",
                current_stage="done",
                final_video_path=str(_require(self.artifacts.final_video, "final_video")),
                completed_at=database.now_iso(),
            )
            self.log("Task succeeded")
        except Exception as exc:
            current = database.get_task(self.task_id)
            failed_stage = current["current_stage"] if current else None
            if failed_stage and failed_stage != "done":
                database.update_stage(
                    self.task_id,
                    failed_stage,
                    status="failed",
                    completed_at=database.now_iso(),
                    error_message=str(exc),
                    last_message="Failed",
                )
            database.update_task(
                self.task_id,
                status="failed",
                error_message=str(exc),
                completed_at=database.now_iso(),
            )
            self.log("Task failed")
            self.log(traceback.format_exc())

    def log(self, message: str) -> None:
        _write_log(self.task_id, message)

    def stage_message(self, stage: str, message: str) -> None:
        database.update_stage(self.task_id, stage, last_message=message)
        self.log(f"[{stage}] {message}")

    def _run_stage(self, stage: str) -> None:
        database.update_task(self.task_id, current_stage=stage)
        database.update_stage(
            self.task_id,
            stage,
            status="running",
            started_at=database.now_iso(),
            completed_at=None,
            error_message=None,
        )
        self.stage_message(stage, "Started")
        self._stage_handlers[stage](database.get_task(self.task_id))
        database.update_stage(
            self.task_id,
            stage,
            status="succeeded",
            completed_at=database.now_iso(),
            last_message="Completed",
        )
        self.log(f"[{stage}] Completed")

    def _download(self, task: dict) -> None:
        from .adapters.ytdlp import download_youtube

        proxy_port = database.get_ytdlp_settings()["proxy_port"]
        session, _ = download_youtube(task["url"], WORKFOLDER, YOUTUBE_COOKIE_PATH, proxy_port)
        self.artifacts.session = session
        self.artifacts.video_file = session / "media" / "video_source.mp4"
        database.update_task(self.task_id, session_path=str(session))
        self.stage_message("download", f"Downloaded to {session}")

    def _separate(self, _: dict) -> None:
        from .adapters.demucs import separate_audio

        session = _require(self.artifacts.session, "session")
        video_file = _require(self.artifacts.video_file, "video_file")
        self.artifacts.vocals_file, self.artifacts.bgm_file = separate_audio(video_file, session)
        self.stage_message("separate", "Separated vocals and background audio")

    def _asr(self, _: dict) -> None:
        from .adapters.funasr import recognize_speech

        session = _require(self.artifacts.session, "session")
        vocals_file = _require(self.artifacts.vocals_file, "vocals_file")
        self.artifacts.asr_file = recognize_speech(vocals_file, session)
        self.stage_message("asr", "Recognized speech")

    def _translate(self, _: dict) -> None:
        from .adapters.openai_translate import translate_asr

        session = _require(self.artifacts.session, "session")
        asr_file = _require(self.artifacts.asr_file, "asr_file")
        settings = database.get_openai_settings()
        self.artifacts.translation_file = translate_asr(asr_file, session, settings)
        self.stage_message("translate", "Translated utterances one by one")

    def _split_audio(self, _: dict) -> None:
        from .adapters.audio import split_audio_by_translation

        session = _require(self.artifacts.session, "session")
        vocals_file = _require(self.artifacts.vocals_file, "vocals_file")
        translation_file = _require(self.artifacts.translation_file, "translation_file")
        self.artifacts.vocals_dir = split_audio_by_translation(vocals_file, translation_file, session)
        self.stage_message("split_audio", "Created vocal reference segments")

    def _tts(self, _: dict) -> None:
        from .adapters.voxcpm import generate_tts

        session = _require(self.artifacts.session, "session")
        translation_file = _require(self.artifacts.translation_file, "translation_file")
        vocals_dir = _require(self.artifacts.vocals_dir, "vocals_dir")
        self.artifacts.tts_dir = generate_tts(translation_file, vocals_dir, session)
        self.stage_message("tts", "Generated Chinese dubbing segments")

    def _merge_audio(self, _: dict) -> None:
        from .adapters.audio import merge_tts_audio

        session = _require(self.artifacts.session, "session")
        translation_file = _require(self.artifacts.translation_file, "translation_file")
        tts_dir = _require(self.artifacts.tts_dir, "tts_dir")
        self.artifacts.dubbing_file = merge_tts_audio(translation_file, tts_dir, session)
        self.stage_message("merge_audio", "Merged dubbing timeline")

    def _merge_video(self, _: dict) -> None:
        from .adapters.ffmpeg import merge_video

        session = _require(self.artifacts.session, "session")
        video_file = _require(self.artifacts.video_file, "video_file")
        dubbing_file = _require(self.artifacts.dubbing_file, "dubbing_file")
        bgm_file = _require(self.artifacts.bgm_file, "bgm_file")
        translation_file = _require(self.artifacts.translation_file, "translation_file")
        self.artifacts.final_video = merge_video(video_file, dubbing_file, bgm_file, translation_file, session)
        self.stage_message("merge_video", "Created final video")


def run_task(task_id: str) -> None:
    PipelineRunner(task_id).run()
