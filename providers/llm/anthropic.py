"""
Anthropic Claude LLM provider — default implementation.

Wraps the existing clients/claude_client.py for provider interface compatibility.
"""

from __future__ import annotations

from typing import Any

from providers.base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Claude LLM provider using the Anthropic API."""

    def __init__(self):
        from clients.claude_client import SONNET
        self._default_model = SONNET

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 4000,
        expect_json: bool = True,
        output_schema: dict | None = None,
    ) -> Any:
        from clients.claude_client import call_claude
        return call_claude(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model or self._default_model,
            max_tokens=max_tokens,
            expect_json=expect_json,
            output_schema=output_schema,
        )

    def generate_with_search(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 4000,
        output_schema: dict | None = None,
    ) -> str:
        from clients.claude_client import call_claude_with_search
        return call_claude_with_search(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model or self._default_model,
            max_tokens=max_tokens,
            output_schema=output_schema,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str | None = None) -> float:
        from clients.claude_client import _PRICES
        model = model or self._default_model
        prices = _PRICES.get(model, {"input": 3.00, "output": 15.00})
        return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000

    @property
    def name(self) -> str:
        return "Anthropic Claude"
