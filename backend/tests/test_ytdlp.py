from pathlib import Path

from backend.app.adapters import ytdlp


def test_ytdlp_proxy_port_takes_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("HTTP_PROXY", "http://env-proxy:8080")

    options = ytdlp._ydl_base(Path(tmp_path / "missing-cookie.txt"), "7890")

    assert options["proxy"] == "http://127.0.0.1:7890"


def test_ytdlp_proxy_falls_back_to_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("HTTP_PROXY", "http://env-proxy:8080")

    options = ytdlp._ydl_base(Path(tmp_path / "missing-cookie.txt"), "")

    assert options["proxy"] == "http://env-proxy:8080"


def test_ytdlp_enables_node_js_runtime(tmp_path):
    options = ytdlp._ydl_base(Path(tmp_path / "missing-cookie.txt"), "")

    assert options["js_runtimes"] == {"node": {}}


def test_ytdlp_format_candidates_start_with_backend_format():
    assert ytdlp.FORMAT_CANDIDATES[0] == "bestvideo[height<=1080]+bestaudio/best"
    assert "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best" not in ytdlp.FORMAT_CANDIDATES
