"""Turn monographs into audiobooks read as though by the author.

The pipeline is four phases, each a verb reading the previous phase's
files from the working directory: ``extract`` (document -> sections/),
``redact`` (working_text -> redactions/<variant>/), ``recite``
(redactions -> audio/<variant>/), and ``publish`` (audio -> Opus + an
M3U playlist). Verbs resolve their own dependencies — free phases run
on demand, billed ones never implicitly. ``draft-lexicon`` is a
checkpoint: it drafts pronunciation entries and stops so they can be
validated before recite. Run bare with just ``-o`` and the whole chain
runs to publish with default settings.
"""

import hashlib
import re
import shutil
from collections import Counter
from pathlib import Path

from cement import App, Controller

from extraction import Extraction, UnsupportedFormatError, extract, read_metadata
from redaction import (
    DEFAULT_MODELS,
    PROVIDERS,
    TAGGING_MODELS,
    FootnoteWeaver,
    Glossator,
    Manner,
    NearMiss,
    ProviderError,
    Script,
    ScriptSection,
    TongueInterpreter,
    Utterance,
    ensure_synopsis,
    estimate_gloss_cost,
    redact,
    render_estimate,
)
from redaction.mend import SeamMender
from redaction.usage import append_usage, new_record

WORKING_TEXT = "working_text"

_OUTPUT_ARGUMENT = (
    ["-o", "--output"],
    {
        "help": "the working directory (default: derived from the document name)",
        "dest": "output",
        "metavar": "DIR",
    },
)

_VARIANT_ARGUMENT = (
    ["--variant"],
    {
        "help": "which weaving to work from: book, glossed, or verbatim",
        "dest": "variant",
        "metavar": "NAME",
        "default": "book",
    },
)

_SECTIONS_ARGUMENT = (
    ["--sections"],
    {
        "help": "only sections whose title matches this regex (default: everything "
        "except apparatus — front matter, bibliography, index, ...)",
        "dest": "sections",
        "metavar": "REGEX",
    },
)

_PROVIDER_ARGUMENTS = [
    (
        ["--provider"],
        {
            "help": "LLM provider",
            "dest": "provider",
            "choices": sorted(PROVIDERS),
            "default": "anthropic",
        },
    ),
    (
        ["--model"],
        {
            "help": "model override (defaults per provider and task)",
            "dest": "model",
            "metavar": "MODEL",
        },
    ),
    (
        ["--base-url"],
        {
            "help": "OpenAI-compatible endpoint, for local models "
            "(e.g. http://localhost:11434/v1 for Ollama)",
            "dest": "base_url",
            "metavar": "URL",
        },
    ),
    (
        ["--effort"],
        {
            "help": "reasoning effort (low/medium/high; local reasoning models "
            "like gpt-oss need high)",
            "dest": "effort",
            "metavar": "LEVEL",
        },
    ),
]


def slugify(text: str) -> str:
    """Reduce a document name to a filesystem-friendly directory name."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "document"


def section_stem(index: int, title: str) -> str:
    """The filename stem shared by a section's pipeline files."""
    return f"{index:02d}_{slugify(title)[:48].rstrip('_')}"


def _digest(path: Path) -> str:
    """Content hash of a document, streamed."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def prepare_workdir(document: Path, directory: Path) -> Path:
    """Create the working directory and link the source document into it.

    The document is copied into the directory and ``working_text`` is a
    relative symlink to that copy, so later pipeline stages have a stable
    name to read regardless of the original filename. The directory gets a
    self-ignoring ``.gitignore`` since generated artefacts don't belong in
    version control. Returns the path of the copied document.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".gitignore").write_text("*\n")

    copy = directory / document.name
    if not copy.exists():
        shutil.copy2(document, copy)

    link = directory / WORKING_TEXT
    link.unlink(missing_ok=True)
    link.symlink_to(copy.name)
    return copy


def write_sections(extraction: Extraction, directory: Path) -> Path:
    """Write each section to ``sections/NN_title.txt`` plus a footnotes file."""
    sections_dir = directory / "sections"
    sections_dir.mkdir(exist_ok=True)
    for index, section in enumerate(extraction.sections, start=1):
        stem = section_stem(index, section.title)
        (sections_dir / f"{stem}.txt").write_text(section.text + "\n")
        if section.footnotes:
            notes = "\n".join(f"[^{note.ref}]: {note.text}" for note in section.footnotes)
            (sections_dir / f"{stem}.footnotes.txt").write_text(notes + "\n")
    return sections_dir


