from __future__ import annotations

import json
from pathlib import Path

from openai import OpenAI


SYSTEM_PROMPT = (
    "You are a precise video subtitle translator. Translate each input sentence into natural "
    "Simplified Chinese. Return only the translated sentence. Do not add explanations, labels, "
    "quotes, markdown, or extra whitespace."
)


def list_models(*, base_url: str, api_key: str) -> list[str]:
    if not api_key:
        raise ValueError("OpenAI API key is not configured.")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.models.list()
    seen: set[str] = set()
    models: list[str] = []
    for item in response.data:
        model_id = getattr(item, "id", "")
        if model_id and model_id not in seen:
            seen.add(model_id)
            models.append(model_id)
    return models


def translate_sentence(text: str, *, base_url: str, api_key: str, model: str) -> str:
    if not api_key:
        raise ValueError("OpenAI API key is not configured.")
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.2,
    )
    translated = response.choices[0].message.content or ""
    return translated.strip()


def translate_asr(asr_file: Path, session: Path, settings: dict[str, str]) -> Path:
    output_file = session / "metadata" / "translation.zh.json"
    if output_file.exists():
        return output_file

    data = json.loads(asr_file.read_text(encoding="utf-8"))
    translation = []
    for utterance in data["result"]["utterances"]:
        text = utterance["text"].strip()
        translated = translate_sentence(text, **settings)
        translation.append(
            {
                "en": text,
                "zh": translated,
                "start_time": utterance["start_time"],
                "end_time": utterance["end_time"],
            }
        )

    output_file.write_text(json.dumps({"translation": translation}, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_file
