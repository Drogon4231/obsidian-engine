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
| 1. Research | Deep-dives into the topic using AI |
| 2. Originality | Finds a unique angle nobody has covered |
| 3. Narrative | Architects a story structure with hooks and pacing |
| 4. Script | Writes a broadcast-quality narration script |
| 4b. Script Doctor | Scores and rewrites until quality threshold is met |
| 5. Verification | Fact-checks every claim in the script |
| 6. SEO | Generates titles, descriptions, tags optimized for YouTube |
| 7. Storyboard | Breaks the script into visual scenes |
| 7b. Visual Continuity | Ensures visual consistency across scenes |
| 8. Audio | Generates narration via text-to-speech |
| 9. Footage | Finds relevant stock footage |
| 10. Images | Generates AI images for scenes that need them |
| 11. Video | Renders the final video using Remotion |
| 12. QA | Quality checks the output |
| 13. Upload | Uploads to YouTube (or saves locally) |

Each stage has quality gates, automatic retries, and self-healing error recovery.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (recommended) or local setup
- API keys (see below)

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/Drogon4231/obsidian-engine.git
cd obsidian-engine

cp .env.example .env
# Edit .env with your keys (see "Getting API Keys" below)

docker compose up --build
```

Open `http://localhost:8080` and use the **Setup Wizard** (SETUP tab) to configure everything from the browser.

### Option 2: Local Setup

```bash
git clone https://github.com/Drogon4231/obsidian-engine.git
cd obsidian-engine

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cd remotion && npm install && cd ..
cd dashboard && npm install && npm run build && cd ..

cp .env.example .env
# Edit .env with your keys

# Run a single video
python run_pipeline.py "The History of the Internet"
```

### Option 3: CLI One-Shot

```bash
python run_pipeline.py "The Rise and Fall of the Roman Empire"

# Resume a failed run
python run_pipeline.py "The Rise and Fall of the Roman Empire" --resume

# Start from a specific stage
python run_pipeline.py "The Rise and Fall of the Roman Empire" --from-stage 8
```

## Getting API Keys

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

Typical cost for a 15-minute video:

| Service | Cost |
|---------|------|
| Claude (Anthropic) | $0.50 - $1.50 |
| ElevenLabs (TTS) | $0.30 - $0.80 |
| fal.ai (images) | $0.20 - $0.50 |
| Pexels (footage) | Free |
| **Total** | **$1.00 - $2.80** |

## Content Profiles

Profiles control the tone, structure, and visual style of generated videos. Change one line in `obsidian.yaml`:

```yaml
profile: explainer  # or documentary, true_crime, video_essay
```

| Profile | Style | Think... |
|---------|-------|----------|
| `documentary` | Cinematic, authoritative, dark history | Netflix/HBO docs |
| `explainer` | Clear, curious, educational | Kurzgesagt, Wendover |
| `true_crime` | Measured, investigative, suspenseful | JCS, That Chapter |
| `video_essay` | Thoughtful, analytical, personal | Nerdwriter, Philosophy Tube |

**Create your own:** Copy `profiles/_template.yaml`, customize, and set `profile: your_name` in `obsidian.yaml`.

## Pluggable Providers

Swap any external service by changing `obsidian.yaml`:

```yaml
providers:
  llm:
    name: openai          # Switch from Claude to GPT
  tts:
    name: elevenlabs      # Default TTS
  images:
    name: fal             # AI image generation
  footage:
    name: pexels          # Stock footage
  upload:
    name: local           # Save to disk instead of YouTube
```

Built-in providers: `anthropic`, `openai`, `elevenlabs`, `fal`, `pexels`, `local`

Or use a custom provider class: `name: my_package.module.MyProvider`

## Configuration

All pipeline behavior is controlled from `obsidian.yaml`:

```yaml
profile: documentary          # Content style

voice:
  narrator_id: "JBFqnCBsd6RMkjVDRZzb"   # ElevenLabs voice ID
  speed_body: 0.76                        # Narration speed

models:
  premium: "claude-opus-4-6"     # Creative tasks
  full: "claude-sonnet-4-6"      # Complex reasoning
  light: "claude-haiku-4-5-20251001"  # Fast tasks

cost:
  budget_max_usd: 5.00           # Max spend per video (0 = unlimited)

video:
  fps: 30
  long_width: 1920
  long_height: 1080
```

See `obsidian.yaml` for all options with documentation.

## Dashboard

Real-time monitoring UI at `http://localhost:8080` with 6 tabs:

| Tab | What It Shows |
|-----|--------------|
| HOME | Pipeline status, live logs, run history |
| QUEUE | Topic queue browser |
| INTEL | Analytics and performance insights |
| HEALTH | Error summary, agent stats, traces |
| TUNING | Parameter optimization with AI recommendations |
| SETUP | Guided setup wizard for initial configuration |

Keyboard shortcuts: `1`-`6` switch tabs, `T` triggers a run, `L` toggles logs, `?` shows help.

## Architecture

```
obsidian-engine/
├── run_pipeline.py       # Entry point
├── obsidian.yaml         # All configuration
├── profiles/             # Content style profiles
├── providers/            # Pluggable service backends
│   ├── base.py           #   Abstract base classes
│   ├── registry.py       #   Provider factory
│   ├── llm/              #   Anthropic, OpenAI
│   ├── tts/              #   ElevenLabs
│   ├── images/           #   fal.ai
│   ├── footage/          #   Pexels
│   └── upload/           #   Local save
├── agents/               # 15 specialized AI agents
├── core/                 # Config, logging, costs, schemas
├── pipeline/             # Media processing (audio, images, video)
├── clients/              # API clients (Claude, Supabase)
├── server/               # Webhook server + notifications
├── dashboard/            # Monitoring UI (Preact + Signals + Tailwind)
├── remotion/             # Video renderer (React + Remotion)
├── intel/                # Competitive intelligence
├── tests/                # 1400+ tests
├── Dockerfile
└── docker-compose.yml
```

## Features

- **Any content style** - Documentary, explainer, true crime, video essay, or custom profiles
- **Swappable backends** - Change LLM, TTS, image, footage, or upload provider in one line
- **Setup wizard** - Browser-based configuration for non-technical users
- **Self-healing pipeline** - Automatic retries, pipeline doctor for stage-level recovery
- **Quality gates** - Every stage validates output before proceeding
- **Cost tracking** - Real-time token counting and budget caps
- **Resume support** - Crash-safe state persistence, resume from any stage
- **Thread-safe** - Parallel execution with proper locking
- **Dashboard** - Real-time monitoring via Server-Sent Events
- **Notifications** - Telegram + Discord alerts on completion/failure
- **Series detection** - Automatically identifies multi-part topics
- **Shorts pipeline** - Generates YouTube Shorts alongside long-form

## Running Tests

```bash
# Python tests (1400+ tests)
python -m pytest tests/ -v --tb=short --cov=. --cov-fail-under=26

# Linting
ruff check --select E,F,W --ignore E501,E402 --exclude remotion .

# Dashboard tests
cd dashboard && npm test

# Remotion tests
cd remotion && npm test
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, project invariants, and PR process.

## License

MIT - see [LICENSE](LICENSE).
