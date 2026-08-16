"""The pipeline phases, shared by more than one verb.

Each ``_*_phase`` function runs one stage of extract -> redact -> recite ->
publish and logs its own summary; verbs in ``lecturer.controllers`` call
these rather than reimplementing the phase logic per command.
"""

import re
from collections import Counter
from pathlib import Path

from extraction import Extraction, UnsupportedFormatError, extract, read_metadata
from lecturer.io import read_redactions, write_redactions, write_review, write_sections
from lecturer.workdir import WORKING_TEXT, prepare_workdir, section_stem
from redaction import (
    PROVIDERS,
    FootnoteWeaver,
    Glossator,
    ProviderError,
    Script,
    TongueInterpreter,
    price_tokens,
    redact,
)
from redaction.usage import append_usage, new_record

_DEFAULT_ELOCUTION_DIR = Path.home() / ".config" / "lecturer" / "elocution"


def _provider(app, defaults):
    return PROVIDERS[app.pargs.provider](
        model=app.pargs.model or defaults[app.pargs.provider],
        base_url=app.pargs.base_url,
        effort=app.pargs.effort,
    )


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


def _persist_gloss_usage(app, directory: Path, weaver) -> None:
    """Persist a Glossator's real usage — called on success *and* on a crash.

    A ``ProviderError`` mid-run doesn't unwind the Glossator's own counters;
    whatever it billed before the failure (real money, real cache entries
    already written) must not vanish from ``gloss_usage.jsonl`` just because
    the surrounding ``redact()`` pipeline didn't finish — a later
    ``estimate-gloss`` would otherwise never see it. No-op for anything that
    isn't a ``Glossator``, or one that never reached a billed call.
    """
    if not isinstance(weaver, Glossator) or not weaver.calls:
        return
    record = new_record(
        provider_label=weaver.provider.label,
        input_tokens=weaver.gloss_input_tokens,
        output_tokens=weaver.gloss_output_tokens,
        cache_creation_input_tokens=weaver.gloss_cache_creation_tokens,
        cache_read_input_tokens=weaver.gloss_cache_read_tokens,
        calls=weaver.calls,
        truncated=weaver.gloss_truncated,
    )
    append_usage(directory / "gloss_usage.jsonl", record)
    dollars = price_tokens(
        weaver.provider.model,
        input_tokens=record.input_tokens,
        cache_creation_tokens=record.cache_creation_input_tokens,
        cache_read_tokens=record.cache_read_input_tokens,
        output_tokens=record.output_tokens,
    )
    cost = f"${dollars:.2f}" if dollars is not None else "no pricing on file"
    app.log.info(
        f"glossator billed {record.calls} call(s) this run: {record.input_tokens} input + "
        f"{record.cache_creation_input_tokens} cache-write + {record.cache_read_input_tokens} "
        f"cache-read + {record.output_tokens} output tokens on {record.provider_label} "
        f"— real cost: {cost}"
    )


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
        _persist_gloss_usage(app, directory, weaver)
        # near_misses doesn't exist yet — Elocutor runs after weaving — but
        # a Glossator's own reverted paragraphs survive the crash just like
        # its usage counters do, and shouldn't vanish from review.md either.
        reverted = weaver.reverted if isinstance(weaver, Glossator) else []
        write_review(near_misses=[], reverted=reverted, directory=directory, variant=variant)
        app.log.error(f"redaction failed: {error} (finished paragraphs are cached)")
        app.exit_code = 1
        raise SystemExit(app.exit_code) from error
    redactions_dir = write_redactions(script, directory, variant)
    reverted = weaver.reverted if isinstance(weaver, Glossator) else []
    review_path = write_review(near_misses, reverted, directory, variant)
    if review_path is not None:
        parts = []
        if near_misses:
            parts.append(f"{len(near_misses)} unconverted citation(s)")
        if reverted:
            parts.append(f"{len(reverted)} paragraph(s) reverted to verbatim weaving")
        app.log.warning(f"{' and '.join(parts)} — see {review_path}")
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
    if isinstance(interpreter, TongueInterpreter):
        provider = interpreter.provider
        if provider.input_tokens or provider.output_tokens:
            app.log.info(
                f"interpreter used {provider.input_tokens} input + "
                f"{provider.output_tokens} output tokens on {provider.label}"
            )
    _persist_gloss_usage(app, directory, weaver)
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