_TAG = re.compile(r"^\[(\w+)(?: lang=([\w-]+))?\]$")


def write_redactions(script: Script, directory: Path, variant: str) -> Path:
    """Write each redacted section to ``redactions/<variant>/NN_title.txt``.

    Weaving variants fork the tree, mirroring ``audio/``. Each file opens
    with a ``[section] title`` header so later phases can read the script
    back; utterances follow, separated by blank lines, each under a
    ``[manner]`` or ``[manner lang=xx]`` tag line. Notes no layer wove in
    are kept next door in ``.unwoven.txt`` files.
    """
    redactions_dir = directory / "redactions" / variant
    redactions_dir.mkdir(parents=True, exist_ok=True)
    for index, section in enumerate(script.sections, start=1):
        stem = section_stem(index, section.title)
        rendered = "\n\n".join(
            f"[{utterance.manner}{'' if utterance.lang == 'en' else f' lang={utterance.lang}'}]"
            f"\n{utterance.text}"
            for utterance in section.utterances
        )
        (redactions_dir / f"{stem}.txt").write_text(f"[section] {section.title}\n\n{rendered}\n")
        if section.footnotes:
            notes = "\n".join(f"[^{note.ref}]: {note.text}" for note in section.footnotes)
            (redactions_dir / f"{stem}.unwoven.txt").write_text(notes + "\n")
    return redactions_dir


def write_review(near_misses: list[NearMiss], directory: Path, variant: str) -> Path | None:
    """Write ``redactions/<variant>/review.md``: citations Elocutor couldn't convert.

    Not a diagnosis — each entry is a known siglum sitting next to
    something locator-shaped the grammar didn't accept, with enough
    surrounding text for a human to see why and fix it by hand (in the
    source text, or by extending the matching system in
    ``redaction/elocution/``). Named ``.md``, not ``.txt``, so
    ``read_redactions``'s glob never mistakes it for a section. Always
    overwritten, even to "nothing to review" — never deleted, so a run
    invoked with a narrower ``systems`` set (or one that errors early)
    can't make an existing review vanish out from under someone reading it.
    """
    review_path = directory / "redactions" / variant / "review.md"
    if not near_misses:
        review_path.write_text(
            f"# Citation review — {variant}\n\n"
            "Nothing to review — every citation-shaped span converted.\n"
        )
        return None
    lines = [
        f"# Citation review — {variant}\n",
        f"{len(near_misses)} citation-shaped span(s) Elocutor didn't convert. Not a "
        "diagnosis: a known siglum sits next to something locator-ish (a missing "
        "space, OCR noise, a shape the system doesn't cover...) that the grammar "
        "didn't accept. Check the context below and fix by hand if it's worth it.\n",
    ]
    for miss in near_misses:
        lines.append(f'- **{miss.section}**, {miss.location} — `[{miss.system}]` "{miss.siglum}"')
        lines.append(f"  > {miss.context}")
    review_path.write_text("\n".join(lines) + "\n")
    return review_path


def read_redactions(directory: Path, variant: str) -> Script | None:
    """Read a redacted script back from ``redactions/<variant>/``.

    The inverse of :func:`write_redactions` — this file tree is the
    interface between the redaction and recitation phases. Returns
    ``None`` when the variant has not been redacted yet.
    """
    redactions_dir = directory / "redactions" / variant
    files = sorted(
        path for path in redactions_dir.glob("*.txt") if not path.name.endswith(".unwoven.txt")
    )
    if not files:
        return None
    sections = []
    for path in files:
        blocks = path.read_text().split("\n\n")
        if blocks[0].startswith("[section]"):
            title = blocks[0].removeprefix("[section]").strip()
        else:
            title = path.stem  # pre-header files: slugified but serviceable
        utterances = []
        for block in blocks[1:]:
            tag, _, text = block.partition("\n")
            match = _TAG.match(tag.strip())
            if match is None or not text.strip():
                continue
            utterances.append(
                Utterance(
                    text=text.strip(),
                    manner=Manner(match.group(1)),
                    lang=match.group(2) or "en",
                )
            )
        sections.append(ScriptSection(title=title, utterances=utterances))
    return Script(sections=sections)


