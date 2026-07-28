"""Old Testament Pseudepigrapha sigla — SBL §8.3.4, hand-typed, then cleaned.

Unlike ``biblical.py`` and ``stephanus.py``, this wasn't auto-transcribed
from SBL's own compilation: SBL's front matter claims editorial authorship
over that selection, so reproducing it wholesale here would be a
derivative of the compilation, not a fact-per-citation use — see the
project's copyright-caution convention. The table below is the user's own
typed-in copy, sourced from a lookup they did themselves rather than this
project transcribing SBL's PDF; that sidesteps the concern the same way a
hand-copied table always has.

The pasted-in table needed real cleanup, not just formatting:

- Two stray non-breaking em-spaces (a PDF copy-paste artefact, not visible
  as ordinary whitespace) broke the file outright — a ``SyntaxError``, not
  a style nit.
- "Treat." / "Shem Treatise of Shem" was a mis-split entry; the siglum is
  two words, "Treat. Shem" -> "Treatise of Shem".
- SBL's own "Use LAB" / "Use Apocr. Ezek." / "Use Hist. Rech." / "Use 4
  Bar." entries are cross-references *within the print handbook* telling
  an editor which siglum to prefer — spoken literally, "Use LAB" would
  come out of the TTS as those exact words. Resolved to whatever their
  target actually speaks instead (``Ant. bib.`` speaks the same as
  ``LAB``, etc.), never left as apparatus text.
- Two entries ("Ascen. Isa.", "Mart. Isa.") aren't cross-references but do
  the same kind of thing — pointing at a page range within a different,
  longer composite work ("Mart. Ascen. Isa. 6-11") rather than naming
  their own title. Given clean English names for those sub-sections
  instead of narrating the range.
- Every parenthetical scholarly gloss ("2 Baruch (Syriac Apocalypse)",
  "5 Maccabees (Arabic)") is dropped from the spoken form — apparatus for
  a reader's eye, not something a TTS should recite mid-sentence, the
  same call made for the Damascus Document's full SBL description in
  ``qumran.py``.
- A duplicate "4 Ezra" key from the pasted table (SBL lists it as its own
  trivial "4 Ezra -> 4 Ezra") silently overwrote this file's original,
  evidenced "Fourth Ezra" spoken form — a dict literal keeps only the
  last of a repeated key. Restored to "Fourth Ezra"; the several other
  harmless exact-duplicate keys (repeated identically) are just
  collapsed to one each.

Three bare, unpunctuated sigla ("Sib Or", "Jub", "Pss Sol") are kept
alongside SBL's own punctuated forms ("Sib. Or.", "Pss. Sol.") because
real citations in Collins' *The Apocalyptic Imagination* use both — not
speculative, both spellings are directly evidenced. "Jub." isn't listed
separately: ``_merge``'s optional-period separator already matches it off
the bare "Jub" key, the same as every single-word siglum elsewhere.

No spoken form here takes a leading article ("Testament of Dan", not "the
Testament of Dan") — matching ``biblical.py``'s own bare-title convention
("1 Cor" -> "First Corinthians", never "the First Corinthians"), so a
citation reads the same grammatical way regardless of which system
resolved it.
"""

from redaction.elocution.base import System

