"""Philo of Alexandria — closed, standard, no draft needed.

Verified against the SBL Handbook's §8.3.6, which lists Philo separately
from the general classical/patristic table (§8.3.14.3) since his corpus
gets its own dedicated section. Shares the general dotted book.section
locator, so no locator grammar of its own is needed.

"Leg" (*Legum allegoriae*) is deliberately omitted: this corpus's own
footnotes cite bare "Leg." at least twice for *Legatio ad Gaium* used
loosely instead of SBL's prescribed "Legat.", and separately cite
Cicero's *De Legibus* as "Leg. 2.22.9" — three genuinely different works
under the identical bare siglum with the identical locator shape, which
is exactly the case ``base.py``'s shape-based disambiguation *can't*
resolve (unlike "Apol." or "Leg." vs Plato's Stephanus-paginated "Leg.",
which differ in locator shape). Guessing which one a bare "Leg." means
would be wrong some fraction of the time by this corpus's own evidence,
so it's left unresolved rather than picking a winner. "Spec. Leg" below
is unaffected — it's a longer, unambiguous siglum this corpus actually
uses for *On the Special Laws*, alongside SBL's own bare "Spec".
"""

from redaction.elocution.base import System

PHILO_SIGLA: dict[str, str] = {
    "Abr": "Abraham",
    "Aet": "Eternity",
    "Agr": "Agriculture",
    "Anim": "Animals",
    "Cher": "Cherubim",
    "Conf": "Confusion",
    "Congr": "Preliminary Studies",
    "Contempl": "Contemplative Life",
    "Decal": "Decalogue",
    "Deo": "God",
    "Det": "Worse",
    "Deus": "Unchangeable",
    "Ebr": "Drunkenness",
    "Exsecr": "Curses",
    "Flacc": "Flaccus",
    "Fug": "Flight",
    "Gig": "Giants",
    "Her": "Heir",
    "Hypoth": "Hypothetica",
    "Ios": "Joseph",
    "Legat": "Embassy",
    "Migr": "Migration",
    "Mos": "Moses",
    "Mut": "Names",
    "Opif": "Creation",
    "Plant": "Planting",
    "Post": "Posterity",
    "Praem": "Rewards",
    "Prob": "Good Person",
    "Prov": "Providence",
    "QE": "Questions and Answers on Exodus",
    "QG": "Questions and Answers on Genesis",
    "Sacr": "Sacrifices",
    "Sobr": "Sobriety",
    "Somn": "Dreams",
    "Spec": "Special Laws",
    "Spec. Leg": "Special Laws",  # this corpus's own variant form
    "Virt": "Virtues",
}


def philo_system() -> System:
    return System("philo", PHILO_SIGLA)
