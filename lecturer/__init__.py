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

Split one file per verb under ``controllers/`` so multiple people can
work on different commands without all touching the same file:
``workdir.py`` (work-dir/naming helpers), ``io.py`` (the
``redactions/`` file-tree read/write format), ``phases.py`` (the four
pipeline phases, shared by more than one verb), ``arguments.py``
(shared CLI argument definitions), and ``main.py`` (the ``App`` class
and entry point).
"""

from lecturer.main import main

__all__ = ["main"]
