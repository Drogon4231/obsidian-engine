# The Obsidian Archive — Railway Deployment Checklist

## Overview
This project runs as a **headless worker** on Railway.
It has no HTTP server — the container runs `scheduler.py --daemon` continuously,
producing videos on schedule and uploading them to YouTube.

---

## Step 1 — One-time local setup (before deploying)

### 1a. Generate YouTube OAuth token locally
The YouTube upload API requires an interactive OAuth flow that **cannot run inside Railway**.
You must generate `youtube_token.json` on your local machine first:

```bash
cd ~/Desktop/Obsidian
python3 11_youtube_uploader.py
# Browser will open — log in with your YouTube channel account
# Token is saved to youtube_token.json
```

The token now includes the `yt-analytics.readonly` scope (required by Agent 12).
**Keep this file safe — it grants upload access to your channel.**

### 1b. Upload the token to Railway as a secret file
In Railway dashboard → your service → **Variables** → add:
```
YOUTUBE_TOKEN_JSON = <paste the full contents of youtube_token.json here>
```
Then in `11_youtube_uploader.py`, the startup can write this back to disk.
*(Or mount it as a volume — see Step 4.)*

---

## Step 2 — Set all environment variables in Railway dashboard

Go to: Railway dashboard → your project → your service → **Variables**

### Required — pipeline will fail without these

| Variable             | Description                                              |
|----------------------|----------------------------------------------------------|
| `ANTHROPIC_API_KEY`  | Claude API key — used by every agent                     |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS API key — Stage 8 audio production        |
| `FAL_KEY`            | fal.ai key — Stage 10 AI image generation                |
| `FAL_API_KEY`        | **Must match `FAL_KEY`** — `run_pipeline.py` reads this name specifically (`os.getenv("FAL_API_KEY")`) |
| `PEXELS_API_KEY`     | Pexels video search — Stage 9 footage hunting            |
| `SUPABASE_URL`       | Your Supabase project URL (`https://xxx.supabase.co`)    |
| `SUPABASE_KEY`       | Supabase `service_role` or `anon` key                    |

> ⚠️ **Note on `FAL_KEY` vs `FAL_API_KEY`:** Set **both** to the same value.
> The fal-client SDK reads `FAL_KEY`; `run_pipeline.py` reads `FAL_API_KEY`.

### Required — for YouTube upload & analytics

| Variable                  | Description                                       |
|---------------------------|---------------------------------------------------|
| `YOUTUBE_TOKEN_JSON`      | Full JSON contents of `youtube_token.json`         |

### Optional

| Variable               | Description                                          |
|------------------------|------------------------------------------------------|
| `PYTHONUNBUFFERED`     | Set to `1` (already in Dockerfile, but safe to repeat) |

---

## Step 3 — Write youtube_token.json at container startup

Add this to the **top of `scheduler.py`** (after `load_dotenv`) so the token file
is restored from the env var each time the container starts:

```python
# Restore YouTube token from env var (Railway secret)
_token_json = os.getenv("YOUTUBE_TOKEN_JSON", "")
if _token_json:
    token_path = Path(__file__).parent / "youtube_token.json"
    token_path.write_text(_token_json)
```

---

## Step 4 — Mount a persistent volume for outputs

Railway containers are **ephemeral** — the filesystem is wiped on each deploy.
All rendered videos, audio files, and state JSON live in `outputs/`.

In Railway dashboard → your service → **Volumes**:
- Mount path: `/app/outputs`
- Size: start with **20 GB** (each video ~500MB–2GB rendered)

> Without this volume, every restart loses all rendered content.

---

## Step 5 — Deploy

```bash
# Push to the Git repo connected to Railway
git add .
git commit -m "Add Railway deployment files"
git push origin main
```

Railway detects the `Dockerfile` via `railway.toml` and builds automatically.
Build time: **~8–12 minutes** (Node + Python deps + Remotion Chromium download).

---

## Step 6 — Verify deployment

In Railway dashboard → **Logs**, you should see:
```
============================================================
  DAEMON MODE — 2x/week
============================================================
  Scheduled: Daily at 06:00 (analytics)
  Scheduled: Tuesday at 09:00
  Scheduled: Friday at 09:00

[Scheduler] Running... (Ctrl+C to stop)
```

If you see import errors, check that all env vars in Step 2 are set.

---

## Schedule summary

| Time (UTC)     | Job                                        |
|----------------|--------------------------------------------|
| Every Monday 08:00  | Topic discovery (Agent 00)            |
| Every Tuesday 09:00 | Full video pipeline                   |
| Every Friday 09:00  | Full video pipeline                   |
| Every day 06:00     | Analytics feedback loop (Agent 12)    |
| Every 5th video     | Experiment video (20% DNA budget)     |

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `SUPABASE_URL and SUPABASE_KEY must be set` | Missing env vars in Railway |
| `No rendered video found` | Volume not mounted, outputs/ is empty |
| `YouTube token deleted — re-authentication required` | `youtube_token.json` missing — restore from `YOUTUBE_TOKEN_JSON` env var |
| `FATAL: Fact verification requires full rewrite` | Twist reveal unverifiable — topic needs to be re-queued with a different angle |
| `Pipeline halted: script too short` | Claude returned < 1000 words — retry the topic |
| Remotion render crash | Chrome deps missing — check Dockerfile build logs |
