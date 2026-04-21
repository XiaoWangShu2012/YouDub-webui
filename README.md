# YouDub WebUI

Minimal single-machine YouTube dubbing console.

## Stack

- Frontend: Next.js App Router, shadcn/ui, Lucide icons
- Backend: FastAPI, SQLite, local files
- Pipeline: yt-dlp -> Demucs -> FunASR -> OpenAI-compatible translation -> VoxCPM2 -> FFmpeg
- Model downloads: ModelScope first for FunASR and VoxCPM2

The MVP runs one task at a time. Every stage is executed serially.

## Layout

```text
apps/web/          Next.js UI
backend/app/       FastAPI API and pipeline
backend/tests/     Backend tests
data/              SQLite, cookies, logs (ignored)
workfolder/        Video/session artifacts (ignored)
```

## Setup

Use Aliyun mirrors first. Do not pass Tsinghua as `--extra-index-url`; pip merges indexes and may choose Tsinghua even when Aliyun has the package. Retry individual failed packages with Tsinghua only when Aliyun fails.

```bash
cd /Users/liuzhao/code/YouDub-webui
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install \
  -i https://mirrors.aliyun.com/pypi/simple/ \
  -r requirements.txt
git submodule update --init --recursive
npm --prefix apps/web install --registry=https://registry.npmmirror.com
```

Fallback example for a package that fails from Aliyun:

```bash
.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ <package-name>
```

Create runtime env from the example:

```bash
cp .env.example .env
```

If editing env values through Codex, use `env.txt` and copy values into `.env` for application runtime.

## Run

Backend:

```bash
.venv/bin/uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
npm --prefix apps/web run dev
```

Open:

```text
http://localhost:3000
```

The UI lets you save YouTube cookies, save OpenAI-compatible API settings, submit one YouTube URL, watch stage progress, and download the final video.

## API

- `POST /api/tasks`
- `GET /api/tasks/current`
- `GET /api/tasks/{id}`
- `GET /api/tasks/{id}/log`
- `GET /api/tasks/{id}/artifact/final-video`
- `GET/POST /api/cookies/youtube`
- `GET/POST /api/settings/openai`

## Pipeline Artifacts

Each task writes a session under:

```text
workfolder/{uploader_slug}/{title_slug}__{video_id}/
```

Key files:

- `media/video_source.mp4`
- `media/audio_vocals.wav`
- `media/audio_bgm.wav`
- `metadata/asr.json`
- `metadata/translation.zh.json`
- `segments/vocals/*.wav`
- `segments/tts/*.wav`
- `tmp/audio_dubbing.wav`
- `metadata/subtitles.zh.srt`
- `media/video_final.mp4`

## Demucs Source

Demucs is a git submodule at `submodule/demucs`. The PyPI release is not used because the app imports `demucs.api`, which is available from the source tree.

## ModelScope

FunASR uses ModelScope model IDs directly. VoxCPM2 is downloaded through `modelscope.snapshot_download` before loading:

```text
OpenBMB/VoxCPM2 -> data/modelscope/OpenBMB__VoxCPM2
```

Set `MODEL_CACHE_DIR` to place model caches on a large disk, for example `/data1/liuzhao/modelscope_cache`.

## Test

```bash
.venv/bin/pytest backend/tests
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
