# Lecturer

Text-to-voice pipeline that turns monographs into audiobooks sounding like the author
lecturing from their own book. Planned hard part: extracting footnotes and having an LLM
weave them into the text as spoken digressions. TTS will start with
[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M).

## Layout

- `lecturer.py` — the cement-based CLI: sets up the work directory and runs extraction.
- `extraction/` — strategy-pattern extractors (epub, pdf) producing `Section`s of running
  text with `[^ref]`-anchored footnotes. A section whose title reads as a bibliography
  gets a second pass in `pdf.py`: pymupdf's own block detector glues a hanging-indent
  reference list into one blob when consecutive entries don't leave it enough vertical
  gap to split on (entries run straight into each other with no separating space at all),
  so entries are instead recovered from each line's left-margin position — a
  `BibliographyEntry` per reference, the margin fixed per *page* rather than once for the
  whole section, since this corpus mirrors margins between facing pages. Segmentation
  only, verbatim down to any same-author continuation dash ("———.") the typesetting used
  in place of repeating a name — parsing what an entry *means* (author, primary vs.
  secondary source, the sigla it should resolve) is redaction's job, not extraction's.
  `epub.py` needs no such geometry hack: an EPUB's own `<p>` markup already bounds each
  entry, so its bibliography pass just finds the heading (guarded by a title-length check,
  since some conversions mistag a long body paragraph that merely contains the word
  "references" as a heading element) and takes the `<p>`/`<li>` siblings after it, merging
  one that doesn't end in terminal punctuation into the previous entry — a source
  line-wrap the conversion turned into a paragraph break, the same call `SeamMender` makes
  for prose torn by a page break. Chapter splitting reads the book's own navigation tree
  (`_nav_leaves`) rather than the spine alone: the spine only gives file order, and this
  corpus's EPUBs nest three navPoints deep (Part > numbered chapter), so only leaf
  navPoints become sections — a Part-level entry would otherwise swallow every chapter
  under it into one section spanning several. Read from the NCX the spine's `toc`
  attribute names; an EPUB3 nav document isn't parsed yet, since neither validated EPUB
  (both Calibre/EPUB2 productions) declares one. A leaf's fragment can land mid-file —
  one Couliano EPUB packs three chapters and its bibliography into a single physical file,
  fragment-addressed — so a file's own top-level blocks are cut at whichever block carries
  that fragment's id, not just at file boundaries. A file with no leaf of its own (a
  chapter Calibre split across several physical files, the nav pointing only at the first)
  continues whichever section is still open rather than becoming spurious back matter;
  only content past the very last leaf earns that label — the earlier version of this
  routed *any* untargeted file to back matter once one leaf had been seen, silently moving
  a third of some chapters' own footnote-bearing text there. Verified against Couliano's
  *Eros and Magic* and *I miti dei dualismi occidentali*: each section's own footnote
  markers summed to the same book-wide total `pull_endnotes` finds (492 of 493 — the one
  gap is a pre-existing unpaired note predating this change, not investigated further),
  and dropping `linear="no"` spine items (a redundant cover page, and the interactive nav
  document itself — its own `<li>` list would otherwise read as body paragraphs) keeps two
  near-duplicate blobs out of the running text. Front matter still legitimately speaks a
  "Table of Contents" heading and the chapter list beneath it — a real printed Contents
  page from the book's own front matter file, not a nav artefact, so left as verbatim
  extraction requires; only redaction gets to judge whether it's worth reciting. Surfaced but left alone:
  `BIBLIOGRAPHY_TITLE`'s English-only regex means a non-English heading like "Riferimenti
  bibliografici" still gets its own correct section but never gets parsed into
  `BibliographyEntry` structure — no non-English book is actually in flight yet.

  **Parked: a structureless-PDF front end.** A scanned book with no real text layer, no
  outline, no font-size profile has no extractor path yet. Evaluated against a shortlist
  of upstream layout/OCR tools (pdf-craft, Marker, MinerU, olmOCR) looking for one that
  could turn such a blob into something with a TOC, front/back matter, and footnotes —
  i.e. something structured enough to hand to `epub.py`, reusing its nav-based chapter
  splitting above rather than reimplementing structure recovery per tool. One firm
  disqualification and one real candidate came out of it, but no forcing case to wire
  either in yet. **MinerU** strips footnotes outright ("removes headers, footers,
  footnotes... to ensure semantic coherence") — ruled out regardless of anything else,
  since footnote weaving is this project's whole point. **Marker** is Apache-2.0 for its
  code (a shortlist that had it down as GPL-3.0 was wrong) and is the only candidate that
  reuses an existing PDF text layer rather than always OCRing (`disable_ocr`), which
  matters since every real PDF in this corpus already has one. **pdf-craft** outputs EPUB
  with an auto-generated TOC — exactly the shape that would feed `epub.py` — but always
  runs DeepSeek-OCR even over a PDF with a perfect text layer, making it a poor general
  front door and a fit only for an actual blob. **olmOCR** always runs a 7B vision model
  per page with no documented footnote handling — a last resort for genuinely degraded
  archival scans, not general use. None of this is wired in yet, but the corpus has since
  grown real forcing cases — Fritz Graf's *Magic in the Ancient World* and Yates' *Art of
  Memory* and *Lull and Bruno* are genuine blobs (`pdf.py`'s three-signal test —
  `doc.get_toc()` empty, `_font_profile`'s `note_size` coming back `None`,
  `_pairing_holds` failing — holds for all three). Kingsley's 2002 journal article
  "Empedocles for the New Millennium" is a near-miss on that same test — a real
  `note_size` (7.8pt) and, after fixing `_NOTE_START` to accept a bare space as well as
  a period, real note *text* (163 parsed, up from 2) — but the in-body superscript
  digits carry the OCR's own character-substitution errors (`[` for `I`, `.` for `,`,
  seen throughout its footnotes too) often enough that only 37% of notes ever find their
  anchor, short of `_pairing_holds`'s 50% floor, so it still extracts with every
  footnote discarded. Michael Allen Williams' *Rethinking
  Gnosticism* and the PDF duplicate of Couliano's *Eros and Magic* are a narrower case:
  a real text layer, no OCR needed, but no embedded outline at all (only two of the three
  signals) — exactly Marker's fit, since `disable_ocr` reuses that text layer rather than
  discarding it. All of these are English, unlike the non-English blobs
  `BIBLIOGRAPHY_TITLE`'s regex and the other closed-vocabulary systems above were
  originally parked for — internationalization is no longer the blocker for this group;
  actually wiring Marker in is. The one file with no extractor at all — the `.djvu` of
  *Eros and Magic* — still just duplicates a title already extracted from its EPUB.
