"""Pre-flight cost estimate for `redact --llm` — see docs/planned/cost-estimate.md.

Computes what the remaining glossing work would cost without spending
anything: input tokens come from ``count_tokens`` (a free endpoint), output
tokens are extrapolated from this book's own persisted call history
(``gloss_usage.jsonl``, written by ``lecturer.py`` after a real run). Scoped
to the Anthropic provider for v1 — OpenAI has different pricing and no
identically-named free token-counting endpoint (non-goal, tracked as future
work in the spec).
"""

from dataclasses import dataclass, field
from pathlib import Path

from extraction import Extraction
from redaction.base import Script
from redaction.gloss import _SYNOPSIS_SYSTEM, _SYSTEM, Glossator, Synopsis
from redaction.mend import SeamMender
from redaction.providers import AnthropicProvider, WovenParagraph
from redaction.usage import load_usage

# $/MTok (input, output) — Anthropic first-party pricing for models this
# project actually defaults to or is likely to be pointed at (redaction/
# providers.py's DEFAULT_MODELS/TAGGING_MODELS). A model not listed here
# means abstaining from a dollar figure, the same posture bibliography.py's
# sniff_style takes on an unconfirmed house style — reporting token counts
# with no price rather than guessing.
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Anthropic's ephemeral prompt cache (5-minute TTL, the only TTL this
# codebase ever requests): a write costs 1.25x the base input price, a read
# costs ~0.1x.
_CACHE_WRITE_MULTIPLIER = 1.25
_CACHE_READ_MULTIPLIER = 0.1

# Below this many prefix tokens, a model silently doesn't cache at all (no
# error, just cache_creation_input_tokens: 0) — and the floor isn't monotonic
# across generations: Claude Opus 5 halves Opus 4.8's own 1024-token floor.
# Looked up per model rather than a single constant for that reason; an
# unlisted model falls back to the middle value in Anthropic's own published
# range rather than guessing high or low.
_CACHE_MINIMUMS: dict[str, int] = {
    "claude-opus-5": 512,
    "claude-opus-4-8": 1024,
    "claude-sonnet-5": 1024,
    "claude-sonnet-4-6": 1024,
    "claude-haiku-4-5": 4096,
}
_DEFAULT_CACHE_MINIMUM = 1024

# ensure_synopsis truncates the whole book to this many characters before
# sending it — mirrored here so the free count matches the real call exactly.
_SYNOPSIS_CHARS = 600_000


def price_tokens(
    model: str,
    *,
    input_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    output_tokens: int = 0,
) -> float | None:
    """Real dollar cost for a set of token counts under ``model``.

    ``None`` when ``model`` isn't in ``_PRICING`` — the same abstain-over-
    guess posture the rest of this module takes, rather than a wrong number.
    One formula, used both by this module's own forward-looking estimate and
    by ``lecturer.py``'s post-run real-cost report (built from
    ``AnthropicProvider``'s real usage counters, cache tokens included) —
    keeping the two from drifting apart the way the estimate's own input
    figure and a run's real reported cost once did (see CLAUDE.md).
    """
    price_in, price_out = _PRICING.get(model, (None, None))
    if price_in is None:
        return None
    return (
        input_tokens * price_in
        + cache_creation_tokens * price_in * _CACHE_WRITE_MULTIPLIER
        + cache_read_tokens * price_in * _CACHE_READ_MULTIPLIER
        + output_tokens * price_out
    ) / 1_000_000


@dataclass
class ChapterEstimate:
    title: str
    paragraphs: int = 0
    cached_prefix_tokens: int = 0  # system + chapter context, cached together
    base_tokens: int = 0  # sum of every paragraph's own request tokens (uncached)


@dataclass
class Estimate:
    provider_label: str
    model: str
    remaining_paragraphs: int
    total_input_tokens: int = 0  # priced or not — always known from count_tokens
    chapters: list[ChapterEstimate] = field(default_factory=list)
    input_dollars: float | None = None
    output_dollars: float | None = None
    output_basis: str | None = None
    caveats: list[str] = field(default_factory=list)

    @property
    def total_dollars(self) -> float | None:
        if self.input_dollars is None or self.output_dollars is None:
            return None
        return self.input_dollars + self.output_dollars


