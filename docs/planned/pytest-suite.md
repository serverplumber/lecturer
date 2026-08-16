# Spec: pytest suite for `lecturer/`

Status: not started, scoped only. No dependencies on other open specs (`docs/planned/`
is otherwise just `shared-canon.md`, unrelated). Written for handoff to a fresh
session — self-contained.

## Purpose

The `lecturer.py` → `lecturer/` package split (one cement `Controller` per verb under
`lecturer/controllers/`, plus `workdir.py`/`io.py`/`phases.py`/`arguments.py`/`main.py` —
see `CLAUDE.md`'s `## Layout`) was verified by hand: `uv run lecturer --help`, `--help`
for each of the 8 verbs, and two real dry runs (`estimate-gloss`, `extract`) against an
existing work dir. That's real verification but not repeatable — it doesn't run in CI
(there isn't one yet, but a test suite is a prerequisite either way) and won't catch a
regression the next time someone touches a controller or `phases.py`.

Scope of this spec, per the user's own split of the problem:

1. CLI-level tests replacing the by-hand `--help` sweep over the app and all 8 verbs,
   plus something standing in for the two real dry runs.
2. Unit tests for `lecturer.workdir.prepare_workdir` and `lecturer.workdir._reconcile`
   (`lecturer/workdir.py:34` and `:56`) — directory creation and the `working_text`
   symlink. The user called these out specifically as testable *now*.

Everything else — a real `redact`/`recite`/`publish` run through the full pipeline —
needs a real document, and the user hasn't found a copyleft-licensed one to use yet.
That's an explicit non-goal below, not an oversight.

## New test-suite infra needed (repo currently has none)

- No `tests/` dir, no `pytest` anywhere in `pyproject.toml` (`[dependency-groups] dev`
  currently only has `pre-commit`, `ruff`). Add `pytest>=8` to `dev`.
- `justfile` has `setup`/`lint`/`fmt`/`check`/`run` recipes but no `test` — add one
  (`test: uv run pytest`), same shape as the others.
- `tests/` layout: `tests/conftest.py`, `tests/test_workdir.py`, `tests/test_cli.py`,
  `tests/fixtures/` (see below). No test in this spec needs `redaction`/`extraction`/
  `recitation` internals mocked out — `extract` runs for real against a tiny fixture
  document; nothing here calls an LLM provider.

## Cement testing pattern (already researched, ready to use)

Cement ships `TestApp` (`cement.TestApp`, defined at
`cement/core/foundation.py:1760` in this repo's installed `cement` package) built
exactly for this: `Meta.argv = []` (nothing pulled from real `sys.argv`), and every
config/plugin/template file+dir list zeroed out (`core_system_config_files`,
`core_user_config_files`, `config_files`, `config_dirs`, plugin/template dirs — all
`[]`). A `TestApp`-based run therefore never reads the real
`~/.config/lecturer/lecturer.conf` or this repo's own gitignored `lecturer.conf`.
`exit_on_close = False` means `app.close()` — called automatically when the `with`
block exits — doesn't raise `SystemExit`, so `app.exit_code` can be asserted
afterward, in-process.

The canonical composition, taken directly from cement's own project-generator
template (`cement/cli/templates/generate/project/{{ label }}/main.py`):

```python
from cement import TestApp
from lecturer.main import Lecturer

class LecturerTest(TestApp, Lecturer):
    class Meta:
        label = "lecturer"
```

`TestApp` goes first in the MRO so its Meta wins the config/argv suppression.
`label` is re-pinned to `"lecturer"` because `TestApp.Meta.label` otherwise defaults
to a random per-instance string (`f"app-{rando()[:12]}"`), and the app's controller
labels/lookups expect the real one. Every CLI test then looks like:

```python
with LecturerTest(argv=["extract", "--help"]) as app:
    app.run()
    assert app.exit_code == 0
```

Fully in-process, no subprocess, no real `sys.argv` — fast enough to be a real pytest
suite instead of a shell-script smoke test.

## `tests/test_cli.py` — replaces the by-hand `--help` sweep + dry runs

1. **App-level `--help`**: `LecturerTest(argv=["--help"])`, assert `exit_code == 0`.
   Open question below on whether this actually stays in-process under `TestApp` or
   needs `pytest.raises(SystemExit)` instead — don't guess the assertion shape without
   spiking it first.
2. **Per-verb `--help`**, parametrized over the same 8 labels checked by hand: `extract`,
   `redact`, `estimate-gloss`, `recite`, `publish`, `draft-lexicon`, `draft-classical`,
   `promote-classical`. One parametrized test, not 8 copies — this is exactly what
   caught (and would catch again) an argument-tuple mis-import, e.g. a wrong
   `*_PROVIDER_ARGUMENTS` splat or a missing import in a `controllers/*.py` file.
3. **`extract` end-to-end**, against a small real fixture document (see "Fixture"
   below) copied into a `tmp_path`-based work dir. Assert: `exit_code == 0`,
   `sections/` contains the expected number of files, `working_text` is a symlink that
   resolves to the copied document. This replaces the by-hand `extract` dry run;
   `working_texts/temple_gates` (used for the by-hand verification) can't be reused
   here — see Non-goals.
4. **`estimate-gloss` is out of scope for this pass** — it needs a live Anthropic
   `count_tokens` call with no offline path (`redaction/estimate.py`'s own scoping),
   and this session's own attempt to smoke-test it live hit an auth failure unrelated
   to the code. Listed explicitly under Non-goals rather than silently dropped.
5. Every CLI test runs against pytest's built-in `tmp_path` fixture — no reason to pull
   in cement's own `fs.Tmp` (from its generated `conftest.py` template) when pytest
   already has an equivalent. Nothing in this suite should touch the real repo tree.

## `tests/test_workdir.py` — `prepare_workdir` and `_reconcile`

Direct unit tests of the two functions in `lecturer/workdir.py`, not exercised through
the CLI layer.

`prepare_workdir(document: Path, directory: Path) -> Path` (`workdir.py:34`):
- Creates `directory` (including parents) if missing.
- Writes `directory/.gitignore` containing exactly `"*\n"`.
- Copies `document` into `directory` under `document.name`; returns that copied path.
- Creates `directory/working_text` as a **relative** symlink to the copy — assert
  `.is_symlink()`, that the raw link target (`os.readlink`) is the bare filename (not
  an absolute path — this is what makes the work dir relocatable), and that
  `.resolve()` matches the copy.
- Idempotent for the same `document`/`directory`: a second call doesn't error and
  doesn't re-copy (assert the copy's mtime or content is unchanged) — this is what the
  real `copy.exists()` guard is for.
- Re-pointing: called a second time with a *different* document (same `directory`)
  updates the symlink to the new copy. `prepare_workdir` itself has no opinion on
  whether that's the right thing to do — that's `_reconcile`'s job, one layer up — so
  this test just confirms `prepare_workdir` does what it's told.

`_reconcile(app, document: Path, directory: Path) -> bool` (`workdir.py:56`):
- No existing `working_text` in `directory` → returns `True` immediately, no prompt.
  Needs only a minimal fake `app` (e.g. `types.SimpleNamespace(log=..., exit_code=0)`
  or a tiny hand-rolled stub) — this function only ever touches `app.log.error` and
  `app.exit_code`, and only on the refusal path, so a real cement `App`/`TestApp`
  isn't needed here (see open question below).
- Existing `working_text` resolves to the *same* document (same real path, or same
  name + matching sha256 digest for a copied-not-identical-path case) → returns
  `True`, no prompt.
- Existing `working_text` resolves to a genuinely *different* document → prompts via
  `input()`. Test both branches by monkeypatching `input` (`monkeypatch.setattr("builtins.input", ...)`
  or patching the name inside `lecturer.workdir`, whichever actually intercepts it —
  confirm against how `_reconcile` calls `input()`): `"y"`/`"yes"` → returns `True`,
  and `sections/`, `redactions/`, `audio/` under `directory` get removed if present;
  anything else (including `EOFError` from stdin, which the real function already
  catches and treats as an empty answer) → returns `False`, `app.exit_code` set to
  `1`, derived trees left untouched.
- No separate test needed for the digest helper (`_digest`, sha256, streamed in 1MiB
  blocks) beyond what the "same document, different path" `_reconcile` case above
  already exercises — it's simple enough not to warrant its own unit test unless it
  changes.

## Fixture: a tiny real document for `extract`

`extraction/` only handles `.epub` and `.pdf` (`extraction/__init__.py`'s
`_EXTRACTORS` dict) — there's no synthetic in-memory format, so the `extract` CLI
test needs a real minimal file of one of those types, small enough to commit. This is
new work: `working_texts/*` entries are real, gitignored, copyrighted source books —
not usable as committed fixtures (see Non-goals).

Recommend a hand-built minimal `.epub` — simpler to construct correctly than a
minimal `.pdf` (plain XHTML + OPF manifest, no binary/font complexity) — with 2-3
short sections and one footnote, using `epub:type="footnote"`/`"noteref"` markup
(`extraction/epub.py`'s primary path, ahead of its endnotes-chapter and reciprocal-
link fallbacks) so it exercises the extractor's main code path rather than a fallback
heuristic. Place it at `tests/fixtures/minimal.epub`, checked into git normally
(a few KB, no real copyrighted content — original or public-domain placeholder text).

## Non-goals

- Not using `working_texts/temple_gates` (or any other `working_texts/*` entry) as a
  test fixture. They're real copyrighted PDFs the user is running through the actual
  pipeline, gitignored for that reason — committing one, or pointing a test at a path
  that won't exist in a fresh checkout or CI anyway, is out of scope without the
  user's explicit say-so.
- Not testing `estimate-gloss`, `redact --llm`, `recite`, `publish`, `draft-lexicon`,
  or `draft-classical`'s actual behaviour beyond `--help` argument parsing this pass —
  each needs either a live Anthropic call, a real document substantial enough to be
  worth glossing/reciting, or both. Revisit once the user has a real copyleft document.
- Not building a mock/fake LLM provider to unblock `estimate-gloss`/`redact --llm`
  testing offline. Possible future work, but what a fake `count_tokens`/
  `messages.create` should even return to be meaningful is a real design question,
  not scoped here.
- Not adding pytest to `.pre-commit-config.yaml` in this pass — left as an open
  question below, not decided either way.

## Open questions for whoever implements this

1. Does app-level `--help` actually stay in-process under `TestApp`, or does cement's
   help handling call `sys.exit` regardless of `exit_on_close`? Spike this before
   locking in the assertion shape for `tests/test_cli.py` item 1 — don't guess.
2. Should pytest gate `.pre-commit-config.yaml`, or stay manual/CI-only? Leaning
   manual/CI-only (commit-time hooks should stay fast; this suite may grow past pure
   `--help` checks later) but not decided.
3. Exact construction of `tests/fixtures/minimal.epub` — hand-author the XHTML/OPF
   directly, or write a small throwaway script (e.g. using `ebooklib`) to generate it
   once and commit the output? Either way, check it against `extraction/epub.py`'s
   actual parsing expectations first, so the fixture round-trips through the real
   extractor rather than a format the tests merely assume works.
4. Whether `_reconcile`'s test needs a real cement `App`/`TestApp` at all, or whether
   the minimal stub described above is sufficient — depends on whether any other
   `_reconcile` caller (currently only `lecturer/controllers/extract.py`) ever needs
   something a stub can't provide.
5. Whether to add a `[tool.pytest.ini_options]` block to `pyproject.toml` now (test
   paths, markers), or let pytest's defaults suffice until the suite is big enough to
   need configuring.
