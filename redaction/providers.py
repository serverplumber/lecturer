"""Provider adapters for the glossator — one structured call, any backend.

Each provider takes a system prompt and a request and returns a parsed
``WovenParagraph`` (or ``None`` when the model produced nothing usable),
accumulating token usage as it goes. Failures the pipeline cannot work
around — missing credentials, API errors — are raised as ``GlossError``.

Local models come through the OpenAI adapter for free: every common local
server (Ollama, llama.cpp, vLLM, LM Studio) speaks the OpenAI wire
protocol, so ``--provider openai --base-url http://localhost:11434/v1``
glosses with whatever the laptop is serving.
"""

import os
from typing import Literal, Protocol

import anthropic
import openai
from pydantic import BaseModel


class Piece(BaseModel):
    manner: Literal["body", "digression"]
    text: str


class WovenParagraph(BaseModel):
    pieces: list[Piece]


class GlossError(Exception):
    """Glossing cannot proceed: credentials, connectivity, or the API itself."""


class GlossProvider(Protocol):
    """Adapter interface — one implementation per API dialect."""

    label: str
    input_tokens: int
    output_tokens: int

    def gloss(self, system: str, request: str) -> WovenParagraph | None: ...


class AnthropicProvider:
    def __init__(self, model: str, base_url: str | None = None, effort: str | None = None) -> None:
        self.label = f"anthropic/{model}" + (f"+effort={effort}" if effort else "")
        self.input_tokens = 0
        self.output_tokens = 0
        self._model = model
        self._effort = effort
        self._client = anthropic.Anthropic(**({"base_url": base_url} if base_url else {}))

    def gloss(self, system: str, request: str) -> WovenParagraph | None:
        extra = {"output_config": {"effort": self._effort}} if self._effort else {}
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=8000,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": request}],
                output_format=WovenParagraph,
                **extra,
            )
        except (TypeError, anthropic.AuthenticationError) as error:
            # The SDK raises a bare TypeError when no credential source exists.
            if isinstance(error, TypeError) and "authentication" not in str(error):
                raise
            raise GlossError(
                "no Anthropic credentials: set ANTHROPIC_API_KEY or run `ant auth login`"
            ) from error
        except anthropic.APIError as error:
            raise GlossError(str(error)) from error
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        return response.parsed_output


class OpenAIProvider:
    """OpenAI proper, or any OpenAI-compatible server via ``base_url``.

    ``effort`` maps to ``reasoning_effort``. It matters enormously for local
    reasoning models: gpt-oss at default effort copies notes verbatim into
    digressions, at high effort it actually respeaks them.
    """

    def __init__(self, model: str, base_url: str | None = None, effort: str | None = None) -> None:
        self.label = (
            f"openai/{model}"
            + (f"@{base_url}" if base_url else "")
            + (f"+effort={effort}" if effort else "")
        )
        self.input_tokens = 0
        self.output_tokens = 0
        self._model = model
        self._effort = effort
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key is None and base_url is not None:
            api_key = "unused"  # local servers accept anything
        try:
            self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        except openai.OpenAIError as error:
            raise GlossError(
                "no OpenAI credentials: set OPENAI_API_KEY (or pass --base-url for a local server)"
            ) from error

    def gloss(self, system: str, request: str) -> WovenParagraph | None:
        extra = {"reasoning_effort": self._effort} if self._effort else {}
        try:
            completion = self._client.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": request},
                ],
                response_format=WovenParagraph,
                **extra,
            )
        except openai.AuthenticationError as error:
            raise GlossError("no OpenAI credentials: set OPENAI_API_KEY") from error
        except openai.LengthFinishReasonError:
            return None  # truncated mid-JSON — unusable, let the caller fall back
        except openai.APIError as error:
            raise GlossError(str(error)) from error
        if completion.usage is not None:
            self.input_tokens += completion.usage.prompt_tokens
            self.output_tokens += completion.usage.completion_tokens
        return completion.choices[0].message.parsed


PROVIDERS: dict[str, type[AnthropicProvider] | type[OpenAIProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}

DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-5.1",
}
