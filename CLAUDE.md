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
  paragraphs torn by page breaks), a footnote weaver, `LanguageTagger` (splits
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
  calls through `GlossProvider` adapters in `redaction/providers.py` — `--provider
  anthropic` (default) or `openai`; local models run via the openai adapter with
  `--base-url` pointed at any OpenAI-compatible server (Ollama etc.; `--effort high` for
  gpt-oss). A faithfulness guard requires the returned body prose to reproduce the
  paragraph verbatim and in full; guarded or failed paragraphs fall back to the verbatim
  weave. Layers to come: maths dictation, and classical-citation speech — "Or. 32.9.6–10" is a unit system as hostile to TTS as mm²/s; possibly deterministic (the standard abbreviation lists), possibly lexicon + cheap LLM.
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