PSEUDEPIGRAPHA_SIGLA: dict[str, str] = {
    "Ahiqar": "Ahiqar",
    "Ant. bib.": "Liber antiquitatum biblicarum",  # SBL: use LAB
    "Apoc. Ab.": "Apocalypse of Abraham",
    "Apoc. Adam": "Apocalypse of Adam",
    "Apoc. Dan.": "Apocalypse of Daniel",
    "Apoc. El. (C)": "Coptic Apocalypse of Elijah",
    "Apoc. El. (H)": "Hebrew Apocalypse of Elijah",
    "Apoc. Ezek.": "Apocryphon of Ezekiel",  # SBL: use Apocr. Ezek.
    "Apoc. Mos.": "Apocalypse of Moses",
    "Apoc. Sedr.": "Apocalypse of Sedrach",
    "Apoc. Zeph.": "Apocalypse of Zephaniah",
    "Apoc. Zos.": "History of the Rechabites",  # SBL: use Hist. Rech.
    "Apocr. Ezek.": "Apocryphon of Ezekiel",
    "Aris. Ex.": "Aristeas the Exegete",
    "Aristob.": "Aristobulus",
    "Artap.": "Artapanus",
    "As. Mos": "Assumption of Moses",
    "Ascen. Isa.": "Ascension of Isaiah",  # SBL: Mart. Ascen. Isa. 6-11
    "2 Bar.": "2 Baruch",
    "3 Bar.": "3 Baruch",
    "4 Bar.": "4 Baruch",
    "Bib. Ant.": "Liber antiquitatum biblicarum",  # SBL: use LAB
    "Bk. Noah": "Book of Noah",
    "Cav. Tr.": "Cave of Treasures",
    "Cl. Mal.": "Cleodemus Malchus",
    "Dem.": "Demetrius the Chronographer",
    "El. Mod.": "Eldad and Modad",
    "1 En.": "1 Enoch",
    "2 En.": "2 Enoch",
    "3 En.": "3 Enoch",
    "Eup.": "Eupolemus",
    "Ezek. Trag.": "Ezekiel the Tragedian",
    "4 Ezra": "Fourth Ezra",
    "5 Apoc. Syr. Pss.": "Five Apocryphal Syriac Psalms",
    "Gk. Apoc. Ezra": "Greek Apocalypse of Ezra",
    "Hec. Ab.": "Hecataeus of Abdera",
    "Hel. Syn. Pr.": "Hellenistic Synagogal Prayers",
    "Hist. Jos.": "History of Joseph",
    "Hist. Rech.": "History of the Rechabites",
    "Jan. Jam.": "Jannes and Jambres",
    "Jos. Asen.": "Joseph and Aseneth",
    "Jub": "Jubilees",
    "LAB": "Liber antiquitatum biblicarum",
    "LAE": "Life of Adam and Eve",
    "Lad. Jac.": "Ladder of Jacob",
    "Let. Aris.": "Letter of Aristeas",
    "Liv. Pro.": "Lives of the Prophets",
    "Lost Tr.": "Lost Tribes",
    "3 Macc.": "3 Maccabees",
    "4 Macc.": "4 Maccabees",
    "5 Macc.": "5 Maccabees",
    "Mart. Ascen. Isa.": "Martyrdom and Ascension of Isaiah",
    "Mart. Isa.": "Martyrdom of Isaiah",  # SBL: Mart. Ascen. Isa. 1-5
    "Odes Sol.": "Odes of Solomon",
    "PJ": "4 Baruch",  # SBL: use 4 Bar.
    "Ph. E. Poet": "Philo the Epic Poet",
    "Pr. Jac.": "Prayer of Jacob",
    "Pr. Jos.": "Prayer of Joseph",
    "Pr. Man.": "Prayer of Manasseh",
    "Pr. Mos.": "Prayer of Moses",
    "Ps.-Eup.": "Pseudo-Eupolemus",
    "Ps.-Hec.": "Pseudo-Hecataeus",
    "Ps.-Orph.": "Pseudo-Orpheus",
    "Ps.-Philo": "Liber antiquitatum biblicarum",  # SBL: use LAB
    "Ps.-Phoc.": "Pseudo-Phocylides",
    "Pss Sol": "Psalms of Solomon",
    "Pss. Sol.": "Psalms of Solomon",
    "Ques. Ezra": "Questions of Ezra",
    "Rev. Ezra": "Revelation of Ezra",
    "Sib Or": "Sibylline Oracles",
    "Sib. Or.": "Sibylline Oracles",
    "Syr. Men.": "Sentences of the Syriac Menander",
    "T. 12 Patr.": "Testaments of the Twelve Patriarchs",
    "T. Ash.": "Testament of Asher",
    "T. Benj.": "Testament of Benjamin",
    "T. Dan": "Testament of Dan",
    "T. Gad": "Testament of Gad",
    "T. Iss.": "Testament of Issachar",
    "T. Jos.": "Testament of Joseph",
    "T. Jud.": "Testament of Judah",
    "T. Levi": "Testament of Levi",
    "T. Naph.": "Testament of Naphtali",
    "T. Reu.": "Testament of Reuben",
    "T. Sim.": "Testament of Simeon",
    "T. Zeb.": "Testament of Zebulun",
    "T. 3 Patr.": "Testaments of the Three Patriarchs",
    "T. Ab.": "Testament of Abraham",
    "T. Isaac": "Testament of Isaac",
    "T. Jac.": "Testament of Jacob",
    "T. Adam": "Testament of Adam",
    "T. Hez.": "Testament of Hezekiah",
    "T. Job": "Testament of Job",
    "T. Mos.": "Testament of Moses",
    "T. Sol.": "Testament of Solomon",
    "Theod.": "Theodotus",
    "Treat. Shem": "Treatise of Shem",
    "Vis. Ezra": "Vision of Ezra",
    "Vis. Isa.": "Ascension of Isaiah",  # SBL: use Ascen. Isa.
}


def pseudepigrapha_system() -> System:
    return System("pseudepigrapha", PSEUDEPIGRAPHA_SIGLA)
