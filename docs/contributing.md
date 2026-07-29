# Contributing

## First run

```sh
just setup   # uv sync, install commit hooks, provision lecturer.conf
just check   # lint + format, same as the commit hooks
```

`just setup` copies `lecturer.conf.example` to `lecturer.conf` the first time only — it never
overwrites an existing one, so it's safe to edit `lecturer.conf` afterward without `just setup`
clobbering your changes on a later run.

## `lecturer.conf`

`lecturer.conf` (repo-root, gitignored — personal to this checkout, never committed) is a dev
override of Cement's own `~/.config/lecturer/lecturer.conf`. Its one setting so far,
`elocution_dir`, is where `redaction/elocution/canon.py`'s shared sigla canon
(`classical.toml`) lives — defaulted here to `./elocution/` (itself self-ignoring, like a work
dir) so a dev checkout accumulates its own canon separately from any copy of `lecturer`
installed for real on the same machine. Delete `lecturer.conf` to fall back to the installed
default, or point `elocution_dir` wherever you like — `LECTURER_ELOCUTION_DIR` in the
environment works too, for a one-off run.

## LLM features need credentials

Everything free (`extract`, `redact`, `recite`, `publish`) needs nothing beyond `uv sync`. The
opt-in, billed layers — `redact --llm` (the glossator), `--interpret`, `draft-lexicon`,
`draft-classical` — need either `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` set, or (Anthropic only)
`ant auth login`. `--provider openai --base-url http://localhost:.../v1` points any of them at a
local OpenAI-compatible server instead (Ollama, llama.cpp, ...) — see `redaction/providers.py`.

## Where the design reasoning lives

`CLAUDE.md` is the single source of truth for *why* — every non-obvious extraction, redaction,
and recitation decision is documented there, alongside the corpus it was verified against. Read
it before touching a module; update it in the same commit as the change it explains, the way
every prior commit in this repo's history does.