class Base(Controller):
    class Meta:
        label = "base"
        description = (
            "Turn monographs into audiobooks. Bare `lecturer -o DIR` runs the "
            "whole chain to publish with default settings; the verbs run one "
            "phase each, reading the previous phase's files from the work dir."
        )
        arguments = [_OUTPUT_ARGUMENT]

    def _default(self):
        directory = Path(self.app.pargs.output) if self.app.pargs.output else None
        if directory is None or not (directory / WORKING_TEXT).exists():
            self.app.args.print_help()
            if directory is not None:
                self.app.log.error(
                    f"no {WORKING_TEXT} in {directory}: run `lecturer extract -o "
                    f"{directory} <document>` first"
                )
                self.app.exit_code = 1
            return
        extraction = _extract_phase(self.app, directory, None)
        if extraction is None:
            return
        script = _redact_phase(self.app, directory, extraction, weaver=None, interpreter=None)
        _recite_phase(self.app, directory, script, "book", skip=_apparatus_skip(None))
        _publish_phase(self.app, directory, script, "book", skip=_apparatus_skip(None))


class Extract(Controller):
    class Meta:
        label = "extract"
        stacked_on = "base"
        stacked_type = "nested"
        help = "set up the work dir and extract sections/ from the document"
        description = "Set up the working directory and extract the document into sections/."
        arguments = [
            _OUTPUT_ARGUMENT,
            (
                ["document"],
                {
                    "help": "path to the monograph (epub, pdf, ...); optional when "
                    "the work dir already has a working_text",
                    "nargs": "?",
                },
            ),
        ]

    def _default(self):
        document = Path(self.app.pargs.document) if self.app.pargs.document else None
        if document is None:
            if self.app.pargs.output:
                link = Path(self.app.pargs.output) / WORKING_TEXT
                if link.exists():
                    document = link.resolve()
            if document is None:
                self.app.args.print_help()
                return
        elif not document.is_file():
            self.app.log.error(f"no such document: {document}")
            self.app.exit_code = 1
            return
        directory = Path(self.app.pargs.output or slugify(document.stem))
        if not _reconcile(self.app, document, directory):
            return
        _extract_phase(self.app, directory, document)


class Redact(Controller):
    class Meta:
        label = "redact"
        stacked_on = "base"
        stacked_type = "nested"
        help = "rework the extraction into redactions/<variant>/"
        description = (
            "Rework the extracted text, layer by layer, into a spoken script. "
            "The weaver decides the variant: notes dropped (book, the default), "
            "woven by the LLM glossator (--llm -> glossed), or verbatim "
            "(--verbatim-notes -> verbatim)."
        )
        arguments = [
            _OUTPUT_ARGUMENT,
            (
                ["--llm"],
                {
                    "help": "weave footnotes in as spoken digressions with the LLM "
                    "glossator (billed API calls; cached in the work dir)",
                    "action": "store_true",
                    "dest": "llm",
                },
            ),
            (
                ["--verbatim-notes"],
                {
                    "help": "weave every footnote in verbatim at its anchor "
                    "(inspection mode; unpleasant listening)",
                    "action": "store_true",
                    "dest": "verbatim_notes",
                },
            ),
            (
                ["--interpret"],
                {
                    "help": "tag Latin-alphabet language switches (loanwords, Latin "
                    "phrases, names) with the LLM (cheap model by default; cached)",
                    "action": "store_true",
                    "dest": "interpret",
                },
            ),
            *_PROVIDER_ARGUMENTS,
        ]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        extraction = _extract_phase(self.app, directory, None)
        if extraction is None:
            return
        weaver = None
        interpreter = None
        if self.app.pargs.verbatim_notes:
            weaver = FootnoteWeaver()
        try:
            if self.app.pargs.llm:
                provider = _provider(self.app, DEFAULT_MODELS)
                synopsis = ensure_synopsis(
                    extraction, provider, directory / "synopsis.txt", log=self.app.log.info
                )
                weaver = Glossator(
                    provider=provider,
                    cache_path=directory / "gloss_cache.json",
                    synopsis=synopsis,
                    log=self.app.log.info,
                )
                stale = weaver.stale_cache_entries(
                    SeamMender().redact(Script.from_extraction(extraction))
                )
                if stale:
                    self.app.log.warning(
                        f"{stale} of {weaver.cache_size} cached gloss(es) in gloss_cache.json "
                        f"don't match any paragraph under {provider.label} — most likely "
                        "glossed under a different model or prompt; those paragraphs will be "
                        "re-sent and re-billed this run (run `estimate-gloss` first to see the "
                        "real cost)"
                    )
            if self.app.pargs.interpret:
                interpreter = TongueInterpreter(
                    provider=_provider(self.app, TAGGING_MODELS),
                    cache_path=directory / "tongue_cache.json",
                    log=self.app.log.info,
                )
        except ProviderError as error:
            self.app.log.error(str(error))
            self.app.exit_code = 1
            return
        _redact_phase(self.app, directory, extraction, weaver=weaver, interpreter=interpreter)


