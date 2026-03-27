"""
Abstract base classes for all provider types.

To create a custom provider:
1. Subclass the relevant base class
2. Implement all abstract methods
3. Register it in obsidian.yaml under providers.*
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class LLMProvider(ABC):
    """Abstract base for text generation providers (Claude, GPT, local models)."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 4000,
        expect_json: bool = True,
        output_schema: dict | None = None,
    ) -> Any:
        """Generate text or structured output.

        Args:
            system_prompt: System/instruction prompt
            user_prompt: User message
            model: Model identifier (provider-specific). None = use default.
            max_tokens: Maximum output tokens
            expect_json: If True, parse response as JSON
            output_schema: JSON schema for structured output (provider enforces if supported)

        Returns:
            Parsed JSON (dict/list) if expect_json=True, else raw string.
        """

    @abstractmethod
    def generate_with_search(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 4000,
        output_schema: dict | None = None,
    ) -> str:
        """Generate text with web search capability.

        Returns raw text with search results embedded.
        """

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str | None = None) -> float:
        """Estimate cost in USD for a given token count."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""


class TTSProvider(ABC):
    """Abstract base for text-to-speech providers (ElevenLabs, OpenAI TTS)."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        voice_settings: dict | None = None,
        speed: float = 1.0,
    ) -> tuple[Path, list[dict]]:
        """Generate speech audio from text.

        Args:
            text: Text to speak
            voice_id: Voice identifier (provider-specific). None = use default.
            voice_settings: Voice parameters (stability, style, etc.)
            speed: Playback speed multiplier

        Returns:
            Tuple of (audio_file_path, word_timestamps).
            word_timestamps: list of {"word": str, "start": float, "end": float}
        """

    @abstractmethod
    def list_voices(self) -> list[dict]:
        """List available voices.

        Returns list of {"id": str, "name": str, "description": str}
        """

    @abstractmethod
    def check_credits(self) -> dict:
        """Check remaining credits/quota.

        Returns {"remaining": int, "limit": int, "unit": str}
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""


class ImageProvider(ABC):
    """Abstract base for image generation providers (fal.ai, Replicate, ComfyUI)."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        style: str | None = None,
        width: int = 1920,
        height: int = 1080,
        seed: int | None = None,
    ) -> Path:
        """Generate an image from a text prompt.

        Args:
            prompt: Image description
            style: Style modifier (provider-specific)
            width: Image width in pixels
            height: Image height in pixels
            seed: Random seed for reproducibility

        Returns:
            Path to the generated image file.
        """

    @abstractmethod
    def estimate_cost(self) -> float:
        """Estimate cost in USD per image generation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""


class FootageProvider(ABC):
    """Abstract base for stock footage providers (Pexels, Pixabay)."""

    @abstractmethod
    def search(
        self,
        query: str,
        orientation: str = "landscape",
        min_duration: int = 5,
        max_results: int = 5,
    ) -> list[dict]:
        """Search for stock footage.

        Args:
            query: Search terms
            orientation: "landscape" or "portrait"
            min_duration: Minimum clip duration in seconds
            max_results: Maximum results to return

        Returns:
            List of {"url": str, "duration": int, "width": int, "height": int, "preview_url": str}
        """

    @abstractmethod
    def download(self, url: str, output_path: Path) -> Path:
        """Download a footage file.

        Returns path to the downloaded file.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""


class UploadProvider(ABC):
    """Abstract base for video upload providers (YouTube, local save)."""

    @abstractmethod
    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_path: Path | None = None,
    ) -> dict:
        """Upload a video.

        Args:
            video_path: Path to the rendered video
            title: Video title
            description: Video description
            tags: List of tags
            thumbnail_path: Optional custom thumbnail

        Returns:
            {"video_id": str, "url": str, "status": str}
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""
