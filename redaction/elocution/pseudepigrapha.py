"""Old Testament Pseudepigrapha sigla — SBL §8.3.4, scoped to what's evidenced.

Unlike ``biblical.py`` and ``stephanus.py``, this is *not* a transcription of
SBL's full closed table (over sixty works, many never cited outside a
specialist bibliography of the pseudepigrapha itself): SBL's own front
matter claims editorial authorship over that compilation's selection, so
reproducing it wholesale would be a derivative of the compilation, not a
fact-per-citation use — see the project's copyright-caution convention.
What's fine to build from freely is the handful of sigla a real corpus
actually cites; each entry below is verified against a real citation in
Collins' *The Apocalyptic Imagination*, not transcribed speculatively
ahead of one. Expand only when a new book turns up a genuine citation, the
same discipline ``classical.py`` follows for its own seed table.

Each spoken form is SBL's own English title (§8.3.4's second column), not
memory-recalled — a single fact per entry, independently checkable, same as
any other siglum table here.

Two sigla are cited in both dotted-and-spaced ("Sib. Or.") and bare
("Sib Or") form in this corpus — real typesetting variance, not an OCR
artefact this time, since Collins' EPUB text is otherwise clean — so both
literal forms are listed; every other entry here only ever appears in one
written form.

TODO(serverplumber): SBL §8.3.4 lists roughly sixty pseudepigrapha sigla;
only the eight evidenced above are here. Type in the rest by hand from a
copy you look up yourself (no copyright issue looking a fact up and typing
it — the issue above is only about *this* project auto-transcribing SBL's
whole curated compilation wholesale) whenever a new corpus cites one.
"""

from redaction.elocution.base import System

PSEUDEPIGRAPHA_SIGLA: dict[str, str] = {
    "Sib. Or.": "Sibylline Oracles",
    "Sib Or": "Sibylline Oracles",
    "4 Ezra": "Fourth Ezra",
    "Jub": "Jubilees",
    "T. Dan": "Testament of Dan",
    "T. Gad": "Testament of Gad",
    "T. Levi": "Testament of Levi",
    "Pss Sol": "Psalms of Solomon",
}


def pseudepigrapha_system() -> System:
    return System("pseudepigrapha", PSEUDEPIGRAPHA_SIGLA)