class EstimateGloss(Controller):
    class Meta:
        label = "estimate-gloss"
        stacked_on = "base"
        stacked_type = "nested"
        help = "print a real cost estimate for redact --llm, without spending anything"
        description = (
            "Compute and print what the remaining redact --llm work would cost, using "
            "count_tokens (free) for input and this book's own gloss_usage.jsonl call "
            "history for output. Spends nothing. Anthropic only for now."
        )
        arguments = [_OUTPUT_ARGUMENT, *_PROVIDER_ARGUMENTS]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        if self.app.pargs.provider != "anthropic":
            self.app.log.error(
                "estimate-gloss only supports --provider anthropic for now "
                "(no free token-counting endpoint for OpenAI)"
            )
            self.app.exit_code = 1
            return
        extraction = _extract_phase(self.app, directory, None)
        if extraction is None:
            return
        try:
            provider = _provider(self.app, DEFAULT_MODELS)
        except ProviderError as error:
            self.app.log.error(str(error))
            self.app.exit_code = 1
            return
        synopsis_path = directory / "synopsis.txt"
        synopsis = synopsis_path.read_text().strip() if synopsis_path.exists() else None
        estimate = estimate_gloss_cost(extraction, provider, directory, synopsis)
        print(render_estimate(estimate))


class Recite(Controller):
    class Meta:
        label = "recite"
        stacked_on = "base"
        stacked_type = "nested"
        help = "speak redactions/<variant>/ into audio/<variant>/"
        description = (
            "Synthesise the redacted script into one WAV per section with Kokoro. "
            "Unchanged sections (by content signature) are kept; apparatus "
            "sections are skipped unless --sections says otherwise."
        )
        arguments = [
            _OUTPUT_ARGUMENT,
            _VARIANT_ARGUMENT,
            _SECTIONS_ARGUMENT,
            (
                ["--voice"],
                {
                    "help": "Kokoro voice, or a blend like af_kore+af_aoede "
                    "(weighted: af_kore:2+af_aoede:1)",
                    "dest": "voice",
                    "metavar": "VOICE",
                    "default": "af_kore+af_aoede",
                },
            ),
            (
                ["--speed"],
                {
                    "help": "speech rate multiplier (0.5-2.0)",
                    "dest": "speed",
                    "metavar": "FACTOR",
                    "type": float,
                    "default": 1.0,
                },
            ),
        ]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        script = _ensure_redactions(self.app, directory)
        if script is None:
            return
        _recite_phase(
            self.app,
            directory,
            script,
            self.app.pargs.variant,
            skip=_apparatus_skip(self.app.pargs.sections),
            voice=self.app.pargs.voice,
            speed=self.app.pargs.speed,
        )


class Publish(Controller):
    class Meta:
        label = "publish"
        stacked_on = "base"
        stacked_type = "nested"
        help = "bind audio/<variant>/ into Opus plus an M3U playlist"
        description = (
            "Convert recited WAVs to Opus (~10x smaller) and write a playlist "
            "with section titles and durations, in reading order."
        )
        arguments = [_OUTPUT_ARGUMENT, _VARIANT_ARGUMENT, _SECTIONS_ARGUMENT]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        script = _ensure_redactions(self.app, directory)
        if script is None:
            return
        variant = self.app.pargs.variant
        skip = _apparatus_skip(self.app.pargs.sections)
        if not any((directory / "audio" / variant).glob("*.wav")):
            self.app.log.info(f"no {variant} audio yet; reciting first (default voice)")
            _recite_phase(self.app, directory, script, variant, skip=skip)
        _publish_phase(self.app, directory, script, variant, skip=skip)


