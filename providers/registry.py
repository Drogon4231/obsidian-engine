"""
Provider registry — instantiate the right provider based on obsidian.yaml config.

Usage:
    from providers.registry import get_provider
    llm = get_provider("llm")       # Returns configured LLMProvider
    tts = get_provider("tts")       # Returns configured TTSProvider
    img = get_provider("images")    # Returns configured ImageProvider
    ftg = get_provider("footage")   # Returns configured FootageProvider
    upl = get_provider("upload")    # Returns configured UploadProvider
"""

from __future__ import annotations

import importlib
from typing import Any

from providers.base import (
    FootageProvider,
    ImageProvider,
    LLMProvider,
    MusicProvider,
    SFXProvider,
    TTSProvider,
    UploadProvider,
)

# Maps provider type → (module_path, class_name) for built-in providers
_BUILTIN_PROVIDERS: dict[str, dict[str, tuple[str, str]]] = {
    "llm": {
        "anthropic": ("providers.llm.anthropic", "AnthropicProvider"),
        "openai": ("providers.llm.openai", "OpenAIProvider"),
    },
    "tts": {
        "elevenlabs": ("providers.tts.elevenlabs", "ElevenLabsProvider"),
        "epidemic_sound": ("providers.tts.epidemic", "EpidemicTTSProvider"),
        "openai": ("providers.tts.openai_tts", "OpenAIProvider"),
    },
    "images": {
        "fal": ("providers.images.fal", "FalProvider"),
    },
    "footage": {
        "pexels": ("providers.footage.pexels", "PexelsProvider"),
    },
    "upload": {
        "local": ("providers.upload.local", "LocalSaveProvider"),
    },
    "music": {
        "epidemic_sound": ("providers.music.epidemic", "EpidemicMusicProvider"),
        "local": ("providers.music.local", "LocalMusicProvider"),
    },
    "sfx": {
        "epidemic_sound": ("providers.sfx.epidemic", "EpidemicSFXProvider"),
        "local": ("providers.sfx.local", "LocalSFXProvider"),
    },
}

# Expected base class for each provider type
_BASE_CLASSES: dict[str, type] = {
    "llm": LLMProvider,
    "tts": TTSProvider,
    "images": ImageProvider,
    "footage": FootageProvider,
    "upload": UploadProvider,
    "music": MusicProvider,
    "sfx": SFXProvider,
}

# Default provider for each type (used when config doesn't specify)
_DEFAULTS: dict[str, str] = {
    "llm": "anthropic",
    "tts": "elevenlabs",
    "images": "fal",
    "footage": "pexels",
    "upload": "local",
    "music": "local",
    "sfx": "local",
}

# Singleton cache
_instances: dict[str, Any] = {}


def _load_class(module_path: str, class_name: str) -> type:
    """Import a class from a dotted module path."""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls


def _resolve_provider_config(provider_type: str) -> tuple[str, dict]:
    """Read obsidian.yaml to find which provider and options to use.

    Returns (provider_name, options_dict).
    """
    try:
        from core.config import cfg
        providers_section = cfg.get("providers")
        if providers_section:
            section = providers_section.get(provider_type)
            if section:
                name = section.get("name") or section.get("provider")
                options = section.get("options") or {}
                if isinstance(options, dict):
                    pass
                else:
                    try:
                        options = options.to_dict()
                    except AttributeError:
                        options = {}
                if name:
                    return str(name), options
    except Exception:
        pass

    return _DEFAULTS.get(provider_type, ""), {}


def get_provider(provider_type: str, *, fresh: bool = False) -> Any:
    """Get a configured provider instance.

    Args:
        provider_type: One of "llm", "tts", "images", "footage", "upload"
        fresh: If True, create a new instance instead of returning cached one

    Returns:
        An instance of the appropriate provider.

    Raises:
        ValueError: If provider_type is unknown
        RuntimeError: If the provider can't be loaded
    """
    if provider_type not in _BASE_CLASSES:
        raise ValueError(
            f"Unknown provider type '{provider_type}'. "
            f"Must be one of: {', '.join(_BASE_CLASSES)}"
        )

    if not fresh and provider_type in _instances:
        return _instances[provider_type]

    name, options = _resolve_provider_config(provider_type)

    # Resolve "auto" for music/sfx: try epidemic_sound if API key set, else local
    builtins = _BUILTIN_PROVIDERS.get(provider_type, {})
    if name == "auto" and provider_type in ("music", "sfx"):
        import os
        if os.getenv("EPIDEMIC_SOUND_API_KEY") and "epidemic_sound" in builtins:
            try:
                module_path, class_name = builtins["epidemic_sound"]
                cls = _load_class(module_path, class_name)
                name = "epidemic_sound"
            except Exception:
                name = "local"
        else:
            name = "local"

    # Check built-in providers first
    if name in builtins:
        module_path, class_name = builtins[name]
        cls = _load_class(module_path, class_name)
    elif "." in name:
        # Custom provider: "my_package.my_module.MyProvider"
        parts = name.rsplit(".", 1)
        if len(parts) != 2:
            raise RuntimeError(
                f"Custom provider '{name}' must be 'module.path.ClassName'"
            )
        cls = _load_class(parts[0], parts[1])
    else:
        raise RuntimeError(
            f"Unknown {provider_type} provider '{name}'. "
            f"Built-in options: {', '.join(builtins)}"
        )

    # Validate it's the right type
    base = _BASE_CLASSES[provider_type]
    if not issubclass(cls, base):
        raise RuntimeError(
            f"Provider {cls.__name__} does not extend {base.__name__}"
        )

    # Instantiate with options
    if options:
        instance = cls(**options)
    else:
        instance = cls()

    _instances[provider_type] = instance
    return instance


def list_providers(provider_type: str | None = None) -> dict[str, list[str]]:
    """List available built-in providers.

    Args:
        provider_type: If given, list only providers for that type.

    Returns:
        Dict of {provider_type: [provider_names]}
    """
    if provider_type:
        return {provider_type: list(_BUILTIN_PROVIDERS.get(provider_type, {}))}
    return {k: list(v) for k, v in _BUILTIN_PROVIDERS.items()}


def clear_cache() -> None:
    """Clear the provider singleton cache. Useful for testing."""
    _instances.clear()
