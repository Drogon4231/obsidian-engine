# The Obsidian Archive — Project Intelligence

## Architecture

15-stage automated documentary pipeline → YouTube upload.

```
Topic → Research(1) → Originality(2) → Narrative(3) → Script(4) → ScriptDoctor(4b)
     → Compliance(5) → SEO(6) → Scenes(7) → VisualContinuity(7b) → TTS(8)
     → Footage(9) → Images(10) → Video(11) → QA(12) → Upload(13)
```

**Core call chain:** `agents/*.py` → `core/agent_wrapper.py:call_agent()` → `clients/claude_client.py:call_claude()` → Anthropic API

**Key files by area:**
- Pipeline orchestrator: `run_pipeline.py` (3700+ lines)
- Agent wrapper with SLA/recovery/diagnostics: `core/agent_wrapper.py`
- Claude API client: `clients/claude_client.py`
- Structured output schemas: `core/structured_schemas.py`
- Observability (errors + traces): `core/observability.py`
- Dashboard: `dashboard/src/` (Preact + Signals + Tailwind)
- Webhook server: `server/webhook_server.py` (Flask + SSE)
- Notifications: `server/notify.py` (Telegram `_tg()` + Discord `_send()`)
- Video renderer: `remotion/src/`
- Scheduler: `scheduler.py`

**Services:** Claude (Anthropic), ElevenLabs (TTS), fal.ai (images), Supabase (DB), YouTube API

## CI Pipeline (must pass before push)

```bash
ruff check --select E,F,W --ignore E501,E402 --exclude remotion .
cd remotion && npm run lint                    # eslint + tsc
python -m pytest tests/ -v --tb=short --cov=. --cov-report=term-missing --cov-fail-under=26
cd remotion && npm test                        # vitest
```

Note: CI uses bare `python` (GitHub Actions), locally use `.venv/bin/python`. Dashboard tests are local-only (not in CI).

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

## Patterns to Follow

- **Adding a notification**: Add to `server/notify.py`, call both `_tg()` and `_send()`, follow pattern of `notify_pipeline_complete()`
- **Adding a dashboard panel**: Type in `types.ts`, signal in `store.ts` (isolated), fetch in `api.ts`, component in view file
- **Adding an API endpoint**: In `webhook_server.py`, use `@require_key` decorator, return `jsonify()`
- **Adding structured output to an agent**: Add schema to `core/structured_schemas.py`, add to `SCHEMA_REGISTRY` (unless agent has multiple call patterns)
