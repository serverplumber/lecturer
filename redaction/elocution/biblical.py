"""The SBL Handbook's biblical book sigla — closed, standard, no draft needed.

Verified against ``style_guides/The_SBL_Handbook_of_Style...pdf`` §8.3.1
(Hebrew Bible/Old Testament), §8.3.2 (New Testament), and §8.3.3
(Deuterocanonical Works and Septuagint) — SBL treats all three under one
punctuation rule (colon for chapter:verse, no period on the siglum) and
groups them together for that reason, which is why the "biblical" system
covers the deuterocanon/Apocrypha too rather than needing its own file.
Each numbered book is expanded from SBL's compact "1-2 Sam" print
convention into separate literal sigla ("1 Sam", "2 Sam"), since that's
how they actually appear in running text; the spoken form stays "First
Samuel" rather than SBL's own English-title column ("1 Samuel") — SBL
verifies which siglum maps to which book, not how it should be read
aloud, and "1 Corinthians" read aloud is the exact mangling this system
exists to fix.

"Num" (Numbers) collides with Plutarch's *Numa*, cited as "Num." in this
corpus — see ``classical.py``'s seed table and ``base.py``'s ``_merge``
for how that tie resolves (classical wins it here; Numbers stays
available for corpora that do cite it under this siglum).
"""

from redaction.elocution.base import System

BIBLICAL_SIGLA: dict[str, str] = {
    # §8.3.1 Hebrew Bible/Old Testament
    "Gen": "Genesis",
    "Exod": "Exodus",
    "Lev": "Leviticus",
    "Num": "Numbers",
    "Deut": "Deuteronomy",
    "Josh": "Joshua",
    "Judg": "Judges",
    "Ruth": "Ruth",
    "1 Sam": "First Samuel",
    "2 Sam": "Second Samuel",
    "1 Kgdms": "First Kingdoms",  # LXX numbering, alongside 1-2 Sam
    "2 Kgdms": "Second Kingdoms",
    "1 Kgs": "First Kings",
    "2 Kgs": "Second Kings",
    "3 Kgdms": "Third Kingdoms",  # LXX numbering, alongside 1-2 Kgs
    "4 Kgdms": "Fourth Kingdoms",
    "1 Chr": "First Chronicles",
    "2 Chr": "Second Chronicles",
    "Ezra": "Ezra",
    "Neh": "Nehemiah",
    "Esth": "Esther",
    "Job": "Job",
    "Ps": "Psalm",
    "Pss": "Psalms",
    "Prov": "Proverbs",
    "Eccl": "Ecclesiastes",
    "Qoh": "Ecclesiastes",  # alt. siglum, "Qoheleth"
    "Song": "Song of Songs",
    "Cant": "Song of Songs",  # alt. siglum, "Canticles"
    "Isa": "Isaiah",
    "Jer": "Jeremiah",
    "Lam": "Lamentations",
    "Ezek": "Ezekiel",
    "Dan": "Daniel",
    "Hos": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obad": "Obadiah",
    "Jonah": "Jonah",
    "Mic": "Micah",
    "Nah": "Nahum",
    "Hab": "Habakkuk",
    "Zeph": "Zephaniah",
    "Hag": "Haggai",
    "Zech": "Zechariah",
    "Mal": "Malachi",
    # §8.3.2 New Testament
    "Matt": "Matthew",
    "Mark": "Mark",
    "Luke": "Luke",
    "John": "John",
    "Acts": "Acts",
    "Rom": "Romans",
    "1 Cor": "First Corinthians",
    "2 Cor": "Second Corinthians",
    "Gal": "Galatians",
    "Eph": "Ephesians",
    "Phil": "Philippians",
    "Col": "Colossians",
    "1 Thess": "First Thessalonians",
    "2 Thess": "Second Thessalonians",
    "1 Tim": "First Timothy",
    "2 Tim": "Second Timothy",
    "Titus": "Titus",
    "Phlm": "Philemon",
    "Heb": "Hebrews",
    "Jas": "James",
    "1 Pet": "First Peter",
    "2 Pet": "Second Peter",
    "1 John": "First John",
    "2 John": "Second John",
    "3 John": "Third John",
    "Jude": "Jude",
    "Rev": "Revelation",
    # §8.3.3 Deuterocanonical Works and Septuagint
    "Tob": "Tobit",
    "Jdt": "Judith",
    "Add Esth": "Additions to Esther",
    "Wis": "Wisdom of Solomon",
    "Sir": "Sirach",
    "Bar": "Baruch",
    "Ep Jer": "Epistle of Jeremiah",
    "Add Dan": "Additions to Daniel",
    "Pr Azar": "Prayer of Azariah",
    "Sg Three": "Song of the Three Young Men",
    "Sus": "Susanna",
    "Bel": "Bel and the Dragon",
    "1 Macc": "First Maccabees",
    "2 Macc": "Second Maccabees",
    "3 Macc": "Third Maccabees",
    "4 Macc": "Fourth Maccabees",
    "1 Esd": "First Esdras",
    "2 Esd": "Second Esdras",
    "Pr Man": "Prayer of Manasseh",
    "Ps 151": "Psalm one hundred fifty-one",
}


def biblical_system() -> System:
    return System("biblical", BIBLICAL_SIGLA)