- `redaction/` — redactional layers (`Redactor`s, applied in order) reworking the
  extraction into a `Script` of `Utterance`s tagged with a delivery `Manner`, ready for
  the TTS. Named for redaction criticism. Current layers, in order: `SeamMender` (joins
  paragraphs torn by page breaks), a footnote weaver, `Elocutor` (speaks inline citation
- `redaction/` — redactional layers (`Redactor`s, applied in order) reworking the
  extraction into a `Script` of `Utterance`s tagged with a delivery `Manner`, ready for
  the TTS. Named for redaction criticism. Current layers, in order: `SeamMender` (joins
  paragraphs torn by page breaks), a footnote weaver, `Elocutor` (speaks inline citation
  abbreviations aloud instead of leaving them for the TTS to mangle — "1 Cor 2:10" →
  "First Corinthians two, ten"; a list of `System`s in `redaction/elocution/`, one file
  per abbreviation scheme, each tried in turn — see below), `LanguageTagger` (splits
  utterances at writing-system boundaries and tags them, e.g. `lang=grc`; Latin-alphabet
  language switches are left for `TongueInterpreter`), optionally `TongueInterpreter`
  (`--interpret`: LLM-tags Latin-alphabet switches maximally — loanwords, Latin phrases,
  transliterated Greek, source-form names; cheap model by default, `tongue_cache.json`
  in the work dir), and `Cantillator` (points overlong comma-free
  stretches with breath commas at clause boundaries — unspoken, but the TTS breathes
  there instead of improvising a pause mid-phrase). The weaver is `NoteDropper` by default (read
  the book plain — anchors stripped, no note spoken), `Glossator` with `--llm` (one call
  per annotated paragraph, prefixed by a cache-stable context — the work dir's
  `synopsis.txt` (drafted once by the glossator's model, then hand-editable, never
  regenerated) plus the full current chapter under a cache breakpoint; substantive notes
  respoken as asides, bare citations dropped; write-through cache in `gloss_cache.json`,
  keyed by paragraph inputs only so context refinements never invalidate finished work), or `FootnoteWeaver` with
  `--verbatim-notes` (every note verbatim at its anchor — inspection mode). The glossator
  calls through `Provider` adapters in `redaction/providers.py` — `--provider
  anthropic` (default) or `openai`; local models run via the openai adapter with
  `--base-url` pointed at any OpenAI-compatible server (Ollama etc.; `--effort high` for
  gpt-oss). A faithfulness guard requires the returned body prose to reproduce the
  paragraph verbatim and in full; guarded or failed paragraphs fall back to the verbatim
  weave. `AnthropicProvider` sends `thinking={"type": "adaptive"}` optimistically and, on
  the specific `BadRequestError` a model without adaptive-thinking support raises (Haiku
  4.5 among them — the default for every cheap-tier call: `draft-lexicon`,
  `TongueInterpreter`, `draft-classical`), disables it and retries once, then stays off for
  that provider instance — found for real running `draft-classical` against `temple_gates`;
  a hardcoded model list was rejected in favour of this since it would only go stale as new
  models ship.
- **Citation dictation**, in `redaction/elocution/` — inline scholarly citations
  ("1 Cor 10:2–4", "Or. 32.9.6–10") are author's-own-prose, not apparatus, so they can't
  be dropped like bare footnotes; they need to be *spoken*, just not as written. Not
  folded into the lexicon (phoneme-level substitution, not word rewriting) and not folded
  into `Glossator` (whose faithfulness guard requires body text verbatim; `Elocutor` is
  the first layer allowed to rewrite the author's actual words). Plain regex throughout —
  a parser generator would buy grammar (nesting, precedence) these flat locators never
  need, and it can't fix cross-system siglum collisions either, since those are semantic,
  not structural. `base.py` holds the engine (`System`, `mechanical_locator`, `Elocutor`);
  one file per abbreviation scheme holds only its siglum table. Recognition splits in two:
  the numeric locator (siglum + multi-part number/range) is mechanical — spelled out, with
  book/chapter/section labels dropped ("6–10" → "six to ten"; a range dash may be a
  hyphen, en dash, or true minus sign — this corpus's typesetting uses U+2212) — labels
  come back only if a sample sounds wrong without them; the siglum's spoken form is each
  system's own vocabulary.
  `Elocutor` merges every system's sigla into **one combined regex pass**, not one
  sequential pass per system: a separate pass per system would let a later, narrower
  pattern's own scan claim a substring an earlier, wider citation should have owned whole
  (biblical's "2 Cor" vs a bare classical "Cor." would turn "2 Cor. 3.18" into "2
  Coriolanus three, eighteen" under naive sequential passes). One merged, longest-siglum-first
  alternation lets the regex engine's own leftmost, non-overlapping scan settle that for
  free. Entries are never deduplicated by siglum text alone — two systems can legitimately
  share a written siglum with *different locator shapes* (Plato's "Apol." in Stephanus
  page+letter vs. a patristic "Apol." in chapter.section), and since each is its own
  alternation branch with its own locator sub-pattern, the regex engine's own backtracking
  picks whichever one's full pattern actually matches the text that follows — no explicit
  disambiguation needed. Only a siglum that is identical *and* shares a locator shape
  ("Num" for Numbers vs. Plutarch's *Numa*, both plain dotted numbers) is genuinely
  ambiguous; those tie-break by system priority — earlier systems in `default_systems()`
  win. A real "Num" citation for the losing system, in a corpus that cites both, is the
  one case this can't get right — that needs context, which is exactly the boundary the
  LLM-drafted systems below are meant to live behind, not cross.
  `bare_author_system` is the first system that isn't a siglum table: most classical
  authors never get their own multi-work abbreviation (SBL enumerates the ones that do —
  Josephus, Philo, Suetonius, ... — each because their body of distinct works needs
  disambiguating), so someone conventionally cited as having written one work is just
  named directly before the locator ("Cassius Dio, 57.25.8", "Livy, 1.36.2–6"). Reuses the
  same matching/replacement machinery, keyed by the author's own full name instead of an
  abbreviation — the "siglum" is the name, "spoken" is that name again with its comma
  baked in (the separator itself is consumed by the match, so the pause a reader would say
  has to be re-added; added unconditionally, even where the source has none). `_merge`'s
  separator between siglum and locator is `[,.]?` (was `\.?`) to admit this comma
  alongside the existing period-or-nothing convention — a single literal space, not
  `\s+`, since extraction joins paragraphs with blank lines and widening the whitespace
  too would let a siglum-shaped word ending one paragraph match across the break.
  Verified against `temple_gates`: diffed `Elocutor`'s full output over all 748 footnotes
  before and after, both with the separator widened alone (zero changes) and with a
  `bare_author_system(["Cassius Dio"])` added (22 lines changed, every one a genuine new
  Cassius Dio conversion, nothing else touched). Surfaced two narrow, pre-existing edge
  cases the generic locator was never exercised against before now: a trailing
  disambiguation letter ("57.18.5a" converts "57.18" and strands ".5a" — an excerpt
  fragment number from Cassius Dio's own critical edition, not Stephanus's fixed a-e page
  division; still open, and only one occurrence in this corpus so far, not yet worth
  building for. Unlike Stephanus's own letter, which is capitalised so a TTS reads it as a
  letter name rather than the indefinite article, a bare letter needs no such
  transliteration — Kokoro already pronounces it correctly as-is). The other edge case — `LOCATOR` capped at three dot/colon-separated
  numbers, stranding a fourth ("Livy, 13.16.8.1" converted "13.16.8" and left ".1") — is
  fixed: uncapped to one-or-more repetitions on both the main chain and the range side,
  since nothing about the grammar depends on a fixed depth and real citations in this
  corpus go to four parts. Re-verified against `temple_gates`: 3 more lines changed, every
  one a genuine fix, nothing else moved.
  - `bare_authors.py` — turned out *not* to be purely document-local after all: whether
    Cassius Dio needs a work-siglum is a fact about how many works Cassius Dio wrote, not
    about any one book's own bibliography, so it's the same kind of closed fact
    `biblical.py`/`stephanus.py` hardcode once rather than re-derive per document. The
    trigger was Livy — cited bare five times in `temple_gates`' own footnotes, exactly
    like Cassius Dio, but with *no* separate bibliography entry in this book at all, so
    `pair_sigla`'s bibliography-gated derivation could never confirm him no matter how
    many real citations existed. `BARE_AUTHORS` holds both names, each verified against a
    real citation rather than transcribed from any handbook, and feeds `default_systems()`
    via `bare_authors_system()` — universal, like every other closed system. `redact()`'s
    `_bare_author_systems` still runs `sniff_style` → `parse_bibliography` → `pair_sigla`
    per document, but now only as the supplementary layer for whatever a *specific* book's
    own bibliography confirms beyond this closed list, excluding names already in
    `BARE_AUTHORS` so the two layers don't double up. Re-verified against `temple_gates`
    after the split: 10 more lines changed, every one a genuine new Livy conversion,
    Cassius Dio's untouched.
  - `biblical.py` — the SBL Handbook's book sigla: closed, universal, hardcoded, no draft
    needed.
  - `stephanus.py` — Plato's dialogues, cited by Henri Estienne's 1578 page+letter
    pagination rather than any edition's own page numbers. Closed and standard like
    biblical, so also hardcoded, but its locator shape ("364b", "514a2", ranges like
    "364b–365a") is different enough from the dotted default that it supplies its own
    (`base.py`'s `STEPHANUS_LOCATOR`/`stephanus_locator`). Its "Apol." (Plato's *Apology*)
    is the reason the shape-based disambiguation above exists: the classical citations in
    this corpus already use "Apol." for a patristic Apology under the dotted locator, so
    the two need to coexist under the same siglum without either being dropped once
    classical's table grows to include it.
  - `classical.py` — the heterogeneous Latin author-work abbreviations ("Or." → "Oration",
    "Ann." → "Annals", ...). Open-vocabulary, so past its one hand-verified seed ("Num" for
    Plutarch's *Numa*, listed first in `default_systems()` so it wins the tie against
    biblical's Numbers) the real table is grown externally, in `redaction/elocution/
    canon.py`'s two tiers, rather than by further hand-editing this module: tier 1
    (`elocution_dir/classical_sigla.toml` — this machine's shared canon, valid for every book) and
    tier 2 (`<work dir>/classical_sigla.toml` — this one document's own entries). Both TOML, both
    for the same reason: an entry can carry a real comment recording *why*, the same
    provenance the closed tables keep inline, rather than splitting formats because tier 2
    is also tooling-written — `promote-classical` (below) already proves `tomlkit` writes
    TOML programmatically, comments and all, so there was never a principled reason to keep
    tier 2 on JSON once it needed to carry that kind of provenance too. Precedence is seed <
    tier 1 < tier 2; only `promote-classical` ever writes tier 1, additively, never touching
    a siglum it already has. `elocution_dir` is ordinary Cement config (`[lecturer]
    elocution_dir`, or `LECTURER_ELOCUTION_DIR`), defaulting to `~/.config/lecturer/
    elocution` so a real install needs no setup — see `docs/contributing.md` for the
    repo-local dev override that keeps a checkout's own canon from silently sharing state
    with an installed copy on the same machine.
  - `draft-classical`/`promote-classical` (`redaction/elocution/draft.py`, `canon.py`) —
    `draft-classical` seeds tier 2 by reusing `citation_pairing.py`'s `pair_sigla`: computed
    there already, but until now only its `siglum is None` (bare-author) rows were used, the
    `siglum is not None` rows are candidates here, excluding any siglum a system already
    resolves (covers Josephus/Philo's own dedicated tables for free, since their sigla are
    already in the merged set) and any siglum `pair_sigla`'s own `collisions()` flags
    ambiguous. The LLM's only job is expanding an already-confirmed author+siglum pair into
    a spoken title ("AJ" → "Jewish Antiquities") — narrower and safer than guessing
    authorship, exactly the boundary this file and `citation_pairing.py` were originally
    written to describe before either was built. A siglum that stays unresolved — genuinely
    ambiguous, or the model wasn't confident — isn't dropped: it's written into tier 2 as a
    **stub**, no `spoken` key (so `canon.py`'s loader ignores it exactly as if it weren't
    there) but a real TOML comment recording why, plus a `bibliography` hint pulled verbatim
    from this document's own confirmed primary-source entries naming the candidate
    author(s). A stub is the one thing a later, more confident run is allowed to overwrite
    without a human editing it first; two stubs never replace each other, so a hint stays
    stable rather than churning every run. `promote-classical` copies only `spoken` into
    tier 1 — a stub's own `note`/`candidates`/`bibliography` are this document's scratch
    context, not a fact about the siglum worth keeping once resolved. Verified end to end
    against a real re-extraction of `temple_gates`: 27 real candidates, correctly withholding
    "Ann." (Tacitus 13x vs. Suetonius 1x — the same collision `citation_pairing.py`'s own
    bullet below already confirmed a genuine citation slip in the book, not a scanner bug);
    two separate real model runs resolved 25 then 2 more (additive, nothing overwritten);
    promoted into `classical_sigla.toml`, idempotent on a second promote; and
    `default_systems(elocution_dir=...)` actually speaking a promoted entry through
    `Elocutor` ("Suetonius, Ner. 49.2" → "Suetonius, Nero forty-nine, two"). Surfaced along
    the way, fixed, unrelated to this feature specifically: `AnthropicProvider.ask` sent
    `thinking={"type": "adaptive"}` unconditionally, and Haiku 4.5 — the default cheap tier
    every draft sweep here uses (`draft-lexicon`, `TongueInterpreter`, `draft-classical`) —
    rejects it outright; now an instance-level fallback (optimistic on the first call,
    retries once without thinking on that specific error, stays off after) rather than a
    model-name list that would only go stale. See `docs/classical-sigla.md` for the
    walkthrough.
  - **Still to come**: Bekker numbering and Diels-Kranz are further closed, enumerable
    systems of the same shape as biblical/Stephanus once they show up outside footnotes.
    Units (SAE vs SI collisions) are parked until citation dictation's systems are mature
    enough to tell whether the same machinery generalises or the two need separate
    treatment.
  - `bibliography.py` — turns extraction's raw, geometry-segmented `BibliographyEntry`
    list into structure: `authors`, `role` (ed./eds., an editor's names still belong in
    `authors`), `translator` (a "Pausanias, trans. X" entry's translator is not any kind
    of author of the work, so it gets its own field — `authors` is left empty rather than
    misattributed), `title`, `container` (journal siglum, or the book a chapter is *in*),
    `editors`, `year`, `pages` — one dataclass, one parser, one module,
    per `docs/elocution.md`'s Pass 0/1, rather than split across per-component files: no
    database or service boundary here justifies carving up one parsing job over one list of
    strings. `sniff_style` confirms (never assumes) the corpus's one validated house style —
    Chicago/SBL notes-bibliography, year at the entry's tail — before the parser runs at
    all; author-date's year-after-author, or anything else unconfirmed, abstains every
    entry to raw `text` rather than mis-parsing a shape this project has never tested
    against. Confirmation needs *coverage*, not just an absolute count: validated against a
    second real bibliography (Couliano's *Tree of Gnosis*, a different house style
    entirely), an early version of the gate misfired — 5 of 288 entries happened to parse
    as tail-year, clearing the absolute threshold while the other 283 went unmeasured and
    unrecognized. Fixed by requiring the tail-year signal to cover a real fraction of the
    whole entry list (`_MIN_COVERAGE`), which separates the two corpora (63.9% vs. 1.7%)
    where the ratio among only the entries that parsed couldn't (~99% for both). The
    same-author continuation marker is also fully sniffed, never hardcoded: three real
    corpora have shown three different markers (temple_gates' typeset em dash "———.",
    *Tree of Gnosis*'s double hyphen "--,", Couliano's *Eros and Magic*'s single hyphen
    "-.") — both the character and the run length are read off the document, not assumed
    to be an em dash repeated three times. Every field is
    best-effort and `text` is always kept verbatim regardless. `classify_sources` classifies
    each parsed entry primary (ancient) vs. secondary (modern) — HEU feature scoring, not
    identity resolution, from structural signals verified against real bibliographies rather
    than assumed: a non-empty `translator` (fronts a modern name but presents someone else's
    work as a translation — `authors` is already empty for these) is strong enough alone. A
    bare/natural-order first author (no comma — "Cassius Dio" rather than a modern scholar's
    "Surname, First") is **not** strong enough alone, even though it looked that way against
    the first validated corpus: a second real one (Couliano's *Eros and Magic*) turned up
    "Faust. Cahiers de l'Hermétisme..." and "Soleil. Le Soleil à la Renaissance...", where the
    bare capitalized word is the print bibliography's own filing keyword for an anonymous
    themed collection, not a person. It now needs corroboration from a modern edition
    apparatus — a known ancient-text series (`LCL`, `Loeb Classical Library`, `Ancient
    Christian Writers`) or a "Translated by"/"Edited by" credit anywhere in the entry's own
    text (checked as raw text, since those fields are only structurally populated for
    specific entry shapes and "Translated by Earnest Cary" sits mid-entry in a plain "Author.
    Title." bare-name entry) — every genuine bare-name entry in both validated corpora
    carries one or the other, since an ancient text only reaches a modern bibliography
    through a modern edition or translation. The apparatus signal alone still isn't enough,
    precisely because of the original counterexample (a modern "Introduction" essay published
    *inside* a Loeb-adjacent volume, correctly left secondary). This is the foundation
    `draft-classical`'s LLM sweep reads from, via `citation_pairing.py`'s `pair_sigla` below.
  - `citation_pairing.py` — a document's own author-siglum vocabulary, read off its
    footnotes rather than aligned from bibliography titles. `docs/elocution.md`'s
    `truncation_aligner` (component 6) assumed a bibliography entry's title text could be
    aligned against a footnote's abbreviation; this corpus's primary sources are collected
    Loeb-style entries with no per-work title to align against, so that never had anything
    to work from. What works instead: a citation already names its author in full right
    next to the siglum ("Josephus, AJ 18.81–84", "Tacitus, Ann. 2.32") — `pair_sigla`
    counts every (author, siglum) pairing the footnotes' own text supplies, gated on
    `bibliography.py`'s confirmed `is_primary_source` authors so no name is ever guessed,
    only read. An author cited with no siglum at all ("Livy, 1.36.2–6") is itself a real
    result — one work, nothing to abbreviate. `collisions` flags a siglum paired with more
    than one author in this document rather than silently keeping whichever it saw last;
    verified against `temple_gates`, the one collision it caught ("Ann." — Tacitus and
    Suetonius) turned out to be a genuine citation slip in the book itself, not a scanner
    bug — still left for a human, not resolved here or by `draft-classical` below, since
    which of the two is right is exactly the judgement call `collisions()` exists to hand
    off rather than guess. Wired up by `draft-classical` (above): every other pairing here
    — one where `pair_sigla` paired exactly one author with a siglum — is a candidate for
    turning that siglum into a spoken expansion ("AJ" → "Jewish Antiquities"), a narrower,
    lower-risk LLM ask than guessing authorship, since the author side is already settled
    here.
  - **Citation review** — every abstain-over-guess layer above still needs a way to tell a
    human "look here," not just silently leave text unconverted. `Elocutor` now scans its
    own input (both utterance text and, for the `book` variant, notes `NoteDropper` left on
    `section.footnotes` rather than folding into utterances — the only weaver that leaves
    citations Elocutor's substitution pass never touches) for a known siglum sitting next to
    something locator-ish — a digit immediately glued on, or a couple of separator
    characters away — that the strict merged pattern didn't accept. Not a diagnosis: it
    reports *where*, with enough surrounding context to read *why* off the text, not a
    guess at which of several possible causes (missing space, OCR noise, an uncovered
    locator shape, a genuine siglum collision) applies — the same posture as every abstain
    above. `PatternSystem` (Qumran) is skipped: a generative shape has no fixed siglum to
    scan for in the first place. `lecturer.py`'s `write_review` writes the result to
    `redactions/<variant>/review.md` — `.md`, not `.txt`, so `read_redactions`'s glob never
    mistakes it for a section — overwritten every run, even to "nothing to review," rather
    than deleted, so a run with a narrower `systems` set can't make an existing review
    vanish out from under someone reading it. Verified against two real corpora: Kingsley's
    *Ancient Philosophy, Mystery, and Magic* (a blob PDF, so its Diels-Kranz citations sit in
    running body text rather than footnotes) surfaced 27 spans in a report short enough to
    read end to end, including the 3 already known from `diels_kranz.py`'s own TODO
    ("DK47A1" with no space, "DK 21 Bag" and "DK 87 B6o" from OCR digit/letter confusion) —
    plus a genuinely new pattern, "DK 1. 289.17" and the like: Diels' own volume/page
    citation shape, distinct from the chapter/letter/item fragment grammar `diels_kranz.py`
    implements, evidenced but not yet worth building a system for on one corpus alone.
    `temple_gates` surfaced 21 spans, all one shape: Justin's/Apuleius's/Tertullian's
    "Apol." and Philo's/Cicero's "Leg." in chapter.section form, losing to Stephanus's
    identically-spelled "Apol."/"Leg." (Plato's *Apology*/*Laws*, page+letter form) under
    `_merge`'s priority tie-break — confirming component 9 `patristic_sigla`'s gap
    (`docs/elocution.md`) is a real, evidenced collision in this corpus, not just the
    hypothetical the shape-disambiguation design doc-comment above uses as its example.
    Checked for the live-mispronunciation risk this implies (a `Leg.`/`Apol.` locator that
    *does* happen to fit Stephanus's page+letter shape would be silently spoken as Plato,
    invisible to a review that only reports what the pattern rejected): none found in
    `temple_gates`'s redacted output. Separately, `extraction/pdf.py`'s `_pairing_holds`
    bail — silently discarding every parsed footnote on an OCR/anchor mismatch — now
    `warnings.warn`s instead of failing silent, the one bail site destructive enough
    (whole-document footnote loss) to warrant a warning ahead of citation review's own
    per-document report.
- `recitation/` — speaks the script (`--speak`): `Reciter` strategy protocol, one WAV per
  section into the work dir's `audio/`. `KokoroReciter` runs Kokoro-82M via kokoro-onnx
  (pure wheels, CPU ~4× realtime; model fetched once into `~/.cache/lecturer`). Text is
  chunked at sentence boundaries under Kokoro's 510-phoneme batch limit (mid-sentence
  splices sound like random commas). Apparatus sections (front matter, bibliography, index, ...)
  are skipped by default — `--sections REGEX` chooses explicitly — and existing WAVs are
  kept, so re-runs only synthesise what's missing. `publish` binds the recited sections into
  per-section Opus (~10x smaller, streamed through the soundfile wheel's libsndfile)
  plus an `.m3u` playlist with section titles and durations, and — when ffmpeg is on
  PATH — a single chaptered `.m4b` audiobook per variant (the universal format; AirDrop
  it to a phone and Books treats it right). Both the Opus files and the `.m4b` carry real
  tags — title, artist/album_artist, album, date, genre — read from the source document's
  own metadata (`extraction.read_metadata`: an EPUB's OPF `<metadata>` block, filtering
  `dc:creator` to `opf:role="aut"` so a translator credit doesn't end up as a co-author; a
  PDF's trailer Info dictionary, trusting `creationDate` for the year since a born-digital
  PDF stamps that close to publication — unlike an EPUB's separate Calibre-conversion
  timestamp, which is why that one reads `dc:date` instead). Every field is left `None`
  rather than guessed when the document doesn't state it plainly, the same abstain-over-guess
  posture as `sniff_style`. One field is spent on the software itself: every file's `comment`
  tag credits Lecturer with a link back to the repo — the one part of "fill in every field"
  that isn't a fact about someone else's book. Confirmed with `ffprobe -show_entries
  stream_tags`/`format_tags` rather than trusting exit codes: libsndfile's OGG/Opus writer
  does honour `SoundFile.title`/`.artist`/etc. (surfaced as upper-case Vorbis comments,
  `software` becomes `ENCODER`), but only if set before the first `write()` call, and
  `ffprobe -show_format` alone won't show them — Opus tags land at the stream level, not
  the format level, a container-parsing quirk of this ffprobe/libsndfile combination, not
  evidence they're missing. Titles run through `-metadata`'s escaping rules
  (`\`, `=`, `;`, `#`, newline) before they reach the `.m4b`'s `FFMETADATA1` file, chapter
  titles included — previously unescaped, latent since no title so far has actually
  contained one of those characters. Bound by the same WAV-mtime gate as the rest of
  `publish`: an already-built `.m4b`/`.opus` doesn't regain tags on a plain re-run; delete
  it to force a rebuild. `--voice` takes a name or a weighted
  blend of style vectors (default `af_kore+af_aoede`; af_heart/af_bella glottal-pause before
  vowel-initial words — measure, don't trust ears alone). Tagged languages Kokoro
  was trained on switch to a native voice; Latin (Italian rules — ecclesiastical) and
  Greek (Modern Greek values — Reuchlinian; transliterations via Italian) are spoken in
  the lecture's own voice; the rest are skipped and counted. The work dir's `lexicon.json`
  gives recurring names and terms their pronunciation (`recitation/lexicon.py`): `as`
  respellings, `lang` reroutes, or exact `ipa`, applied at phoneme level;
  `--lexicon-draft` seeds it with a cheap LLM sweep (never overwriting hand-edits), and
  audio signatures include per-section lexicon digests so editing an entry re-renders
  only the sections that use it.
- `texts/` — source monographs (gitignored; copyrighted material).
- `elocution/` (or wherever `elocution_dir` points) holds `redaction/elocution/canon.py`'s
  tier 1 — `classical_sigla.toml` today, the shared sigla canon every book draws on. Not a work
  dir (it outlives any one book), but self-ignoring the same way, and gitignored from a dev
  checkout via `lecturer.conf` — see `docs/contributing.md`.
- Working directories (e.g. `./eros_magic`) are created by the CLI wherever `-o` points
  (`-d` belongs to cement's `--debug`). Each contains a copy of the source document, a
  `working_text` symlink to it, a `sections/` directory of extracted text + footnotes
  files, a `redactions/<variant>/` tree of manner-tagged utterances (plus
  `.unwoven.txt` leftovers), forked per weaving like `audio/`, an `audio/<variant>/` tree of per-section WAVs, Opus files, and an `.m3u`
  playlist per variant — the final audio. **Weaving variants fork the tree** and live
  side by side: `book` (notes dropped), `glossed` (`--llm`), `verbatim`
  (`--verbatim-notes`). Within a variant, reciter changes (voice, speed) overwrite:
  each WAV's JSON `.sig` sidecar names the reciter and hashes the section's utterances,
  so re-runs keep unchanged sections, re-synthesise stale ones, and `--publish` follows
  via mtime; the playlist records the reciter in a comment. Text outputs (`sections/`,
  `redactions/`) hold whatever the last run produced. A work dir may also carry
  `lexicon.json` (pronunciation) and `classical_sigla.toml` (this document's own tier-2 sigla,
  `redaction/elocution/canon.py`) — both hand-editable, both grown by a `draft-*` verb
  rather than regenerated wholesale. Each work dir contains a self-ignoring `.gitignore`.

## Commands

Everything routine is in the `justfile`:

- `just setup` — `uv sync` + install pre-commit hooks + provision `lecturer.conf` from
  `lecturer.conf.example` (once after cloning; never overwrites an existing
  `lecturer.conf`). See `docs/contributing.md`.
- `just lint` / `just fmt` / `just check` — ruff, same as the commit hooks run.
- `just run -o <dir>` — the whole chain to publish, default settings. The phases are
  verbs — `extract` (takes the document; a different one prompts before rebuilding from
  the top), `redact` (weaving + LLM flags), `recite` (`--variant/--voice/--speed/
  --sections`), `publish`, `draft-lexicon` (drafts pronunciation entries, then stops for
  review), and `draft-classical`/`promote-classical` (draft this document's own
  `classical_sigla.toml` sigla, then graduate one into the shared canon — see
  `docs/classical-sigla.md`). Verbs resolve their own dependencies: free phases run on
  demand, glossing never runs implicitly.

Use `uv` for all dependency management (`uv add`, `uv add --dev`), never pip. direnv
activates the venv; `.envrc` runs `uv sync` on entry.

## Conventions

- Canadian/British spelling in prose, docs, comments, and user-facing strings
  (colour, behaviour, artefact, -ise).
- If the user makes a spelling mistake or typo (in prose, identifiers, anywhere),
  point it out rather than propagating it into code.
- Ruff handles formatting and linting; config lives in `pyproject.toml`
  (line length 100, py313).
