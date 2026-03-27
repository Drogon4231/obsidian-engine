# Obsidian Engine

**Open-source AI video pipeline.** Generate full YouTube videos from a single topic — documentary, essay, explainer, true crime, or any style you define.

```
Topic → Research → Script → Narration → Visuals → Video → Upload
```

One command in, finished video out.

---

## What It Does

Obsidian Engine is a 13-stage automated pipeline that turns a topic into a complete, narrated, visually-rich YouTube video:

| Stage | What Happens |
|-------|-------------|
| 1. Research | Deep-dives into the topic using Claude AI |
| 2. Originality | Finds a unique angle nobody has covered |
| 3. Narrative | Architects a story structure with hooks and pacing |
| 4. Script | Writes a broadcast-quality narration script |
| 4b. Script Doctor | Scores and rewrites until quality threshold is met |
| 5. Verification | Fact-checks every claim in the script |
| 6. SEO | Generates titles, descriptions, tags optimized for YouTube |
| 7. Storyboard | Breaks the script into visual scenes |
| 7b. Visual Continuity | Ensures visual consistency across scenes |
| 8. Audio | Generates narration via text-to-speech |
| 9. Footage | Finds relevant stock footage from Pexels |
| 10. Images | Generates AI images for scenes that need them |
| 11. Video | Renders the final video using Remotion |
| 12. QA | Quality checks the output |
| 13. Upload | Uploads to YouTube with metadata |

Each stage has quality gates, automatic retries, and self-healing error recovery.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (recommended) or local setup
- API keys (see below)

### Option 1: Docker (Recommended)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/obsidian-engine.git
cd obsidian-engine

# Configure your API keys
cp .env.example .env
# Edit .env with your keys (see "Getting API Keys" below)

# Run
docker compose up --build
```

The dashboard opens at `http://localhost:8080`.

### Option 2: Local Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/obsidian-engine.git
cd obsidian-engine

# Python environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Remotion (video renderer)
cd remotion && npm install && cd ..

# Dashboard (monitoring UI)
cd dashboard && npm install && cd ..

# Configure
cp .env.example .env
# Edit .env with your keys

# Run a single video
python run_pipeline.py "The History of the Internet"

# Or run the scheduler daemon (auto-discovers topics)
python scheduler.py --daemon
```

### Option 3: CLI One-Shot

```bash
# Generate a single video
python run_pipeline.py "The Rise and Fall of the Roman Empire"

# Resume a failed run
python run_pipeline.py "The Rise and Fall of the Roman Empire" --resume

# Start from a specific stage
python run_pipeline.py "The Rise and Fall of the Roman Empire" --from-stage 8
```

## Getting API Keys

You need these API keys to run the pipeline:

| Service | Purpose | Free Tier? | Get It |
|---------|---------|-----------|--------|
| **Anthropic** | AI text generation (Claude) | $5 free credit | [console.anthropic.com](https://console.anthropic.com) |
| **ElevenLabs** | Text-to-speech narration | 10k chars/month | [elevenlabs.io](https://elevenlabs.io) |
| **fal.ai** | AI image generation | $10 free credit | [fal.ai](https://fal.ai) |
| **Pexels** | Stock footage | Unlimited free | [pexels.com/api](https://www.pexels.com/api/new/) |

Optional:
| Service | Purpose | Get It |
|---------|---------|--------|
| Supabase | Database for analytics | [supabase.com](https://supabase.com) |
| YouTube API | Auto-upload | [Google Cloud Console](https://console.cloud.google.com) |
| Telegram | Notifications | Message [@BotFather](https://t.me/BotFather) |

## Cost Per Video

Typical cost for a 15-minute documentary:

| Service | Cost |
|---------|------|
| Claude (Anthropic) | $0.50 – $1.50 |
| ElevenLabs (TTS) | $0.30 – $0.80 |
| fal.ai (images) | $0.20 – $0.50 |
| Pexels (footage) | Free |
| **Total** | **$1.00 – $2.80** |

## Architecture

```
run_pipeline.py          ← Entry point
├── pipeline/
│   ├── context.py       ← PipelineContext (shared state)
│   ├── runner.py        ← StageRunner (orchestration)
│   ├── phase_setup.py   ← Init, credit checks, agent loading
│   ├── phase_script.py  ← Stages 1-5 (research → verification)
│   ├── phase_prod.py    ← Stages 6-11 (SEO → video render)
│   └── phase_post.py    ← Stage 12-13 (QA → upload)
├── agents/              ← 15 specialized AI agents
├── core/                ← Infrastructure (logging, costs, schemas)
├── clients/             ← API clients (Claude, Supabase)
├── server/              ← Webhook server + notifications
├── remotion/            ← Video renderer (React/TypeScript)
├── dashboard/           ← Monitoring UI (Preact + Signals)
└── intel/               ← Competitive intelligence & trends
```

## Features

- **Self-healing pipeline** — Automatic retries with exponential backoff, pipeline doctor for stage-level recovery
- **Quality gates** — Every stage validates its output before proceeding
- **Cost tracking** — Real-time token counting and budget caps
- **Resume support** — Crash-safe state persistence, resume from any stage
- **Thread-safe** — Parallel execution with proper locking for shared state
- **Structured logging** — JSON logs with rotating file handler
- **Dashboard** — Real-time pipeline monitoring via SSE
- **Notifications** — Telegram + Discord alerts on completion/failure
- **Series detection** — Automatically identifies multi-part topics
- **Shorts pipeline** — Generates YouTube Shorts alongside long-form

## Configuration

Key settings in `core/pipeline_config.py`:

```python
COST_BUDGET_MAX_USD = 5.00      # Max spend per video
SCRIPT_MIN_WORDS = 1500         # Minimum script length
SCRIPT_DOCTOR_MIN_SCORE = 7.0   # Minimum quality score (1-10)
MAX_PARALLEL_WORKERS = 3        # ThreadPoolExecutor workers
```

Voice settings in `pipeline/voice.py` — change narrator/quote voices by updating the ElevenLabs voice IDs in your `.env`.

## Running Tests

```bash
# Python tests
python -m pytest tests/ -v --tb=short --cov=. --cov-fail-under=26

# Linting
ruff check --select E,F,W --ignore E501,E402 --exclude remotion .

# Remotion tests
cd remotion && npm test

# Remotion lint
cd remotion && npm run lint
```

## Project Structure

```
obsidian-engine/
├── agents/           # 15 AI agent modules (one per pipeline stage)
├── clients/          # API client wrappers (Claude, Supabase)
├── core/             # Infrastructure (logging, costs, schemas, optimizer)
├── dashboard/        # Monitoring UI (Preact + Tailwind)
├── docs/             # PRD and technical documentation
├── intel/            # Competitive intelligence engine
├── media/            # Static media assets
├── pipeline/         # Pipeline orchestration and media processing
├── remotion/         # Video renderer (React + Remotion)
├── scripts/          # Utility scripts
├── server/           # Webhook server + notifications
├── tests/            # Test suite (56 files, 1300+ tests)
├── run_pipeline.py   # Main entry point
├── scheduler.py      # Daemon mode with auto topic discovery
├── Dockerfile        # Production container
└── docker-compose.yml
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE).
