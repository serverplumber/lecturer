# Lecturer

Text-to-voice pipeline that turns monographs into audiobooks sounding like the author
lecturing from their own book. Planned hard part: extracting footnotes and having an LLM
weave them into the text as spoken digressions. TTS will start with
[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M).

## Layout

- `lecturer.py` — the cement-based CLI: sets up the work directory and runs extraction.
- `extraction/` — strategy-pattern extractors (epub, pdf) producing `Section`s of running
  text with `[^ref]`-anchored footnotes.
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
  free. Sigla that are identical strings across systems ("Num" for Numbers vs.
  Plutarch's *Numa*) can't be told apart by length; those tie-break by system priority —
  earlier systems in `default_systems()` win. A real ambiguous case (a corpus citing both
  under the bare siglum) is the one thing this can't resolve — that needs context, which
  is exactly the boundary the LLM-drafted systems below are meant to live behind, not
  cross.
  - `biblical.py` — the SBL Handbook's book sigla: closed, universal, hardcoded, no draft
    needed.
  - `classical.py` — the heterogeneous Latin author-work abbreviations ("Or." → "Oration",
    "Ann." → "Annals", ...). Open-vocabulary, so the real table wants a per-document
    cheap-LLM draft sweep into a hand-editable map, additive and never-overwrite, reusing
    the `--lexicon-draft` *pattern* rather than the `Lexicon` class — **not built yet**.
    Currently holds one hand-verified seed entry, added for a real collision rather than
    drafted: "Num" for Plutarch's *Numa*, listed before biblical in `default_systems()` so
    it wins that tie. Expand minimally once the draft sweep lands — never resolve
    author/work identity (exactly where a cheap model hallucinates; the surrounding prose
    already supplies it).
  - **Still to come**: Bekker numbering, Diels-Kranz, and Stephanus pagination are further
    open-vocabulary systems of the same shape once they show up outside footnotes. Units
    (SAE vs SI collisions) are parked until citation dictation's systems are mature enough
    to tell whether the same machinery generalises or the two need separate treatment.
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
  it to a phone and Books treats it right). `--voice` takes a name or a weighted
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
