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
  archival scans, not general use. None of this is wired in: every PDF currently in
  `texts/` is born-digital with a real outline and font profile (`pdf.py` already handles
  all four cleanly), and the one file with no extractor at all — the `.djvu` of *Eros and
  Magic* — duplicates a title already extracted from its EPUB. The router needs no new
  code when a real blob shows up: `pdf.py` already computes the three signals that
  jointly mean "this is a blob" (`doc.get_toc()` empty, `_font_profile`'s `note_size`
  coming back `None`, `_pairing_holds` failing). Parked past that, too: the real blobs
  waiting to be transcribed aren't English, and every closed-vocabulary system built so
  far — `BIBLIOGRAPHY_TITLE`'s regex just above, `biblical.py`'s SBL sigla, `stephanus.py`
  — is English/Latin-corpus-shaped in ways a non-English blob would immediately expose.
  Worth revisiting once internationalization is underway, not before.
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
  weave.
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
  transliteration — Kokoro already pronounces it correctly as-is) and a multi-locator
  citation reusing the author bare
  ("Cassius Dio, 40.47, 23.26.1" only converts the first pair) — the same bare-reuse gap
  `citation_pairing.py` already measured, belonging to component 14's stateful register,
  not this system. The other edge case — `LOCATOR` capped at three dot/colon-separated
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
    "Ann." → "Annals", ...). Open-vocabulary, so the real table wants a per-document
    cheap-LLM draft sweep into a hand-editable map, additive and never-overwrite, reusing
    the `--lexicon-draft` *pattern* rather than the `Lexicon` class — **not built yet**.
    Currently holds one hand-verified seed entry, added for a real collision rather than
    drafted: "Num" for Plutarch's *Numa*, listed before biblical in `default_systems()` so
    it wins that tie. Expand minimally once the draft sweep lands — never resolve
    author/work identity (exactly where a cheap model hallucinates; the surrounding prose
    already supplies it).
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
    `classical.py`'s not-yet-built draft sweep is meant to read from — not yet wired to it.
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
    bug. Pure functions only so far, no CLI wiring and no LLM: that's `classical.py`'s
    still-pending draft sweep, which is meant to take a pairing like this and turn its
    siglum into a spoken expansion ("AJ" → "Jewish Antiquities") — a narrower, lower-risk
    LLM ask than guessing authorship, since the author side is already settled here.
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
  `redactions/`) hold whatever the last run produced. Each
  work dir contains a self-ignoring `.gitignore`.

## Commands

Everything routine is in the `justfile`:

- `just setup` — `uv sync` + install pre-commit hooks (once after cloning).
- `just lint` / `just fmt` / `just check` — ruff, same as the commit hooks run.
- `just run -o <dir>` — the whole chain to publish, default settings. The phases are
  verbs — `extract` (takes the document; a different one prompts before rebuilding from
  the top), `redact` (weaving + LLM flags), `recite` (`--variant/--voice/--speed/
  --sections`), `publish`, and `draft-lexicon` (drafts pronunciation entries, then stops
  for review). Verbs resolve their own dependencies: free phases run on demand, glossing
  never runs implicitly.

Use `uv` for all dependency management (`uv add`, `uv add --dev`), never pip. direnv
activates the venv; `.envrc` runs `uv sync` on entry.

## Conventions

- Canadian/British spelling in prose, docs, comments, and user-facing strings
  (colour, behaviour, artefact, -ise).
- If the user makes a spelling mistake or typo (in prose, identifiers, anywhere),
  point it out rather than propagating it into code.
- Ruff handles formatting and linting; config lives in `pyproject.toml`
  (line length 100, py313).
