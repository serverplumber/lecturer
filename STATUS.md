# Status

**Prototyped to deliver; now in long-tail hardening.** Lecturer was built
fast to get real books to a listener, and it did: several monographs have
been taken end to end to a tagged `.m4b`. The work since has been the other
half: finding what a real run breaks, closing it, and writing down what is
still open so it can't be forgotten.

This file records both, as of the commit noted at the top of each list. An
entry leaves "Open" by being fixed, or by being moved to "Deliberate" with
the reason it stays.

---

## Hardened

As of `504004e`. Every item was found on a real run against a real book,
not in a synthetic test.

- **Streaming, not `.parse()`.** Raising `max_tokens` to 24000 crossed the
  Anthropic SDK's fixed non-streaming heuristic (~21,333), which refuses
  the call before it reaches the network. `count_tokens` has no such guard,
  so every pre-flight check passed and the first real chapter failed.
  `AnthropicProvider` now streams.
- **Retry headroom.** Two transient 500s each stopped a long run under the
  SDK's default two retries. Raised to six; a book is dozens of sequential
  calls.
- **Billed calls that never reached the counters.** A truncated response is
  billed in full, but its usage dies inside the SDK's `ValidationError`
  unwind. Fixed by raising `max_tokens` (billing is per token generated,
  not per ceiling) and counting any remaining truncations separately so the
  usage record discloses the gap rather than understating spend.
- **Prompt-cache tokens priced.** Cache writes (1.25×) and reads (0.1×)
  weren't tracked, so no real run's cost could be reconciled with its
  estimate. Now tracked end to end, priced by one shared `price_tokens`
  used by both the estimate and the post-run report.
- **Usage survives a crash.** A `ProviderError` mid-run skipped the usage
  write, silently shrinking the history the estimator extrapolates from.
  Now persisted on both paths.
- **No silent spend.** `redact --llm` prints an estimate and requires `y`
  or `--yes`; `--budget` refuses on the known portion and is never bypassed
  by `--yes`. The synopsis draft (itself a billed call) moved behind the
  gate. On providers with no free token count, `--budget` errors rather
  than silently checking nothing.
- **Stale cache warning.** The gloss cache is keyed by model, so a
  default-model bump orphaned 145 real entries. Now counted and reported
  before any billed call.
- **Feature probing over model lists.** Adaptive thinking is tried and
  dropped on the specific 400 a model without it returns, rather than kept
  in a list that goes stale.
- **Type checking.** `ty` added, and what it found fixed.

---

## Open

As of `504004e`.

### No test suite

**Gap.** Nothing under `tests/`. Correctness so far rests on end-to-end
runs against real corpora, whose outputs are diffable but not held to a
suite.

**Why it exists.** Prototype phase: real books were the forcing cases, and
synthetic fixtures for a copyrighted corpus are their own project.
`docs/planned/pytest-suite.md` has the plan.

**Closing it.** Pure functions first, since they need no fixtures:
`_faithful`, `_locate`/`_split`, `load_usage`'s backward compatibility with
older records, `price_tokens`. Then the deterministic layers against small
hand-written excerpts.

**Trigger.** Now. This is the phase.

### `TongueInterpreter` lags `Glossator`

**Gap.** The second LLM layer missed the hardening the first one got. Its
cache is written in place rather than via `.part` and rename; its calls and
tokens aren't counted or persisted; a batch with no usable answer returns
nothing and is not reported, where a failed gloss is reported in
`review.md`.

**Why it exists.** The glossator is the expensive layer and was hardened
first; the interpreter runs on the cheap tier.

**Closing it.** Atomic cache write; usage counters and a usage record;
failed batches reported the way `RevertedParagraph` reports failed
paragraphs.

**Trigger.** Now; it is the same work already done once.

### `OpenAIProvider` doesn't count truncated calls

**Gap.** `LengthFinishReasonError` returns `None` with nothing recorded, so
usage on the OpenAI and local-server path can understate what was
generated.

**Closing it.** Count it the way `AnthropicProvider.truncated` does.

**Trigger.** Now; small.

### Scanned and outline-less PDFs have no extractor path

**Gap.** A PDF with no text layer, no outline and no font-size profile
extracts with every footnote discarded (`_pairing_holds` warns rather than
failing silently).

**Why it exists.** Parked until a forcing case arrived. Upstream tools were
evaluated: MinerU strips footnotes and is out; Marker reuses an existing
text layer and is the candidate.

**Trigger.** Met. Graf's _Magic in the Ancient World_ and Yates'
_Art of Memory_ and _Lull and Bruno_ are genuine blobs; Williams'
_Rethinking Gnosticism_ has a text layer but no outline, which is exactly
Marker's fit. Wiring it in is the remaining work.

### Patristic sigla collide with Stephanus

**Gap.** "Apol." and "Leg." in chapter.section form (Justin, Apuleius,
Tertullian; Philo, Cicero) lose to Plato's identically spelled Stephanus
sigla under the priority tie-break. Citation review reports 21 such spans
in `temple_gates`; none was found mis-spoken as Plato, but that check was
by hand.

**Closing it.** The `patristic_sigla` system planned in
`docs/elocution.md`.

**Trigger.** Evidenced in one corpus already.

---

## Deliberate

Known, scoped, and staying until something forces them.

- **"Ann." in `temple_gates`** pairs with both Tacitus and Suetonius. It is
  a citation slip in the book itself, left as a stub for a human to settle
  against the text, by design.
- **Trailing fragment letters** ("57.18.5a", Cassius Dio's critical-edition
  numbering) strand the letter. One occurrence in the corpus. Trigger: a
  second.
- **Diels' volume/page shape** ("DK 1. 289.17"), distinct from the fragment
  grammar `diels_kranz.py` implements. Seen in one corpus. Trigger: a
  second.
- **Bibliography heading pattern is English-only.** A non-English heading
  yields a correct section but no parsed structure. Trigger: a non-English
  monograph.
- **Bekker numbering** is a closed citation system of the same shape as the
  implemented ones. Trigger: a book that cites Aristotle that way.
- **No per-chapter scoping on `redact`.** Re-runs are already
  paragraph-cheap via the cache; the stale-cache warning covers the costly
  case.
