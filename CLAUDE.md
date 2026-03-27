# Obsidian Engine — Project Intelligence

## What This Is

Open-source AI video pipeline. Takes a topic, outputs a complete YouTube video. Pluggable providers, swappable content styles, browser-based setup wizard. MIT licensed.

**Repo:** https://github.com/Drogon4231/obsidian-engine

## Architecture

13-stage automated pipeline → rendered video → upload.

```
Topic → Research(1) → Originality(2) → Narrative(3) → Script(4) → ScriptDoctor(4b)
     → Verification(5) → SEO(6) → Scenes(7) → VisualContinuity(7b) → TTS(8)
     → Footage(9) → Images(10) → Video(11) → QA(12) → Upload(13)
```

**Core call chain:** `agents/*.py` → `core/agent_wrapper.py:call_agent()` → `clients/claude_client.py:call_claude()` → Anthropic API

### Key Files

| Area | Files |
|------|-------|
| Pipeline orchestrator | `run_pipeline.py` |
| Agent wrapper (SLA/recovery) | `core/agent_wrapper.py` |
| Claude API client | `clients/claude_client.py` |
| **Master config** | `obsidian.yaml` → `core/config.py` (dot-access `cfg` singleton) |
| **Config constants** | `core/pipeline_config.py` (reads from `cfg`, backward-compatible) |
| **Content profiles** | `profiles/*.yaml` → `core/profile.py` (loader + cache) |
| **Profile injection** | `intel/dna_loader.py:get_dna()` prepends style directive |
| **Provider abstraction** | `providers/base.py` (ABCs) → `providers/registry.py` (factory) |
| **Provider implementations** | `providers/llm/`, `providers/tts/`, `providers/images/`, `providers/footage/`, `providers/upload/` |
| Structured output schemas | `core/structured_schemas.py` |
| Observability | `core/observability.py` |
| Dashboard | `dashboard/src/` (Preact + Signals + Tailwind, 6 tabs including Setup Wizard) |
| Webhook server | `server/webhook_server.py` (Flask + SSE) |
| Setup wizard API | `server/webhook_server.py` (`/api/setup/status`, `/api/setup/validate`, `/api/setup/save`) |
| Notifications | `server/notify.py` (Telegram `_tg()` + Discord `_send()`) |
| Video renderer | `remotion/src/` |
| Scheduler | `scheduler.py` |

### Configuration System

All config flows through `obsidian.yaml` → `core/config.py`:

```python
from core.config import cfg
cfg.voice.narrator_id       # Dot-access to any YAML key
cfg.models.premium           # "claude-opus-4-6"
cfg.get("profile", "documentary")  # Safe access with default
cfg.voice.body.to_dict()    # Convert section to plain dict
```

Override priority: defaults → `obsidian.yaml` → env vars (`OBSIDIAN_` prefix)

### Profile System

Profiles control tone, structure, and visuals. Set in `obsidian.yaml`:
```yaml
profile: documentary  # or explainer, true_crime, video_essay, custom
```

Profile's `style_directive` is injected into every agent via `intel/dna_loader.py:get_dna()`.

Key functions: `core/profile.py` → `get_profile()`, `get_style_directive()`, `get_mood_palette()`, `get_hook_registers()`, `reset_profile_cache()`

### Provider System

Swap any external service in `obsidian.yaml`:
```yaml
providers:
  llm:
    name: anthropic    # or openai, or custom.module.ClassName
  tts:
    name: elevenlabs
  images:
    name: fal
  footage:
    name: pexels
  upload:
    name: local
```

Key functions: `providers/registry.py` → `get_provider("llm")`, `list_providers()`, `clear_cache()`

Built-in providers: `anthropic`, `openai`, `elevenlabs`, `fal`, `pexels`, `local`

**Services:** Claude (Anthropic), ElevenLabs (TTS), fal.ai (images), Pexels (footage), Supabase (DB), YouTube API

## CI Pipeline (must pass before push)

```bash
ruff check --select E,F,W --ignore E501,E402 --exclude remotion .
cd remotion && npm run lint                    # eslint + tsc
python -m pytest tests/ -v --tb=short --cov=. --cov-report=term-missing --cov-fail-under=26
cd remotion && npm test                        # vitest
cd dashboard && npm test                       # vitest (local only)
```

Note: CI uses bare `python` (GitHub Actions), locally use `.venv/bin/python`. 1,428 tests, 57% coverage.

## Project Invariants (violating these = bugs)

1. **Anthropic SDK**: `output_config={"format":{"type":"json_schema","schema":...}}` — NOT `output_format`, NOT `response_format`
2. **Notifications**: All new notification code uses `server/notify.py` (`_tg()` + `_send()` dual-send). NEVER extend `server/notifier.py` (legacy, Discord-only).
3. **Dashboard types**: ALL type interfaces live in `dashboard/src/types.ts`. Never define types in component files or store.ts.
4. **Dashboard signals**: New signals must NOT be referenced in `systemState` computed (store.ts) unless they affect pipeline state.
5. **File I/O in server code**: Always `with open() as f:` context managers. Never bare `open()` with deque/readlines.
6. **Schema registry**: Agent 13 (Content Auditor) uses explicit per-call schemas, NOT the auto-lookup registry.
7. **Recovery calls**: `_call_raw()` args tuple must include ALL params that `_call_raw` accepts — silent schema loss otherwise.
8. **Thread safety**: `run_pipeline.py` image gen uses 3 ThreadPoolExecutor workers. Shared state must be read-only or locked.
9. **Import style**: One import per line for Python (ruff E401). Lazy imports in try/except for optional modules.
10. **Test coverage**: Minimum 26%. New signals/state must be covered in `resetAllSignals()` test.
11. **Config source of truth**: All tunable values come from `obsidian.yaml` via `core/config.py`. Never hardcode values that exist in config.
12. **Profile injection**: Style directives are injected via `intel/dna_loader.py:get_dna()`. Never modify agent files directly for style changes.
13. **Provider pattern**: New providers extend ABCs in `providers/base.py` and register in `providers/registry.py`. Never hardcode service calls.

## Patterns to Follow

- **Adding a notification**: Add to `server/notify.py`, call both `_tg()` and `_send()`, follow pattern of `notify_pipeline_complete()`
- **Adding a dashboard panel**: Type in `types.ts`, signal in `store.ts` (isolated), fetch in `api.ts`, component in view file
- **Adding an API endpoint**: In `webhook_server.py`, use `@require_key` decorator, return `jsonify()`
- **Adding structured output to an agent**: Add schema to `core/structured_schemas.py`, add to `SCHEMA_REGISTRY` (unless agent has multiple call patterns)
- **Adding a content profile**: Copy `profiles/_template.yaml`, fill all sections, set `profile:` in `obsidian.yaml`. Tests auto-validate.
- **Adding a provider**: Extend ABC from `providers/base.py`, register in `providers/registry.py` `_BUILTIN_PROVIDERS`, add tests in `tests/test_providers.py`
- **Changing config defaults**: Edit `obsidian.yaml`, constants in `core/pipeline_config.py` will pick it up automatically
