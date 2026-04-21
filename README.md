# YouDub WebUI

YouDub WebUI is a minimal local YouTube-to-Chinese-dubbing console. The current project is a single repository containing a Next.js frontend and a FastAPI backend. It is intentionally small: one page, one active task, one serial media pipeline, local SQLite state, and local filesystem artifacts.

## What It Does

The app takes one YouTube video URL and runs these stages in order:

1. `download`: download one YouTube video with yt-dlp.
2. `separate`: split vocals and background music with Demucs.
3. `asr`: recognize speech with FunASR / SenseVoice.
4. `translate`: translate each utterance independently through an OpenAI-compatible Chat API.
5. `split_audio`: cut vocal reference segments from the original vocal track.
6. `tts`: generate Chinese dubbing with VoxCPM2.
7. `merge_audio`: align generated speech onto the original timeline.
8. `merge_video`: mix background music, dubbing, subtitles, and source video with FFmpeg.

There is no Redis, Postgres, worker queue, playlist monitor, Bilibili upload, cover editor, or concurrent execution in this MVP.

## Current Stack

- Frontend: Next.js App Router, shadcn/ui-style components, Lucide icons, light mode only.
- Backend: FastAPI, SQLite, local file storage.
- Download: yt-dlp with YouTube cookies, optional local proxy port, Node-based EJS challenge solving.
- Separation: Demucs source checkout as a git submodule.
- ASR: FunASR `iic/SenseVoiceSmall` with `fsmn-vad`.
- Translation: OpenAI-compatible Chat Completions API, one request per utterance.
- TTS: VoxCPM2 from ModelScope.
- Media: FFmpeg / ffprobe.
- Runtime target used during development: `gil-gpu:/data1/liuzhao/YouDub-webui`, GPU1 via `CUDA_VISIBLE_DEVICES=1`.

## Repository Layout

```text
apps/web/                 Next.js frontend
apps/web/src/app/         Single-page console and app styles
apps/web/src/components/  shadcn/ui-style primitives
apps/web/src/lib/api.ts   Frontend API client
backend/app/              FastAPI app, SQLite repository, pipeline runner
backend/app/adapters/     yt-dlp, Demucs, FunASR, OpenAI, VoxCPM, FFmpeg adapters
backend/tests/            Backend unit and integration-style tests
data/                     Runtime DB, logs, cookies; ignored by git
workfolder/               Per-video task artifacts; ignored by git
submodule/demucs/         Demucs source submodule
env.txt.example           Runtime environment template
requirements.txt          Python dependencies
```

## Runtime Data

Runtime state is intentionally stored locally:

- `data/youdub.sqlite`: SQLite database.
- `data/cookies/youtube.txt`: Netscape-format YouTube cookie file.
- `data/logs/{task_id}.log`: task logs.
- `workfolder/{uploader_slug}/{title_slug}__{video_id}/`: task session directory.

These paths are ignored by git and should not be committed.

## Artifacts

Each task writes a session like:

```text
workfolder/{uploader_slug}/{title_slug}__{video_id}/
```

Important files:

```text
media/video_source.mp4
media/audio_vocals.wav
media/audio_bgm.wav
metadata/ytdlp_info.json
metadata/asr.json
metadata/translation.zh.json
metadata/subtitles.zh.srt
segments/vocals/*.wav
segments/tts/*.wav
tmp/audio_dubbing.wav
media/video_final.mp4
```

## API

Task endpoints:

- `POST /api/tasks`: submit a single YouTube URL. Returns `409` if a task is queued or running.
- `GET /api/tasks/current`: current or most recent task.
- `GET /api/tasks/{id}`: task details and stage statuses.
- `GET /api/tasks/{id}/log`: task log text.
- `GET /api/tasks/{id}/artifact/final-video`: final video download.

Settings endpoints:

