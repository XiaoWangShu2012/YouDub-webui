from __future__ import annotations

from pathlib import Path

from backend.app import database
from backend.app.pipeline import PipelineRunner


def configure_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.sqlite")
    database.init_db()


def _noop_stage(self, task):
    return None


def test_pipeline_marks_all_stages_succeeded(monkeypatch, tmp_path):
    configure_db(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=abcdefghijk")
    final_path = tmp_path / "video_final.mp4"
    final_path.write_bytes(b"mp4")

    for name in ("_download", "_separate", "_asr", "_translate", "_split_audio", "_tts", "_merge_audio"):
        monkeypatch.setattr(PipelineRunner, name, _noop_stage)

    def merge_video(self, task):
        self.artifacts.final_video = final_path

    monkeypatch.setattr(PipelineRunner, "_merge_video", merge_video)

    PipelineRunner(task_id).run()
    task = database.get_task(task_id)

    assert task["status"] == "succeeded"
    assert task["final_video_path"] == str(final_path)
    assert [stage["status"] for stage in task["stages"]] == ["succeeded"] * 8


def test_pipeline_failure_stops_following_stages(monkeypatch, tmp_path):
    configure_db(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=abcdefghijk")

    monkeypatch.setattr(PipelineRunner, "_download", _noop_stage)
    monkeypatch.setattr(PipelineRunner, "_separate", _noop_stage)

    def fail_asr(self, task):
        raise RuntimeError("asr exploded")

    monkeypatch.setattr(PipelineRunner, "_asr", fail_asr)

    PipelineRunner(task_id).run()
    task = database.get_task(task_id)
    stages = {stage["name"]: stage for stage in task["stages"]}

    assert task["status"] == "failed"
    assert stages["asr"]["status"] == "failed"
    assert stages["translate"]["status"] == "pending"
    assert task["error_message"] == "asr exploded"

