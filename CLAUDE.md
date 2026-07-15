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
  language switches are left for the LLM), and `Cantillator` (points overlong comma-free
  stretches with breath commas at clause boundaries — unspoken, but the TTS breathes
  there instead of improvising a pause mid-phrase). The weaver is `NoteDropper` by default (read
  the book plain — anchors stripped, no note spoken), `Glossator` with `--llm` (one call
  per annotated paragraph: substantive notes respoken as asides, bare citations dropped;
  write-through cache in the work dir's `gloss_cache.json`), or `FootnoteWeaver` with
  `--verbatim-notes` (every note verbatim at its anchor — inspection mode). The glossator
  calls through `GlossProvider` adapters in `redaction/providers.py` — `--provider
  anthropic` (default) or `openai`; local models run via the openai adapter with
  `--base-url` pointed at any OpenAI-compatible server (Ollama etc.; `--effort high` for
  gpt-oss). A faithfulness guard requires the returned body prose to reproduce the
  paragraph verbatim and in full; guarded or failed paragraphs fall back to the verbatim
  weave. A maths-dictation layer and LLM language tagging are to come.
- `recitation/` — speaks the script (`--speak`): `Reciter` strategy protocol, one WAV per
  section into the work dir's `audio/`. `KokoroReciter` runs Kokoro-82M via kokoro-onnx
  (pure wheels, CPU ~4× realtime; model fetched once into `~/.cache/lecturer`). Text is
  chunked at sentence boundaries under Kokoro's 510-phoneme batch limit (mid-sentence
  splices sound like random commas). `--voice` takes a name or a weighted blend of style
  vectors (default `af_kore+af_aoede`; af_heart/af_bella glottal-pause before
  vowel-initial words — measure, don't trust ears alone). Non-English utterances are
  skipped and counted.
- `texts/` — source monographs (gitignored; copyrighted material).
- Working directories (e.g. `./eros_magic`) are created by the CLI wherever `-o` points
  (`-d` belongs to cement's `--debug`). Each contains a copy of the source document, a
  `working_text` symlink to it, a `sections/` directory of extracted text + footnotes
  files, a `redactions/` directory of manner-tagged utterances (plus `.unwoven.txt`
  leftovers), later intermediary pipeline files, and eventually the final audio. Each
  work dir contains a self-ignoring `.gitignore`.

## Commands

Everything routine is in the `justfile`:

- `just setup` — `uv sync` + install pre-commit hooks (once after cloning).
- `just lint` / `just fmt` / `just check` — ruff, same as the commit hooks run.
- `just run -d <dir> <document>` — run the CLI.

Use `uv` for all dependency management (`uv add`, `uv add --dev`), never pip. direnv
activates the venv; `.envrc` runs `uv sync` on entry.

## Conventions

- Canadian/British spelling in prose, docs, comments, and user-facing strings
  (colour, behaviour, artefact, -ise).
- If the user makes a spelling mistake or typo (in prose, identifiers, anywhere),
  point it out rather than propagating it into code.
- Ruff handles formatting and linting; config lives in `pyproject.toml`
  (line length 100, py313).
