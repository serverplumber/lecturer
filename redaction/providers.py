"""Provider adapters for the LLM layers — one structured call, any backend.

Each provider takes a system prompt, a request, and a pydantic schema, and
returns the parsed answer (or ``None`` when the model produced nothing
usable), accumulating token usage as it goes. Failures the pipeline cannot
work around — missing credentials, API errors — are raised as
``ProviderError``.

Local models come through the OpenAI adapter for free: every common local
server (Ollama, llama.cpp, vLLM, LM Studio) speaks the OpenAI wire
protocol, so ``--provider openai --base-url http://localhost:11434/v1``
glosses with whatever the laptop is serving.
"""

import os
from typing import Literal, Protocol, TypeVar

import anthropic
import openai
from pydantic import BaseModel, ValidationError


class Piece(BaseModel):
    manner: Literal["body", "digression"]
    text: str


class WovenParagraph(BaseModel):
    pieces: list[Piece]


class ProviderError(Exception):
    """The provider cannot proceed: credentials, connectivity, or the API itself."""


Schema = TypeVar("Schema", bound=BaseModel)


class Provider(Protocol):
    """Adapter interface — one implementation per API dialect.

    ``ask`` makes one structured call: system prompt, request, and the
    pydantic schema the answer must parse into (``None`` when the model
    produced nothing usable). Any redactional layer can bring its own
    schema — the glossator asks for woven paragraphs, the interpreter of
    tongues for language switches. ``context`` is a byte-stable prefix
    (synopsis + chapter) placed under a cache breakpoint: sequential calls
    sharing it pay ~0.1x for the cached span on Anthropic, and prefix
    reuse comes free on OpenAI and local servers.
    """

    label: str
    input_tokens: int
    output_tokens: int

    def ask(
        self, system: str, request: str, schema: type[Schema], context: str | None = None
    ) -> Schema | None: ...


