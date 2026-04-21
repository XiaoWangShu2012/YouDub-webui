from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import database
from backend.app import main


def configure_tmp_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.sqlite")
    monkeypatch.setattr(main, "YOUTUBE_COOKIE_PATH", tmp_path / "cookies" / "youtube.txt")
    database.init_db()


def test_openai_key_is_masked(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    database.save_openai_settings("https://example.com/v1", "sk-test-secret", "test-model")
    client = TestClient(main.app)

    response = client.get("/api/settings/openai")

    assert response.status_code == 200
    body = response.json()
    assert body["api_key"] == "********"
    assert body["has_api_key"] is True
    assert "sk-test-secret" not in str(body)


def test_masked_openai_key_is_not_saved_back(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    database.save_openai_settings("https://example.com/v1", "sk-test-secret", "test-model")
    client = TestClient(main.app)

    response = client.post(
        "/api/settings/openai",
        json={"base_url": "https://example.com/v1", "api_key": "********", "model": "next-model"},
    )

    assert response.status_code == 200
    settings = database.get_openai_settings()
    assert settings["api_key"] == "sk-test-secret"
    assert settings["model"] == "next-model"


def test_cookie_response_does_not_leak_content(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    client = TestClient(main.app)

    response = client.post("/api/cookies/youtube", json={"content": "secret-cookie-content"})

    assert response.status_code == 200
    assert response.json()["content"] == ""
    assert "secret-cookie-content" not in response.text


def test_running_task_blocks_second_submit(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "run_task", lambda task_id: None)
    client = TestClient(main.app)
    payload = {"url": "https://www.youtube.com/watch?v=abcdefghijk"}

    first = client.post("/api/tasks", json=payload)
    second = client.post("/api/tasks", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_cors_origins_include_runtime_configuration(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://172.27.2.90:3000, http://100.94.222.54:3000")

    origins = main.cors_origins()

    assert "http://localhost:3000" in origins
    assert "http://172.27.2.90:3000" in origins
    assert "http://100.94.222.54:3000" in origins


def test_openai_models_use_form_key_without_leaking_it(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    captured = {}

    def fake_list_models(*, base_url: str, api_key: str) -> list[str]:
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        return ["gpt-test", "qwen-test"]

    monkeypatch.setattr(main, "list_openai_models", fake_list_models)
    client = TestClient(main.app)

    response = client.post(
        "/api/settings/openai/models",
        json={"base_url": "https://example.com/v1", "api_key": "sk-secret-models"},
    )

    assert response.status_code == 200
    assert response.json() == {"models": ["gpt-test", "qwen-test"]}
    assert captured == {"base_url": "https://example.com/v1", "api_key": "sk-secret-models"}
    assert "sk-secret-models" not in response.text


def test_openai_models_can_use_saved_key(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    database.save_openai_settings("https://saved.example/v1", "sk-saved", "saved-model")
    captured = {}

    def fake_list_models(*, base_url: str, api_key: str) -> list[str]:
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        return ["saved-model"]

    monkeypatch.setattr(main, "list_openai_models", fake_list_models)
    client = TestClient(main.app)

    response = client.post("/api/settings/openai/models", json={"base_url": "", "api_key": ""})

    assert response.status_code == 200
    assert response.json() == {"models": ["saved-model"]}
    assert captured == {"base_url": "https://saved.example/v1", "api_key": "sk-saved"}


def test_ytdlp_proxy_port_settings(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    client = TestClient(main.app)

    saved = client.post("/api/settings/ytdlp", json={"proxy_port": "7890"})
    loaded = client.get("/api/settings/ytdlp")

    assert saved.status_code == 200
    assert loaded.status_code == 200
    assert loaded.json() == {"proxy_port": "7890"}


def test_ytdlp_proxy_port_rejects_invalid_value(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    client = TestClient(main.app)

    response = client.post("/api/settings/ytdlp", json={"proxy_port": "70000"})

    assert response.status_code == 422
