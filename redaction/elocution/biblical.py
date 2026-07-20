"""The SBL Handbook's biblical book sigla — closed, standard, no draft needed.

Unlike the classical author-work abbreviations, biblical book sigla are a
small, fixed, universally known list: hardcoded rather than drafted.
Covers the Protestant canon plus the deuterocanon/Apocrypha, since
freelance-experts scholarship cites Tobit and Sirach as readily as Paul.

"Num" (Numbers) collides with Plutarch's *Numa*, cited as "Num." in this
corpus — see ``classical.py``'s seed table and ``base.py``'s ``_merge``
for how that tie resolves (classical wins it here; Numbers stays
available for corpora that do cite it under this siglum).
"""

from redaction.elocution.base import System

BIBLICAL_SIGLA: dict[str, str] = {
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
    "1 Kgs": "First Kings",
    "2 Kgs": "Second Kings",
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
    "Song": "Song of Songs",
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
    "Tob": "Tobit",
    "Jdt": "Judith",
    "Wis": "Wisdom of Solomon",
    "Sir": "Sirach",
    "Bar": "Baruch",
    "1 Macc": "First Maccabees",
    "2 Macc": "Second Maccabees",
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
}


def biblical_system() -> System:
    return System("biblical", BIBLICAL_SIGLA)
