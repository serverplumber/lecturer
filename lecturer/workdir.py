"""Work-directory setup and naming: the filesystem side of the CLI's identity.

Leaf module — no imports from any other ``lecturer`` submodule.
"""

import hashlib
import re
import shutil
from pathlib import Path

WORKING_TEXT = "working_text"


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
