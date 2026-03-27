"""
Providers — swappable backends for external services.

Each provider type has an abstract base class and one or more implementations.
The active provider is selected in obsidian.yaml and loaded via get_provider().

Provider types:
  - llm: Text generation (Anthropic Claude, OpenAI, local)
  - tts: Text-to-speech (ElevenLabs, OpenAI TTS)
  - images: Image generation (fal.ai, Replicate)
  - footage: Stock footage (Pexels, Pixabay)
  - upload: Video upload (YouTube, local save)
"""

from providers.registry import clear_cache, get_provider, list_providers

__all__ = ["get_provider", "list_providers", "clear_cache"]
