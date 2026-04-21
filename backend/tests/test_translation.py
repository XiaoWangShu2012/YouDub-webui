from __future__ import annotations

import json

from backend.app.adapters import openai_translate


def test_translate_asr_calls_once_per_utterance(monkeypatch, tmp_path):
    session = tmp_path
    metadata = session / "metadata"
    metadata.mkdir()
    asr_file = metadata / "asr.json"
    asr_file.write_text(
        json.dumps(
            {
                "result": {
                    "utterances": [
                        {"text": "Hello.", "start_time": 0, "end_time": 1000},
                        {"text": "World.", "start_time": 1000, "end_time": 2000},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_translate(text, **settings):
        calls.append(text)
        return f"zh:{text}"

    monkeypatch.setattr(openai_translate, "translate_sentence", fake_translate)

    output = openai_translate.translate_asr(
        asr_file,
        session,
        {"base_url": "https://example.com/v1", "api_key": "sk-test", "model": "model"},
    )

    assert calls == ["Hello.", "World."]
    data = json.loads(output.read_text(encoding="utf-8"))
    assert [item["zh"] for item in data["translation"]] == ["zh:Hello.", "zh:World."]

