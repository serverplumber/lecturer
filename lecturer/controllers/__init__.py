"""One cement ``Controller`` per verb, aggregated for ``Lecturer.Meta.handlers``."""

from lecturer.controllers.base import Base
from lecturer.controllers.classical import DraftClassical, PromoteClassical
from lecturer.controllers.estimate import EstimateGloss
from lecturer.controllers.extract import Extract
from lecturer.controllers.lexicon import DraftLexicon
from lecturer.controllers.publish import Publish
from lecturer.controllers.recite import Recite
from lecturer.controllers.redact import Redact

# Order matters here, but counterintuitively backwards: cement's
# ArgparseController._setup_controllers resolves siblings nested on the same
# parent (all of these are stacked_on "base") by insert(0, ...)-ing each into
# its resolved list in registration order, which reverses that order in the
# final --help listing. So this list is written in the *reverse* of the
# pipeline sequence it's meant to display — verified against `lecturer --help`
# after each reordering, since the effect isn't otherwise obvious from
# reading cement's source alone.
HANDLERS = [
    Base,
    PromoteClassical,
    DraftClassical,
    DraftLexicon,
    Publish,
    Recite,
    EstimateGloss,
    Redact,
    Extract,
]

__all__ = [
    "HANDLERS",
    "Base",
    "DraftClassical",
    "DraftLexicon",
    "EstimateGloss",
    "Extract",
    "PromoteClassical",
    "Publish",
    "Recite",
    "Redact",
]
