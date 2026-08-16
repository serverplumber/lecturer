# Spec: shared citation canon

Status: not started, scoped only. No dependencies on other open specs (`docs/planned/` is
otherwise empty). Written for handoff to a fresh session — self-contained.

## Purpose

`redaction/elocution/canon.py` already runs a working cumulative canon for classical-work
sigla: a document's own `draft-classical` run seeds tier 2 (`<work dir>/classical_sigla.toml`),
and `promote-classical` graduates a resolved entry into tier 1
(`elocution_dir/classical_sigla.toml`), read by every future book on that machine via
`merged_sigla`'s `seed < tier1 < tier2` precedence (`canon.py:101-109`). But tier 1 only
accumulates *across one person's own books* — `elocution_dir` defaults to
`~/.config/lecturer/elocution`, and every directory that can hold one (`elocution/.gitignore`,
a work dir's own `.gitignore`) ignores it with a bare `*`. It has never been shared between
people.

The goal here is a second, genuinely cross-person canon: a descriptive record of scholarly
citation practice that nobody currently maintains — SBL and Chicago *prescribe* citation
practice; this would *record what real bibliographies actually do*, the same posture
`sniff_style` already takes for one document at a time (`redaction/elocution/bibliography.py`).
The concrete first fact worth recording this way is the same-author continuation marker: three
real corpora already sniffed give three different answers (temple_gates: typeset em dash
"———."; Couliano's *Tree of Gnosis*: double hyphen "--,"; Couliano's *Eros and Magic*: single
hyphen "-."), and none of it is persisted anywhere today — `sniff_style` recomputes it fresh, in
memory, on every call, from two independent call sites (`redaction/__init__.py`'s
`_bare_author_systems`, `draft.py`'s `_bibliography`), per `docs/elocution.md:186,274`'s own
note that even a single per-document `DocStyle` object hasn't been built yet, let alone
anything cross-document.

## Design tension this spec exists to resolve

The classical-sigla canon's own `promote()` (`canon.py:187-217`) is not a template to copy
as-is — it has a real gap the moment "shared" means "between people" rather than "between one
person's books." It copies only `entry["spoken"]` from a resolved tier-2 entry into tier 1,
deliberately dropping `count`, `candidates`, `bibliography`, `locators`, and `note`. Those
richer fields exist today only on **stubs** — unresolved entries a human hasn't confirmed yet
(`canon.py:121-148`; populated by `draft.py`'s `_ambiguous_stubs`/low-confidence-stub paths,
lines 101-117 and 186-192) — and vanish the instant an entry resolves, both when `draft()`
itself writes `{"spoken": ..., "count": counts[siglum]}` into tier 2 (dropping `locators`/
`bibliography` even there) and again when `promote()` strips it further down to bare `spoken`.

That shape makes sense for a *local* canon: once you trust an entry, you don't need to keep
re-justifying it to yourself. It's backwards for a *shared* one. The value of a shared entry to
someone else is being able to check it — which corpus it was observed in, which edition, how
many times, whether anyone's verified it — not inheriting a stranger's unexamined conclusion.
That's the project's existing abstain-over-guess posture (CLAUDE.md's standing constraint on
the LLM's role) applied one level up: not to whether the model should answer, but to whether a
shared fact should travel without the means to check it.

## Phase 1 — provenance-bearing resolved entries (classical sigla, still local-only)

Retrofit the *existing* canon before extending it, since the gap above is a pre-existing bug in
spirit, not something new Phase 2 introduces:

- Change `draft()` (`draft.py:136-196`) so a resolved answer keeps `locators` and
  `bibliography` (already computed per-candidate for the stub path — `_locators`/`_hints`,
  `draft.py:96-98`/`91-93` — just discarded once resolved) alongside `spoken`/`count`.
- Change `promote()` (`canon.py:187-217`) to copy the full provenance-bearing shape into tier 1
  instead of `table["spoken"] = entry["spoken"]` alone.
- Existing tier-1 entries — including this user's own already-promoted
  `classical_sigla.toml` — stay valid with no migration: `_resolved()` (`canon.py:67-78`) only
  requires a non-empty `spoken`, so provenance fields are additive, never required for
  `merged_sigla`/`Elocutor` to keep working.

Open question: should an existing spoken-only tier-1 entry ever be backfilled with provenance
(a pass that re-derives `locators`/`bibliography` from whichever document first promoted it,
if that's even recoverable), or left spoken-only forever, with only newly-promoted entries
carrying the richer shape? Leaning toward the latter (no speculative migration) unless a real
need shows up.

## Phase 2 — bibliography house-style canon (new fact type)

A new tier1/tier2 pair — e.g. `bibliography_styles.toml` — recording the same-author
continuation marker (and plausibly the fuller `DocStyle`: `recognized`, the tail-year-vs-
head-year signal, coverage ratio — `bibliography.py:130-144,176-225`) with the same permanent
provenance as Phase 1: occurrence count, a capped sample of the actual entries that showed the
marker, and a `note`/verifier field.

This can't reuse `merged_sigla`'s `dict[str, str]` shape directly — a style record is a struct,
not a single spoken string — so either `canon.py` gains a second, more general merge function,
or this gets its own small module mirroring `canon.py`'s tier1/tier2/promote pattern rather than
literally sharing its code.

Two open questions here, both surfaced in conversation and deliberately left unresolved:

1. **Scope key.** What identifies "this marker applies here" for a future document — publisher/
   series (assumes a press's house style holds across its books), a self-declared style name
   (e.g. "Chicago 17th NB" — matches how style guides are actually cited, but most books don't
   self-declare), or a per-book/edition record with publisher as metadata rather than as the
   key (most conservative — never assumes two books from the same press agree). The user's own
   framing ("which corpus, which edition") leans toward the last, but this hasn't been decided.
2. **Feeds behaviour, or stays descriptive?** Does a registry hit for a known book/publisher
   ever act as a *prior* for `sniff_style`'s own confirmation on a new document (e.g. lowering
   the `_MIN_COVERAGE` bar), or does `sniff_style` keep deciding fresh every time, with the
   registry only ever written to *after* independent confirmation? Leaning toward the latter —
   letting a registry hit substitute for verification is exactly the "inherit some rando's
   conclusion" failure mode the provenance requirement above exists to prevent — but not
   settled.

## Phase 3 — external distribution

A separate public git repository of TOML, mirroring whatever tier-1 shape(s) Phases 1–2 land
on. `promote-classical` (and Phase 2's equivalent verb, once it exists) gains a *submit* path
alongside its existing local-write path: stage the entry into a local clone of that repository
so the user commits/pushes/opens a PR through ordinary git tooling. No backend, no service to
run — PRs are the review mechanism, and the provenance fields from Phases 1–2 are exactly what
a reviewer needs to evaluate a submission, which is the actual payoff of not stripping them.

Corpora (raw source text under `texts/`) never leave the local machine — copyright. Only
derived vocabulary crosses: siglum/spoken pairs, continuation markers, `DocStyle` facts, and
locator/citation-reference strings (bare page/chapter/volume locators, not prose — the working
theory is that these are closer to fact than expression, but this hasn't had a real legal check
and shouldn't be treated as settled before any actual submission happens).

## Non-goals

- Not building any of this now — this spec exists to scope the work, per explicit request, not
  to schedule it. The user may shelve it indefinitely.
- Not retrofitting the other closed elocution systems (`biblical.py`'s SBL book sigla,
  `stephanus.py`'s Estienne pagination) into this shape — those are genuinely closed/universal
  facts already, hardcoded on purpose, nothing to crowdsource.
- Not building any auto-trust or auto-merge mechanism. Submissions stay human-reviewed via
  ordinary PRs; no reputation system, no automatic promotion from a submission into anyone's
  own tier 1.
- Not picking the external repo's host or licence now — any plain git host satisfies the
  no-infrastructure constraint; the choice doesn't affect the design above.

## Open questions for whoever implements this

1. Scope key for bibliography-style entries — publisher/series vs. self-declared style name
   vs. per-book/edition (see Phase 2).
2. Data captured — continuation marker alone vs. the fuller `DocStyle` (see Phase 2).
3. Whether a registry hit ever feeds back into `sniff_style` as a prior, or stays purely
   descriptive forever (see Phase 2).
4. Whether Phase 1's provenance-bearing redesign should ever backfill existing spoken-only
   tier-1 entries, or stay forward-looking only (see Phase 1).
5. Exact module shape for Phase 2's canon — extend `canon.py` generically, or a parallel
   module — once the scope-key question above is settled enough to know what the merge
   function actually needs to key on.
6. The external repository itself: host, name, and licence for the shared data, and a real
   (not just working-theory) check that locator/citation-reference strings are safe to publish
   under the fact-not-expression theory above.
