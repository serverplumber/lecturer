# Spec: pre-flight cost estimate for `redact --llm`

Status: implemented (`estimate-gloss` verb, `redaction/estimate.py` +
`redaction/usage.py`) — see CLAUDE.md's Commands section for the full writeup,
including how it was verified against real corpora. Left in place (not deleted) since
`docs/planned/budget-confirmation.md` depends on it and links here. Written for
handoff to a fresh session — self-contained, no need to re-read the conversation
that produced it.

## Purpose

Before `redact --llm` makes any billed call, compute and print a real, defensible estimate
of what the remaining run will cost, so the user knows the number before spending anything.

## Why this is buildable (and where it's genuinely hard)

- `Glossator` (`redaction/gloss.py`) makes one sequential Anthropic call per annotated
  paragraph. Default model is `claude-opus-4-8` (`redaction/providers.py:181`) — $5.00 /
  MTok input, $25.00 / MTok output — with adaptive thinking on by default.
- `client.messages.count_tokens` is a free endpoint (no billing) and gives an exact input
  token count for a given system+context+request shape. It only covers the *input* half.
- **Output cost (including thinking) cannot be predicted per-call ahead of time.** There is
  no API for this. The only way to estimate it is from real historical samples.
- `gloss_cache.json` stores each call's returned `pieces` (the visible woven text) but
  **not** thinking tokens — Anthropic bills thinking as output tokens, so reconstructing an
  output estimate purely from cached piece text will systematically *undercount*.
- `AnthropicProvider`/`OpenAIProvider` (`redaction/providers.py`) already accumulate real
  `input_tokens`/`output_tokens` per run (`.input_tokens`, `.output_tokens` — output
  includes thinking). `lecturer.py:780-783` logs this at the end of a run:
  ```
  f"{name} used {provider.input_tokens} input + {provider.output_tokens} output tokens on {provider.label}"
  ```
  but only as a printed log line — **nothing persists it today.** This is the actual gap to
  close: without a durable record of real per-run usage, there is no ground-truth
  output/paragraph figure to extrapolate from, on this book or any other.
- **The counters themselves undercount, and this must be fixed before they're trusted as
  ground truth.** `AnthropicProvider.ask`'s `ValidationError` catch (`redaction/
  providers.py:112-113`, added this session for the truncation crash) does `return None`
  *before* `self.input_tokens += response.usage.input_tokens` runs. A truncated Opus call
  is still billed by Anthropic in full — thinking tokens included — but never reaches
  `provider.input_tokens`/`output_tokens`. Persisting these counters as-is (see groundwork
  below) would bake in a silent, one-directional undercount: more truncation this run means
  a lower — and wrong — estimate for the next one. Fix the counting (increment from
  `response.usage` before the `_faithful`/parse check, not after) as part of this spec's
  groundwork, not as an afterthought.

## Required groundwork (do this first, it's small)

Persist real usage after a `redact --llm` run — e.g. a `gloss_usage.json` (or similar)
alongside `gloss_cache.json` in the work dir, recording at minimum: total input tokens,
total output tokens, number of paragraphs glossed this run, provider label, timestamp.
Append across runs rather than overwrite, so the estimate can build a per-paragraph average
from real history rather than one run's noise. This is what makes the estimate honest —
without it, Spec 1 can only ever estimate the cheap half (input).

**Cold-start case:** a book's first-ever `--llm` run has no historical output data at all —
say so plainly in the estimate ("output cost cannot be estimated yet — no prior samples for
this book") rather than guessing from unrelated books. A global average across every book's
usage file is a reasonable fallback if the user wants one, but treat it as clearly labeled
as cross-book, not book-specific.

## Functional requirements

1. A new step — verb or flag, open question, see below — that, without spending anything:
   - Loads the extraction/redaction pipeline the same way `redact --llm` would, and finds
     every paragraph not already satisfied by `gloss_cache.json` (already-cached paragraphs
     cost nothing more and are excluded from the estimate).
   - For each remaining paragraph+context, calls `count_tokens` to get real input counts,
     accounting for prompt-cache economics: the first paragraph per chapter is a cache
     *write* (1.25x/2x of input price depending on TTL), the rest are cache *reads* (~0.1x)
     — **provided consecutive calls in a chapter land inside the cache's 5-minute TTL**. A
     stalled or slow run re-writes the prefix; note this as a caveat in the printed
     estimate, not a silent assumption.
   - Derives a per-paragraph output-token average from the persisted usage history (see
     groundwork above) and extrapolates to the remaining paragraph count.
   - Sums to a total dollar estimate, using pricing for whichever model is actually
     configured (`--model`/`--provider`) — don't hardcode Opus 4.8 pricing. OpenAI has
     different pricing and no identically-named free token-counting endpoint; scope this
     spec to the Anthropic provider for v1 and treat OpenAI parity as explicit future work,
     not silently unsupported.
   - Prints the result as **plain prose**, not a table — e.g. "Estimated cost to gloss the
     remaining 9 chapters (about 241 paragraphs): around $X.XX, based on real per-paragraph
     output sizes measured from your last run." This matters for the actual audience here —
     a blind user on a screen reader can't glance at a dashboard; a sentence with the number
     in it is the accessible form, not a table they'd have to scan cell by cell.

## Non-goals

- No account-balance check or auto top-up — no such Anthropic API exists.
- No per-call `max_tokens` tuning (settled separately, see the one-line fix noted in
  `docs/planned/budget-confirmation.md` — raising the global constant costs nothing and
  removes the truncation class entirely; there's no cost lever in tuning it per call).
- Doesn't touch `gloss_cache.json`'s format — the JSONL-migration question from the
  interrupt-safety discussion stays parked, separate from this.

## Open questions for whoever implements this — resolved

- Verb name and CLI shape: `estimate-gloss`, a distinct verb (not a `redact --estimate`
  flag), stacked on `base` like `draft-classical`.
- Prose wording: reviewed by ear against several real runs (cold-start, priced,
  unpriced-model abstain, no-synopsis-yet) — see CLAUDE.md.
- Usage-history file format: `gloss_usage.jsonl` (`redaction/usage.py`) — its own
  format, one JSON object per line, independent of the gloss *cache*'s format. Not
  merged with `gloss-cache-jsonl.md`'s eventual migration; the two logs record
  different things (finished paragraph output vs. run-level token usage) and there's
  no format collision to resolve.