class DraftLexicon(Controller):
    class Meta:
        label = "draft-lexicon"
        stacked_on = "base"
        stacked_type = "nested"
        help = "draft lexicon.json pronunciation entries, then stop for review"
        description = (
            "Sweep the redacted script for pronunciation risks with a cheap "
            "model and merge draft entries into the work dir's lexicon.json — "
            "then stop: validate the drafts by ear before recite/publish. "
            "Existing entries are never overwritten. Redacts first if needed."
        )
        arguments = [_OUTPUT_ARGUMENT, _VARIANT_ARGUMENT, *_PROVIDER_ARGUMENTS]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        script = _ensure_redactions(self.app, directory)
        if script is None:
            return
        from recitation import draft

        try:
            draft(
                script,
                _provider(self.app, TAGGING_MODELS),
                directory / "lexicon.json",
                log=self.app.log.info,
            )
        except ProviderError as error:
            self.app.log.error(f"lexicon draft failed: {error}")
            self.app.exit_code = 1


class DraftClassical(Controller):
    class Meta:
        label = "draft-classical"
        stacked_on = "base"
        stacked_type = "nested"
        help = "draft classical_sigla.toml (tier 2) author-work sigla, then stop for review"
        description = (
            "Sweep this document's own bibliography and footnotes (via "
            "citation_pairing.py's pair_sigla) for author-work abbreviations no "
            "system already resolves, and ask a model for each one's spoken title "
            "— then stop: check the drafts by eye (redact picks them up "
            "automatically from here on), and run promote-classical once you trust "
            "one enough for every book. Defaults to DEFAULT_MODELS, not the cheap "
            "tagging tier: classical-title expansion needs real classical "
            "knowledge a small model doesn't reliably have. Existing entries are "
            "never overwritten."
        )
        arguments = [_OUTPUT_ARGUMENT, *_PROVIDER_ARGUMENTS]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        extraction = _extract_phase(self.app, directory, None)
        if extraction is None:
            return
        from redaction.elocution.draft import draft

        try:
            draft(
                extraction,
                _provider(self.app, DEFAULT_MODELS),
                _elocution_dir(self.app),
                directory,
                log=self.app.log.info,
            )
        except ProviderError as error:
            self.app.log.error(f"classical draft failed: {error}")
            self.app.exit_code = 1


class PromoteClassical(Controller):
    class Meta:
        label = "promote-classical"
        stacked_on = "base"
        stacked_type = "nested"
        help = "merge this document's classical_sigla.toml (tier 2) into the shared canon"
        description = (
            "Copy every entry in this work dir's classical_sigla.toml (this document's "
            "own author-work sigla) into the shared, hand-curated canon at "
            "elocution_dir/classical_sigla.toml — used by every book from here on. "
            "Additive only: a siglum the canon already has is left untouched. "
            "Run it once you've checked a hand-added or drafted entry by ear."
        )
        arguments = [_OUTPUT_ARGUMENT]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        from redaction.elocution.canon import promote, tier1_path

        elocution_dir = _elocution_dir(self.app)
        added = promote(elocution_dir, directory, "classical")
        if added:
            self.app.log.info(
                f"promoted {len(added)} entr{'y' if len(added) == 1 else 'ies'} into "
                f"{tier1_path(elocution_dir, 'classical')}: {', '.join(sorted(added))}"
            )
        else:
            self.app.log.info("nothing new to promote")


def _existing_workdir(app) -> Path | None:
    """The work dir a phase verb operates on; errors if it isn't one yet."""
    if not app.pargs.output:
        app.args.print_help()
        return None
    directory = Path(app.pargs.output)
    if not (directory / WORKING_TEXT).exists():
        app.log.error(
            f"no {WORKING_TEXT} in {directory}: run `lecturer extract -o "
            f"{directory} <document>` first"
        )
        app.exit_code = 1
        return None
    return directory


def _ensure_redactions(app, directory: Path) -> Script | None:
    """The variant's script, redacting first when it doesn't exist yet.

    Free deterministic variants (book, verbatim) are built on demand — the
    deps do their magic. The glossed variant costs tokens and judgement,
    so it is never built implicitly: run ``redact --llm`` yourself.
    """
    variant = getattr(app.pargs, "variant", "book")
    script = read_redactions(directory, variant)
    if script is not None:
        return script
    if variant == "glossed":
        app.log.error(
            f"no glossed redactions in {directory}, and glossing is never "
            f"implicit (billed): run `lecturer redact -o {directory} --llm` first"
        )
        app.exit_code = 1
        return None
    app.log.info(f"no {variant} redactions yet; redacting first")
    extraction = _extract_phase(app, directory, None)
    if extraction is None:
        return None
    weaver = FootnoteWeaver() if variant == "verbatim" else None
    return _redact_phase(app, directory, extraction, weaver=weaver, interpreter=None)