def estimate_gloss_cost(
    extraction: Extraction,
    provider: AnthropicProvider,
    directory: Path,
    synopsis: str | None,
) -> Estimate:
    """What the remaining ``redact --llm`` work would cost, spending nothing.

    Loads the pipeline through the same layers ``redact --llm`` would before
    the glossator itself runs (``SeamMender``, then the glossator's own
    cache lookup), so the paragraph list matches exactly what a real run
    would still bill for. Groups paragraphs by chapter (the glossator's own
    cache-stable context boundary — by section *position*, since two
    sections sharing a title, real in this corpus's PDF outlines, must not
    collapse into one chapter and lose one context's tokens) to model
    prompt-cache economics: the first uncached paragraph in a chapter is a
    cache write, the rest are cache reads — **provided** those calls land
    inside the cache's 5-minute TTL; a stalled or slow run re-writes the
    prefix instead, which is why that assumption is surfaced as a caveat
    rather than baked in silently. ``synopsis`` is this book's already-drafted
    synopsis.txt if it has one; when it doesn't, drafting it is itself a real,
    billed first call — priced separately below, not folded into the
    per-paragraph total, since it happens once regardless of paragraph count.
    """
    glossator = Glossator(
        provider=provider, cache_path=directory / "gloss_cache.json", synopsis=synopsis
    )
    script = SeamMender().redact(Script.from_extraction(extraction))
    pending = glossator.pending_paragraphs(script)

    chapters: list[ChapterEstimate] = []
    by_index: dict[int, ChapterEstimate] = {}
    for paragraph in pending:
        # No system, no context: isolates this one request's own token cost
        # from the cached system+context prefix (cache_control on the context
        # block caches everything up to and including it, system included).
        request_tokens = provider.count_input_tokens(None, paragraph.request, WovenParagraph)
        chapter = by_index.get(paragraph.section_index)
        if chapter is None:
            cached_prefix = 0
            if paragraph.context is not None:
                full_tokens = provider.count_input_tokens(
                    _SYSTEM, paragraph.request, WovenParagraph, context=paragraph.context
                )
                cached_prefix = max(full_tokens - request_tokens, 0)
            chapter = ChapterEstimate(
                title=paragraph.section_title, cached_prefix_tokens=cached_prefix
            )
            by_index[paragraph.section_index] = chapter
            chapters.append(chapter)
        chapter.paragraphs += 1
        chapter.base_tokens += request_tokens

    caveats: list[str] = []

    if synopsis is None:
        synopsis_text = "\n\n".join(section.text for section in extraction.sections)
        synopsis_tokens = provider.count_input_tokens(
            _SYNOPSIS_SYSTEM, synopsis_text[:_SYNOPSIS_CHARS], Synopsis
        )
    else:
        synopsis_tokens = 0

    if chapters:
        caveats.append(
            "cache pricing below assumes every paragraph in a chapter is glossed within "
            "the cache's 5-minute TTL of the one before it — a stalled or slow run "
            "re-writes the prefix instead, at the higher write price rather than the read price."
        )

    priced = provider.model in _PRICING
    if not priced:
        caveats.append(
            f"no pricing on file for model {provider.model!r} — reporting token counts only."
        )

    min_cacheable = _CACHE_MINIMUMS.get(provider.model, _DEFAULT_CACHE_MINIMUM)
    base_tokens = 0
    write_tokens = 0
    read_tokens = 0
    for chapter in chapters:
        if chapter.cached_prefix_tokens >= min_cacheable:
            write_tokens += chapter.cached_prefix_tokens
            read_tokens += chapter.cached_prefix_tokens * (chapter.paragraphs - 1)
        elif chapter.cached_prefix_tokens > 0:
            # Too short to cache at all (Anthropic's own floor) — every
            # paragraph in the chapter re-sends the context at base price.
            base_tokens += chapter.cached_prefix_tokens * chapter.paragraphs
            caveats.append(
                f"'{chapter.title}': its context is only {chapter.cached_prefix_tokens} tokens, "
                f"below the {min_cacheable}-token cacheable minimum for {provider.model}, so "
                "every paragraph in it is priced at the full base rate rather than cached."
            )
        base_tokens += chapter.base_tokens

    total_input_tokens = base_tokens + write_tokens + read_tokens + synopsis_tokens

    input_dollars = price_tokens(
        provider.model,
        input_tokens=base_tokens,
        cache_creation_tokens=write_tokens,
        cache_read_tokens=read_tokens,
    )
    synopsis_dollars = (
        price_tokens(provider.model, input_tokens=synopsis_tokens) if synopsis_tokens else None
    )

    if synopsis_tokens:
        if synopsis_dollars is not None:
            caveats.append(
                f"this book has no synopsis.txt yet, so redact --llm will draft one first — "
                f"a one-off call of its own, around ${synopsis_dollars:.2f} "
                f"({synopsis_tokens} input tokens), not counted in the per-paragraph total above."
            )
        else:
            caveats.append(
                f"this book has no synopsis.txt yet, so redact --llm will draft one first — "
                f"a one-off call of its own ({synopsis_tokens} input tokens), not counted in "
                "the per-paragraph total above."
            )
        caveats.append(
            "chapter contexts above also lack the synopsis a real run would prepend to "
            "each one once drafted, so the per-paragraph cache figures are a slight "
            "underestimate on top of that."
        )

    remaining = len(pending)
    matching = [
        record
        for record in load_usage(directory / "gloss_usage.jsonl")
        if record.provider_label == provider.label
    ]
    output_dollars = None
    output_basis = None
    if matching:
        total_calls = sum(record.calls for record in matching)
        total_truncated = sum(record.truncated for record in matching)
        total_output = sum(record.output_tokens for record in matching)
        billed_calls = total_calls - total_truncated
        if billed_calls > 0:
            average_output = total_output / billed_calls
            output_basis = (
                f"{billed_calls} real call{'s' if billed_calls != 1 else ''} "
                f"on {provider.label}, from this book's own history"
            )
            output_dollars = price_tokens(provider.model, output_tokens=average_output * remaining)
            if total_truncated:
                caveats.append(
                    f"{total_truncated} of {total_calls} historical call(s) on {provider.label} "
                    "were truncated and their real output tokens are missing from this average "
                    "— the output estimate is a lower bound."
                )
        elif total_truncated:
            caveats.append(
                f"every historical call on {provider.label} for this book was truncated "
                "(no usable output-token sample) — output cost cannot be estimated."
            )
    if output_basis is None:
        caveats.append(
            f"output cost cannot be estimated yet — no prior successful {provider.label} "
            "samples for this book."
        )

    return Estimate(
        provider_label=provider.label,
        model=provider.model,
        remaining_paragraphs=remaining,
        total_input_tokens=total_input_tokens,
        chapters=chapters,
        input_dollars=input_dollars,
        output_dollars=output_dollars,
        output_basis=output_basis,
        caveats=caveats,
    )


