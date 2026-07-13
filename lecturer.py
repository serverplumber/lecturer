"""Turn monographs into audiobooks read as though by the author.

Point lecturer at a document and it sets up a working directory that holds
the source text, every intermediary file, and eventually the final audio.
"""

import re
import shutil
from pathlib import Path

from cement import App, Controller

from extraction import Extraction, UnsupportedFormatError, extract

WORKING_TEXT = "working_text"


def slugify(text: str) -> str:
    """Reduce a document name to a filesystem-friendly directory name."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "document"


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
        stem = f"{index:02d}_{slugify(section.title)[:48].rstrip('_')}"
        (sections_dir / f"{stem}.txt").write_text(section.text + "\n")
        if section.footnotes:
            notes = "\n".join(f"[^{note.ref}]: {note.text}" for note in section.footnotes)
            (sections_dir / f"{stem}.footnotes.txt").write_text(notes + "\n")
    return sections_dir


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
