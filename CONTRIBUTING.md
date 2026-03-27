# Contributing to Obsidian Engine

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# Fork and clone the repo
git clone https://github.com/YOUR_USERNAME/obsidian-engine.git
cd obsidian-engine

# Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Remotion
cd remotion && npm install && cd ..

# Dashboard
cd dashboard && npm install && cd ..

# Copy env template
cp .env.example .env
# Fill in at least ANTHROPIC_API_KEY for tests that hit the API
```

## Running Tests

All tests must pass before submitting a PR:

```bash
# Python lint
ruff check --select E,F,W --ignore E501,E402 --exclude remotion .

# Python tests (26% minimum coverage)
python -m pytest tests/ -v --tb=short --cov=. --cov-fail-under=26

# TypeScript lint
cd remotion && npm run lint

# TypeScript tests
cd remotion && npm test
```

## Project Invariants

These are non-negotiable rules. Violating them will cause bugs:

1. **Anthropic SDK**: Use `output_config={"format":{"type":"json_schema","schema":...}}` — NOT `output_format`
2. **Notifications**: All new notification code goes in `server/notify.py` (dual Telegram + Discord). Never extend `server/notifier.py` (legacy).
3. **Dashboard types**: ALL type interfaces live in `dashboard/src/types.ts`. Never define types in component files.
4. **Thread safety**: Shared state in parallel phases must use `runner.mark_metadata()` (acquires lock).
5. **Import style**: One import per line (ruff E401). Lazy imports in try/except for optional modules.

## What to Contribute

Good first issues:
- Add a new content profile (e.g., `profiles/tutorial.yaml`)
- Add a new provider (e.g., OpenAI TTS, local Ollama)
- Improve documentation
- Add test coverage

Bigger contributions:
- New pipeline stages
- Alternative video renderers
- UI improvements to the dashboard

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Ensure all tests pass
4. Submit a PR with a clear description of what and why

## Code Style

- Python: Follow existing patterns, use `ruff` for linting
- TypeScript: Follow existing patterns, use `eslint` for linting
- Prefer simple, readable code over clever abstractions
- Add tests for new functionality
