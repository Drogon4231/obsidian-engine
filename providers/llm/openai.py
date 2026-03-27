"""
OpenAI GPT LLM provider — alternative implementation.

Requires: pip install openai
Set OPENAI_API_KEY in .env

This is a reference implementation showing how to add a new LLM provider.
"""

from __future__ import annotations

from typing import Any

from providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    def __init__(self, default_model: str = "gpt-4o"):
        self._default_model = default_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            import os
            try:
                import openai
            except ImportError:
                raise ImportError(
                    "OpenAI provider requires the openai package. "
                    "Install with: pip install openai"
                )
            self._client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 4000,
        expect_json: bool = True,
        output_schema: dict | None = None,
    ) -> Any:
        import json
        client = self._get_client()
        model = model or self._default_model

        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        if expect_json or output_schema:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        raw = response.choices[0].message.content.strip()

        if not expect_json:
            return raw

        return json.loads(raw)

    def generate_with_search(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 4000,
        output_schema: dict | None = None,
    ) -> str:
        # OpenAI doesn't have native web search — fall back to regular generation
        # with a note in the system prompt
        enhanced_system = system_prompt + (
            "\n\nNote: Web search is not available with this provider. "
            "Use your training knowledge to provide the best response."
        )
        return self.generate(
            system_prompt=enhanced_system,
            user_prompt=user_prompt,
            model=model,
            max_tokens=max_tokens,
            expect_json=False,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str | None = None) -> float:
        model = model or self._default_model
        # GPT-4o pricing (as of 2025)
        prices = {
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        }
        p = prices.get(model, {"input": 2.50, "output": 10.00})
        return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000

    @property
    def name(self) -> str:
        return "OpenAI GPT"
