# Lecturer

Text-to-voice pipeline that turns monographs into audiobooks sounding like the author
lecturing from their own book. Planned hard part: extracting footnotes and having an LLM
weave them into the text as spoken digressions. TTS will start with
[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M).

## Layout

- `lecturer.py` — the cement-based CLI: sets up the work directory and runs extraction.
- `extraction/` — strategy-pattern extractors (epub, pdf) producing `Section`s of running
  text with `[^ref]`-anchored footnotes.
- `texts/` — source monographs (gitignored; copyrighted material).
- Working directories (e.g. `./eros_magic`) are created by the CLI wherever `-o` points
  (`-d` belongs to cement's `--debug`). Each contains a copy of the source document, a
  `working_text` symlink to it, a `sections/` directory of extracted text + footnotes
  files, later intermediary pipeline files, and eventually the final audio. Each work dir
  contains a self-ignoring `.gitignore`.

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