class AnthropicProvider:
    def __init__(self, model: str, base_url: str | None = None, effort: str | None = None) -> None:
        self.label = f"anthropic/{model}" + (f"+effort={effort}" if effort else "")
        self.model = model
        self.input_tokens = 0
        self.output_tokens = 0
        # A call whose response truncates mid-JSON (see the ValidationError
        # catch in ask()) is still billed by Anthropic in full, but its usage
        # never reaches input_tokens/output_tokens above — there is nothing
        # to add, since the SDK's own Message parsing happens inside the
        # closure that raises. Counted here instead so a persisted usage
        # record (redaction/usage.py) can disclose the gap rather than
        # silently under-reporting real spend.
        self.truncated = 0
        self._model = model
        self._effort = effort
        # The SDK's own default (2) retries 429/5xx with backoff but wasn't
        # enough to ride out a real run of transient 500s this session — a
        # long book means dozens of sequential calls, so raising it here
        # costs nothing on the common case and saves a manual re-run on a bad
        # patch of Anthropic's infra.
        self._client = anthropic.Anthropic(
            max_retries=6, **({"base_url": base_url} if base_url else {})
        )
        # Optimistic until proven otherwise: adaptive thinking isn't available
        # on every model (Haiku 4.5 rejects it outright with a 400), and which
        # models support it isn't something to hardcode a list for — it's
        # cheaper and more robust to just find out from the API once per
        # instance and stop asking, than to guess from a model name.
        self._thinking = True

    def ask(
        self, system: str, request: str, schema: type[Schema], context: str | None = None
    ) -> Schema | None:
        extra = {"output_config": {"effort": self._effort}} if self._effort else {}
        if context is None:
            prompt = system
        else:
            prompt = [
                {"type": "text", "text": system},
                {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
            ]
        if self._thinking:
            extra["thinking"] = {"type": "adaptive"}
        try:
            # Streamed, not .parse(): the SDK refuses a non-streaming call
            # outright once max_tokens crosses ~21333 (its own heuristic —
            # 3600s * max_tokens / 128000 > the 600s non-streaming default —
            # unconditional, not based on how long the call actually takes),
            # and 24000 crosses that. Found for real: raising max_tokens from
            # 8000 (see the ValidationError catch below for why) worked in
            # every test that only counted tokens, then crashed outright on
            # the first genuine long-context glossing call this session.
            with self._client.messages.stream(
                model=self._model,
                max_tokens=24000,
                system=prompt,
                messages=[{"role": "user", "content": request}],
                output_format=schema,
                **extra,
            ) as stream:
                response = stream.get_final_message()
        except (TypeError, anthropic.AuthenticationError) as error:
            # The SDK raises a bare TypeError when no credential source exists.
            if isinstance(error, TypeError) and "authentication" not in str(error):
                raise
            raise ProviderError(
                "no Anthropic credentials: set ANTHROPIC_API_KEY or run `ant auth login`"
            ) from error
        except anthropic.BadRequestError as error:
            if self._thinking and "adaptive thinking is not supported" in str(error):
                self._thinking = False
                return self.ask(system, request, schema, context)
            raise ProviderError(str(error)) from error
        except anthropic.APIError as error:
            raise ProviderError(str(error)) from error
        except ValidationError:
            # Truncated mid-JSON (max_tokens hit) — unusable, let the caller fall
            # back. response is a local to the SDK's own post-parser closure and
            # never reaches here, so there is no response.usage to add — counted
            # separately (see self.truncated) rather than silently dropped.
            self.truncated += 1
            return None
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        return response.parsed_output

    def count_input_tokens(
        self, system: str | None, request: str, schema: type[Schema], context: str | None = None
    ) -> int:
        """Real input-token count for a call shaped like ``ask`` would send it.

        ``count_tokens`` is a free endpoint — used by ``redaction/estimate.py``
        to build a cost estimate without spending anything. Mirrors ``ask``'s
        own request construction (system/context/effort/thinking, including
        its adaptive-thinking fallback) so the count matches what a real call
        would actually be billed for. ``system=None`` omits the system prompt
        entirely (context must then be ``None`` too) — the estimator's way of
        isolating a bare request's own token cost from the cached system+context
        prefix, since Anthropic's ``cache_control`` on the context block caches
        everything before and including it, system prompt included.
        """
        extra = {"output_config": {"effort": self._effort}} if self._effort else {}
        prompt: str | list[dict] | None
        if system is None:
            prompt = None
        elif context is None:
            prompt = system
        else:
            prompt = [
                {"type": "text", "text": system},
                {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
            ]
        if self._thinking:
            extra["thinking"] = {"type": "adaptive"}
        kwargs = {
            "model": self._model,
            "messages": [{"role": "user", "content": request}],
            "output_format": schema,
            **extra,
        }
        if prompt is not None:
            kwargs["system"] = prompt
        try:
            result = self._client.messages.count_tokens(**kwargs)
        except anthropic.BadRequestError as error:
            if self._thinking and "adaptive thinking is not supported" in str(error):
                self._thinking = False
                return self.count_input_tokens(system, request, schema, context)
            raise ProviderError(str(error)) from error
        except anthropic.APIError as error:
            raise ProviderError(str(error)) from error
        return result.input_tokens


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
        # A local server grinding through a reasoning model can legitimately
        # take far longer per paragraph than the SDK's 10-minute default.
        timeout = 3600.0 if base_url is not None else openai.NOT_GIVEN
        try:
            self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        except openai.OpenAIError as error:
            raise ProviderError(
                "no OpenAI credentials: set OPENAI_API_KEY (or pass --base-url for a local server)"
            ) from error

    def ask(
        self, system: str, request: str, schema: type[Schema], context: str | None = None
    ) -> Schema | None:
        extra = {"reasoning_effort": self._effort} if self._effort else {}
        prompt = system if context is None else f"{system}\n\n{context}"
        try:
            completion = self._client.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": request},
                ],
                response_format=schema,
                **extra,
            )
        except openai.AuthenticationError as error:
            raise ProviderError("no OpenAI credentials: set OPENAI_API_KEY") from error
        except openai.LengthFinishReasonError:
            return None  # truncated mid-JSON — unusable, let the caller fall back
        except openai.APIError as error:
            raise ProviderError(str(error)) from error
        if completion.usage is not None:
            self.input_tokens += completion.usage.prompt_tokens
            self.output_tokens += completion.usage.completion_tokens
        return completion.choices[0].message.parsed


PROVIDERS: dict[str, type[AnthropicProvider] | type[OpenAIProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "openai": "gpt-5.1",
}

# Language tagging is classification, not composition — code is cheap,
# tokens aren't, so the interpreter defaults to the cheap tier.
TAGGING_MODELS = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-5-mini",
}