- `GET /api/cookies/youtube`: returns cookie metadata only. Cookie content is never returned.
- `POST /api/cookies/youtube`: saves Netscape cookie content to `data/cookies/youtube.txt`.
- `GET /api/settings/openai`: returns base URL, model, `has_api_key`, and a masked API key.
- `POST /api/settings/openai`: saves OpenAI base URL, API key, and model.
- `POST /api/settings/openai/models`: fetches model IDs from the configured OpenAI-compatible `/models` API.
- `GET /api/settings/ytdlp`: returns the yt-dlp proxy port.
- `POST /api/settings/ytdlp`: saves the yt-dlp proxy port.

Utility:

- `GET /api/health`: basic health check.

## Frontend Behavior

The frontend is one vertical page:

1. Convert video card.
2. Progress card.
3. Task log card.

Settings are in a modal:

- YouTube cookie textarea.
- yt-dlp proxy port input.
- OpenAI base URL.
- OpenAI API key with show/hide button.
- Model input or model select after clicking `Get models`.

Sensitive values are masked in the UI:

- Saved API key appears as `********`.
- Saved YouTube cookie appears as a placeholder instead of being returned from the backend.
- Saving without editing a masked value keeps the existing secret.

The frontend polls `GET /api/tasks/current` every 2 seconds. There is no SSE or WebSocket.

## Environment

The app reads runtime values from `.env`. Codex should not read or edit `.env` directly. Use `env.txt` for editable local notes and copy values into `.env` when needed.

Template:

```bash
cp env.txt.example env.txt
```

Important variables:

```text
WORKFOLDER=./workfolder
MODEL_CACHE_DIR=./data/modelscope
DEVICE=cuda
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
YTDLP_PROXY_PORT=
FUNASR_MODEL=iic/SenseVoiceSmall
FUNASR_VAD_MODEL=fsmn-vad
VOXCPM_MODEL=OpenBMB/VoxCPM2
VOXCPM_MODEL_DIR=
HTTP_PROXY=
```

`YTDLP_PROXY_PORT` and the UI setting are ports only, for example `20171`. The backend converts that to `http://127.0.0.1:20171` for yt-dlp. If no proxy port is configured, yt-dlp can still use `HTTP_PROXY` / `http_proxy`.

## Install

Use Aliyun first. Do not configure Tsinghua as `--extra-index-url`; pip can choose packages from the fallback index even when Aliyun has them. If Aliyun fails for a specific package, retry that package separately with Tsinghua.

```bash
cd /Users/liuzhao/code/YouDub-webui
python3.12 -m venv .venv
.venv/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
git submodule update --init --recursive
npm --prefix apps/web install --registry=https://registry.npmmirror.com
```

Tsinghua fallback for one failed package:

```bash
.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ <package-name>
```

## Demucs

Demucs is intentionally used as a source submodule:

```text
submodule/demucs
```

The app imports `demucs.api.Separator`. The published PyPI package is not used for this import path because the required API is available from the source tree. Keep the submodule initialized before running the pipeline.

## yt-dlp Notes

The download adapter mirrors the working `youdub-backend` format strategy first:

```text
bestvideo[height<=1080]+bestaudio/best
```

It then falls back through wider selectors:

```text
bestvideo+bestaudio/best
bv*+ba/b
best
```

The project depends on `yt-dlp[default]`, which installs `yt-dlp-ejs`. The adapter also enables Node as the JavaScript runtime:

```python
js_runtimes={"node": {}}
```

This is needed for YouTube n-challenge solving. Node must be installed and available in `PATH`.

YouTube may still reject downloads when:

- the proxy IP is rate limited or challenged with HTTP 429;
- the cookie file is stale or incomplete;
- the browser rotated the account cookies after export.

When this happens, export a fresh Netscape-format cookie file from a logged-in YouTube browser session and paste it into Settings.

## Models

Model downloads should use ModelScope where possible.

Defaults:

- FunASR model: `iic/SenseVoiceSmall`
- FunASR VAD: `fsmn-vad`
- VoxCPM model: `OpenBMB/VoxCPM2`

VoxCPM2 is downloaded through `modelscope.snapshot_download`. Use `MODEL_CACHE_DIR` to place model caches on a large disk, for example:

