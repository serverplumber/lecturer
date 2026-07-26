"""Classical authors cited bare, by name alone: closed, no draft needed.

Most classical historians who wrote one continuous, well-known work get no
work-siglum at all — there's nothing to disambiguate, so a citation is just
the author's own name directly before the locator ("Cassius Dio,
57.25.8", "Livy, 1.36.2-6"). ``base.py``'s ``bare_author_system`` is the
matching/replacement machinery for this; this module is the closed list of
*which* authors get it — the same kind of fact ``biblical.py``/
``stephanus.py`` hardcode once rather than re-derive per document, since
whether Cassius Dio needs a work-siglum isn't a fact about any one book's
own bibliography, it's a fact about how many works Cassius Dio wrote.

Every name here is verified against a real citation in this corpus's own
footnotes, not assumed from a style guide's general list (the same
"copyright caution" this project applies to every other siglum table —
grown from evidence, not transcribed):

- **Cassius Dio** — confirmed via ``citation_pairing.py``'s ``pair_sigla``:
  24 bare citations in ``temple_gates``' footnotes ("Cassius Dio,
  57.25.8"), and a bibliography entry (``Cassius Dio. Roman History.
  Translated by...``) that structurally confirms him primary.
- **Livy** — cited bare five times in the same footnotes ("Livy,
  39.8.3-5", "Livy, 39.16.8-9", ...), but with *no* separate bibliography
  entry in this book at all — `pair_sigla`'s bibliography-gated derivation
  can't confirm him for exactly that reason, even though the citation
  shape is identical to Cassius Dio's and just as unambiguous. Added here
  by hand instead, the same way ``classical.py``'s "Num" entry was: a
  real collision (here, a real gap) worth a one-off hardcoded fix rather
  than a document-derived one.

Grows the same way classical.py's does: one verified name at a time,
against a real citation, not a wholesale list assumed from any external
handbook.
"""

from redaction.elocution.base import System, bare_author_system

BARE_AUTHORS: frozenset[str] = frozenset(
    {
        "Cassius Dio",
        "Livy",
    }
)


def bare_authors_system() -> System:
    return bare_author_system(BARE_AUTHORS)