def _reconcile(app, document: Path, directory: Path) -> bool:
    """Guard the work dir's identity: one directory, one book.

    A different document than the one behind ``working_text`` means taking
    the whole process from the top — confirmed by the user, then the
    derived trees are cleared. The document copy, caches, and the
    hand-edited lexicon survive only for the same book.
    """
    link = directory / WORKING_TEXT
    if not link.exists():
        return True
    existing = link.resolve()
    if document.resolve() == existing or (
        document.name == existing.name and _digest(document) == _digest(existing)
    ):
        return True
    print(
        f"{directory} currently holds '{existing.name}';\n"
        f"replacing it with '{document.name}' rebuilds everything: "
        "sections/, redactions/, and audio/ will be removed\n"
        "(caches and lexicon.json are kept — delete them yourself if they "
        "belong to the old book)."
    )
    try:
        answer = input("take it from the top? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() not in ("y", "yes"):
        app.log.error("keeping the existing working text; nothing done")
        app.exit_code = 1
        return False
    for derived in ("sections", "redactions", "audio"):
        shutil.rmtree(directory / derived, ignore_errors=True)
    existing.unlink(missing_ok=True)
    link.unlink(missing_ok=True)
    return True


def _provider(app, defaults):
    return PROVIDERS[app.pargs.provider](
        model=app.pargs.model or defaults[app.pargs.provider],
        base_url=app.pargs.base_url,
        effort=app.pargs.effort,
    )


_DEFAULT_ELOCUTION_DIR = Path.home() / ".config" / "lecturer" / "elocution"


def _elocution_dir(app) -> Path:
    """Where the shared sigla canon (``redaction.elocution.canon``'s tier 1) lives.

    Ordinary Cement config precedence: the ``[lecturer] elocution_dir``
    setting in ``lecturer.conf`` (any of Cement's usual locations), or a
    ``LECTURER_ELOCUTION_DIR`` environment variable, with a plain XDG-style
    default so a real install needs no setup at all. ``main()`` layers a
    repo-local, gitignored ``lecturer.conf`` on top of all of that when one
    exists — see there for why: it lets a dev checkout and an installed copy
    on the same machine each keep their own canon rather than silently
    sharing one through ``~/.config/lecturer/lecturer.conf``.
    """
    value = app.config.get("lecturer", "elocution_dir", fallback=None)
    return Path(value).expanduser() if value else _DEFAULT_ELOCUTION_DIR


def _apparatus_skip(sections: str | None):
    from recitation import APPARATUS

    if sections:
        wanted = re.compile(sections, re.IGNORECASE)
        return lambda title: not wanted.search(title)
    return lambda title: bool(APPARATUS.search(title))


def _extract_phase(app, directory: Path, document: Path | None) -> Extraction | None:
    document = document or (directory / WORKING_TEXT).resolve()
    copy = prepare_workdir(document, directory)
    app.log.info(f"working directory ready: {directory}/{WORKING_TEXT}")
    try:
        extraction = extract(copy)
    except UnsupportedFormatError as error:
        app.log.error(f"{error}; nothing extracted")
        app.exit_code = 1
        return None
    sections_dir = write_sections(extraction, directory)
    notes = sum(len(section.footnotes) for section in extraction.sections)
    app.log.info(
        f"extracted {len(extraction.sections)} sections ({notes} footnotes) into {sections_dir}"
    )
    return extraction


def _redact_phase(app, directory: Path, extraction: Extraction, *, weaver, interpreter) -> Script:
    if isinstance(weaver, Glossator):
        variant = "glossed"
    elif isinstance(weaver, FootnoteWeaver):
        variant = "verbatim"
    else:
        variant = "book"
    try:
        script, near_misses = redact(
            extraction,
            weaver=weaver,
            interpreter=interpreter,
            directory=directory,
            elocution_dir=_elocution_dir(app),
        )
    except ProviderError as error:
        app.log.error(f"redaction failed: {error} (finished paragraphs are cached)")
        app.exit_code = 1
        raise SystemExit(app.exit_code) from error
    redactions_dir = write_redactions(script, directory, variant)
    review_path = write_review(near_misses, directory, variant)
    if review_path is not None:
        app.log.warning(f"{len(near_misses)} unconverted citation(s) — see {review_path}")
    notes = sum(len(section.footnotes) for section in extraction.sections)
    unwoven = sum(len(section.footnotes) for section in script.sections)
    spoken_notes = (
        f"{notes - unwoven} digressions woven, {unwoven} notes left unwoven"
        if weaver is not None
        else f"all {notes} notes dropped"
    )
    tongues = Counter(
        utterance.lang
        for section in script.sections
        for utterance in section.utterances
        if utterance.lang != "en"
    )
    spoken = ", ".join(f"{lang} ({count})" for lang, count in tongues.most_common())
    app.log.info(
        f"redacted into {redactions_dir}: {spoken_notes}"
        + (f", other tongues: {spoken}" if tongues else "")
    )
    for name, layer in (("glossator", weaver), ("interpreter", interpreter)):
        if isinstance(layer, Glossator | TongueInterpreter):
            provider = layer.provider
            if provider.input_tokens or provider.output_tokens:
                app.log.info(
                    f"{name} used {provider.input_tokens} input + "
                    f"{provider.output_tokens} output tokens on {provider.label}"
                )
        if isinstance(layer, Glossator) and layer.calls:
            # Excludes whatever ensure_synopsis spent on this same provider
            # instance before the Glossator existed (gloss_input_tokens/
            # gloss_output_tokens baseline against the provider's counters at
            # construction time) — a per-paragraph average built from this
            # record would otherwise be skewed by one large one-off call.
            append_usage(
                directory / "gloss_usage.jsonl",
                new_record(
                    provider_label=layer.provider.label,
                    input_tokens=layer.gloss_input_tokens,
                    output_tokens=layer.gloss_output_tokens,
                    calls=layer.calls,
                    truncated=layer.gloss_truncated,
                ),
            )
    return script


def _recite_phase(
    app,
    directory: Path,
    script: Script,
    variant: str,
    *,
    skip,
    voice: str = "af_kore+af_aoede",
    speed: float = 1.0,
):
    # Imported here so runs that stop at text never load onnxruntime.
    from recitation import KokoroReciter, Lexicon, recite

    lexicon = Lexicon.load(directory / "lexicon.json")
    if lexicon is not None:
        app.log.info(f"lexicon: {len(lexicon.entries)} pronunciation entries")
    reciter = KokoroReciter(voice=voice, speed=speed, lexicon=lexicon, log=app.log.info)
    audio_dir = recite(
        script, directory, reciter, stem=section_stem, log=app.log.info, skip=skip, variant=variant
    )
    silenced = ", ".join(f"{lang} ({count})" for lang, count in reciter.skipped.most_common())
    app.log.info(f"audio in {audio_dir}" + (f"; left unspoken: {silenced}" if silenced else ""))


def _publish_phase(app, directory: Path, script: Script, variant: str, *, skip):
    from recitation import publish

    metadata = read_metadata((directory / WORKING_TEXT).resolve())
    playlist = publish(
        script,
        directory,
        stem=section_stem,
        log=app.log.info,
        skip=skip,
        variant=variant,
        metadata=metadata,
    )
    if playlist is None:
        app.log.warning("nothing to publish: no recited sections found")
    else:
        app.log.info(f"playlist ready: {playlist}")


class Lecturer(App):
    class Meta:
        label = "lecturer"
        base_controller = "base"
        handlers = [
            Base,
            Extract,
            Redact,
            EstimateGloss,
            Recite,
            Publish,
            DraftLexicon,
            DraftClassical,
            PromoteClassical,
        ]
        exit_on_close = True


# A repo-local, gitignored config file, checked for by main() below — lets a
# dev checkout keep its own settings (an in-repo elocution_dir, say) without
# writing to ~/.config/lecturer/lecturer.conf, which an installed copy on the
# same machine would also read. Not registered in Lecturer.Meta.config_files:
# Cement loads the user-level ~/.config file *after* anything named there
# (core_user_config_files always comes last), so listing it that way would
# have the installed location win instead of this one. Parsed explicitly
# after Cement's own setup so it merges in with the final say instead.
_DEV_CONFIG = Path(__file__).resolve().parent / "lecturer.conf"


def main():
    with Lecturer() as app:
        if _DEV_CONFIG.exists():
            app.config.parse_file(str(_DEV_CONFIG))
        app.run()


if __name__ == "__main__":
    main()