```text
/data1/liuzhao/modelscope_cache
```

Known remote cache paths from the development machine:

```text
/data1/liuzhao/modelscope_cache/OpenBMB__VoxCPM2
/data1/liuzhao/modelscope_cache/models/iic/SenseVoiceSmall
/data1/liuzhao/modelscope_cache/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch
/data1/liuzhao/torch_cache/hub/checkpoints
```

Demucs weights are downloaded by the upstream Demucs source code into the PyTorch hub cache.

## Run Locally

Backend:

```bash
.venv/bin/uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
npm --prefix apps/web run dev -- --hostname 0.0.0.0 --port 3000
```

Open:

```text
http://localhost:3000
```

If the frontend is built for production, set `NEXT_PUBLIC_API_BASE_URL` at build time:

```bash
NEXT_PUBLIC_API_BASE_URL=http://172.27.2.90:8000 npm --prefix apps/web run build
npm --prefix apps/web run start -- --hostname 0.0.0.0 --port 3000
```

## Remote GPU Runbook

The development deployment currently uses:

```text
Host: gil-gpu
Path: /data1/liuzhao/YouDub-webui
GPU: CUDA_VISIBLE_DEVICES=1
Web: http://172.27.2.90:3000
API: http://172.27.2.90:8000
tmux sessions: youdub-api, youdub-web
```

Start backend:

```bash
tmux new-session -d -s youdub-api "\
cd /data1/liuzhao/YouDub-webui && \
export CUDA_VISIBLE_DEVICES=1 DEVICE=cuda \
MODEL_CACHE_DIR=/data1/liuzhao/modelscope_cache \
MODELSCOPE_CACHE=/data1/liuzhao/modelscope_cache \
TORCH_HOME=/data1/liuzhao/torch_cache \
CORS_ALLOW_ORIGINS=http://172.27.2.90:3000,http://100.94.222.54:3000 && \
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
```

Start frontend:

```bash
NEXT_PUBLIC_API_BASE_URL=http://172.27.2.90:8000 npm --prefix apps/web run build
tmux new-session -d -s youdub-web "\
cd /data1/liuzhao/YouDub-webui && \
NEXT_PUBLIC_API_BASE_URL=http://172.27.2.90:8000 \
npm --prefix apps/web run start -- --hostname 0.0.0.0 --port 3000"
```

Check status:

```bash
curl -sS http://127.0.0.1:8000/api/health
curl -I http://127.0.0.1:3000
tmux ls
```

## Tests

Backend:

```bash
.venv/bin/pytest backend/tests
```

Frontend:

```bash
npm --prefix apps/web run lint
npm --prefix apps/web run build
```

Current backend coverage includes:

- YouTube URL validation.
- Cookie and API key masking.
- OpenAI model listing endpoint.
- yt-dlp proxy port validation.
- yt-dlp format selector order and Node EJS runtime setting.
- fixed serial stage status progression.
- mocked full pipeline success and failure behavior.
- translation one-request-per-utterance behavior.
- FFmpeg helper behavior.

## Current Limitations

- Only one active task is supported.
- No task cancel endpoint yet.
- No task deletion or cleanup UI yet.
- No playlist/channel monitoring.
- No Bilibili upload.
- No user accounts or multi-user security model.
- YouTube cookie content is stored locally in plaintext.
- OpenAI API key is stored locally in plaintext.
- The UI shows progress by polling, not streaming logs.

## Operational Notes

- Keep `.env`, `data/`, `workfolder/`, model caches, downloaded videos, and cookies out of git.
- Re-export YouTube cookies when yt-dlp reports `cookies are no longer valid` or `Sign in to confirm you're not a bot`.
- Keep proxy port configured when the server needs v2rayA or another local proxy.
- If using Tailscale IP for the frontend, rebuild the frontend with `NEXT_PUBLIC_API_BASE_URL` pointing to the matching API IP.
- For dependency installs, Aliyun is the primary source; Tsinghua is manual fallback only.