def render_estimate(estimate: Estimate) -> str:
    """Plain prose, not a table — read aloud correctly by a screen reader."""
    if not estimate.remaining_paragraphs:
        return (
            "Nothing left to gloss — every annotated paragraph in this book is already "
            "cached, so redact --llm would spend nothing on a run right now."
        )
    chapters = len(estimate.chapters)
    paragraph_word = "paragraph" if estimate.remaining_paragraphs == 1 else "paragraphs"
    sentences = [
        f"Estimated cost to gloss the remaining {chapters} "
        f"chapter{'s' if chapters != 1 else ''} "
        f"(about {estimate.remaining_paragraphs} {paragraph_word}) on {estimate.model}:"
    ]
    if estimate.total_dollars is not None:
        sentences.append(
            f"around ${estimate.total_dollars:.2f}, based on real per-paragraph output "
            f"sizes measured from {estimate.output_basis}."
        )
    elif estimate.input_dollars is not None:
        sentences.append(
            f"input alone comes to around ${estimate.input_dollars:.2f}; the output half "
            "cannot be priced yet, so this is not the full number."
        )
    else:
        sentences.append(f"no dollar figure — {estimate.total_input_tokens} input tokens total.")
    return " ".join(sentences) + ("\n\n" + "\n".join(estimate.caveats) if estimate.caveats else "")
