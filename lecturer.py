"""Turn monographs into audiobooks read as though by the author.

Point lecturer at a document and it sets up a working directory that holds
the source text, every intermediary file, and eventually the final audio.
"""

import re
import shutil
from collections import Counter
from pathlib import Path

from cement import App, Controller

from extraction import Extraction, UnsupportedFormatError, extract
from redaction import (
    DEFAULT_MODELS,
    PROVIDERS,
    TAGGING_MODELS,
    FootnoteWeaver,
    Glossator,
    ProviderError,
    Script,
    TongueInterpreter,
    redact,
)

WORKING_TEXT = "working_text"


def slugify(text: str) -> str:
    """Reduce a document name to a filesystem-friendly directory name."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "document"


def section_stem(index: int, title: str) -> str:
    """The filename stem shared by a section's pipeline files."""
    return f"{index:02d}_{slugify(title)[:48].rstrip('_')}"


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


def write_redactions(script: Script, directory: Path, variant: str) -> Path:
    """Write each redacted section to ``redactions/<variant>/NN_title.txt``.

    Weaving variants fork the tree, mirroring ``audio/``: the plain book
    and the glossed rendering live side by side. Utterances are separated
    by blank lines, each opening with a tag line — ``[manner]``, or
    ``[manner lang=xx]`` away from the lecture's language — so later
    pipeline stages know how the stretch is delivered. Notes no layer wove
    in are kept next door in ``.unwoven.txt`` files.
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
        (redactions_dir / f"{stem}.txt").write_text(rendered + "\n")
        if section.footnotes:
            notes = "\n".join(f"[^{note.ref}]: {note.text}" for note in section.footnotes)
            (redactions_dir / f"{stem}.unwoven.txt").write_text(notes + "\n")
    return redactions_dir


class Base(Controller):
    class Meta:
        label = "base"
        description = "Turn monographs into audiobooks."
        arguments = [
            (
                ["-o", "--output"],
                {
                    "help": "output directory for intermediary files and the final audio "
                    "(default: derived from the document name)",
                    "dest": "output",
                    "metavar": "DIR",
                },
            ),
            (
                ["--llm"],
                {
                    "help": "weave footnotes in as spoken digressions with the LLM "
                    "glossator instead of dropping them (billed API calls; results "
                    "are cached in the working directory)",
                    "action": "store_true",
                    "dest": "llm",
                },
            ),
            (
                ["--interpret"],
                {
                    "help": "tag Latin-alphabet language switches (loanwords, Latin "
                    "phrases, names) with the LLM so the reciter pronounces them "
                    "in their own language (cheap model by default; cached)",
                    "action": "store_true",
                    "dest": "interpret",
                },
            ),
            (
                ["--verbatim-notes"],
                {
                    "help": "weave every footnote in verbatim at its anchor instead "
                    "of dropping them (inspection mode; unpleasant listening)",
                    "action": "store_true",
                    "dest": "verbatim_notes",
                },
            ),
            (
                ["--provider"],
                {
                    "help": "LLM provider for the glossator",
                    "dest": "provider",
                    "choices": sorted(PROVIDERS),
                    "default": "anthropic",
                },
            ),
            (
                ["--model"],
                {
                    "help": "model for the LLM glossator (default per provider: "
                    + ", ".join(f"{name} → {model}" for name, model in DEFAULT_MODELS.items()),
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
                    "help": "reasoning effort for the glossator (low/medium/high; "
                    "local reasoning models like gpt-oss need high to gloss "
                    "rather than copy)",
                    "dest": "effort",
                    "metavar": "LEVEL",
                },
            ),
            (
                ["--speak"],
                {
                    "help": "synthesise the redacted script into audio/ with Kokoro "
                    "(the model is fetched once into the user cache)",
                    "action": "store_true",
                    "dest": "speak",
                },
            ),
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
                ["--lexicon-draft"],
                {
                    "help": "sweep the book for pronunciation risks with the LLM "
                    "and merge draft entries into the work dir's lexicon.json "
                    "(existing entries are never overwritten)",
                    "action": "store_true",
                    "dest": "lexicon_draft",
                },
            ),
            (
                ["--publish"],
                {
                    "help": "bind recited sections into Opus files plus an M3U "
                    "playlist (works on existing audio; ~10x smaller than wav)",
                    "action": "store_true",
                    "dest": "publish",
                },
            ),
            (
                ["--sections"],
                {
                    "help": "recite only sections whose title matches this regex "
                    "(default: everything except apparatus — front matter, "
                    "bibliography, index, ...)",
                    "dest": "sections",
                    "metavar": "REGEX",
                },
            ),
            (
                ["--speed"],
                {
                    "help": "speech rate multiplier for the reciter (0.5-2.0)",
                    "dest": "speed",
                    "metavar": "FACTOR",
                    "type": float,
                    "default": 1.0,
                },
            ),
            (
                ["document"],
                {
                    "help": "path to the monograph to read (epub, pdf, ...)",
                    "nargs": "?",
                },
            ),
        ]

    def _default(self):
        if self.app.pargs.document is None:
            self.app.args.print_help()
            return

        document = Path(self.app.pargs.document)
        if not document.is_file():
            self.app.log.error(f"no such document: {document}")
            self.app.exit_code = 1
            return

        directory = Path(self.app.pargs.output or slugify(document.stem))
        copy = prepare_workdir(document, directory)
        self.app.log.info(f"working directory ready: {directory}/{WORKING_TEXT}")

        try:
            extraction = extract(copy)
        except UnsupportedFormatError as error:
            self.app.log.warning(f"{error}; nothing extracted yet")
            return
        sections_dir = write_sections(extraction, directory)
        notes = sum(len(section.footnotes) for section in extraction.sections)
        self.app.log.info(
            f"extracted {len(extraction.sections)} sections ({notes} footnotes) into {sections_dir}"
        )

        weaver = None
        interpreter = None
        variant = "book"
        if self.app.pargs.verbatim_notes:
            weaver = FootnoteWeaver()
            variant = "verbatim"
        try:
            if self.app.pargs.llm:
                variant = "glossed"
                weaver = Glossator(
                    provider=self._provider(DEFAULT_MODELS),
                    cache_path=directory / "gloss_cache.json",
                    log=self.app.log.info,
                )
            if self.app.pargs.interpret:
                interpreter = TongueInterpreter(
                    provider=self._provider(TAGGING_MODELS),
                    cache_path=directory / "tongue_cache.json",
                    log=self.app.log.info,
                )
        except ProviderError as error:
            self.app.log.error(str(error))
            self.app.exit_code = 1
            return
        try:
            script = redact(extraction, weaver=weaver, interpreter=interpreter)
        except ProviderError as error:
            self.app.log.error(f"glossing failed: {error} (finished paragraphs are cached)")
            self.app.exit_code = 1
            return
        for name, layer in (("glossator", weaver), ("interpreter", interpreter)):
            if isinstance(layer, Glossator | TongueInterpreter):
                provider = layer.provider
                if provider.input_tokens or provider.output_tokens:
                    self.app.log.info(
                        f"{name} used {provider.input_tokens} input + "
                        f"{provider.output_tokens} output tokens on {provider.label}"
                    )
        redactions_dir = write_redactions(script, directory, variant)
        unwoven = sum(len(section.footnotes) for section in script.sections)
        digressions = notes - unwoven
        spoken_notes = (
            f"{digressions} digressions woven, {unwoven} notes left unwoven"
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
        self.app.log.info(
            f"redacted into {redactions_dir}: {spoken_notes}"
            + (f", other tongues: {spoken}" if tongues else "")
        )

        if self.app.pargs.lexicon_draft:
            from recitation import draft

            try:
                draft(
                    script,
                    self._provider(TAGGING_MODELS),
                    directory / "lexicon.json",
                    log=self.app.log.info,
                )
            except ProviderError as error:
                self.app.log.error(f"lexicon draft failed: {error}")
                self.app.exit_code = 1
                return
        if self.app.pargs.speak or self.app.pargs.publish:
            # Imported here so runs that stop at text never load onnxruntime.
            from recitation import APPARATUS, KokoroReciter, Lexicon, publish, recite

            if self.app.pargs.sections:
                wanted = re.compile(self.app.pargs.sections, re.IGNORECASE)
                skip = lambda title: not wanted.search(title)  # noqa: E731
            else:
                skip = lambda title: bool(APPARATUS.search(title))  # noqa: E731
        if self.app.pargs.speak:
            lexicon = Lexicon.load(directory / "lexicon.json")
            if lexicon is not None:
                self.app.log.info(f"lexicon: {len(lexicon.entries)} pronunciation entries")
            reciter = KokoroReciter(
                voice=self.app.pargs.voice,
                speed=self.app.pargs.speed,
                lexicon=lexicon,
                log=self.app.log.info,
            )
            audio_dir = recite(
                script,
                directory,
                reciter,
                stem=section_stem,
                log=self.app.log.info,
                skip=skip,
                variant=variant,
            )
            silenced = ", ".join(
                f"{lang} ({count})" for lang, count in reciter.skipped.most_common()
            )
            self.app.log.info(
                f"audio in {audio_dir}" + (f"; left unspoken: {silenced}" if silenced else "")
            )
        if self.app.pargs.publish:
            playlist = publish(
                script,
                directory,
                stem=section_stem,
                log=self.app.log.info,
                skip=skip,
                variant=variant,
            )
            if playlist is None:
                self.app.log.warning("nothing to publish: no recited sections found")
            else:
                self.app.log.info(f"playlist ready: {playlist}")

    def _provider(self, defaults):
        return PROVIDERS[self.app.pargs.provider](
            model=self.app.pargs.model or defaults[self.app.pargs.provider],
            base_url=self.app.pargs.base_url,
            effort=self.app.pargs.effort,
        )


class Lecturer(App):
    class Meta:
        label = "lecturer"
        base_controller = "base"
        handlers = [Base]
        exit_on_close = True


def main():
    with Lecturer() as app:
        app.run()


if __name__ == "__main__":
    main()
