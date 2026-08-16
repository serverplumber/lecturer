"""One cement ``Controller`` per verb, aggregated for ``Lecturer.Meta.handlers``."""

from lecturer.controllers.base import Base
from lecturer.controllers.classical import DraftClassical, PromoteClassical
from lecturer.controllers.estimate import EstimateGloss
from lecturer.controllers.extract import Extract
from lecturer.controllers.lexicon import DraftLexicon
from lecturer.controllers.publish import Publish
from lecturer.controllers.recite import Recite
from lecturer.controllers.redact import Redact

# Order matters here: cement uses it for controller registration/help
# ordering, so this mirrors the verb sequence of the pipeline itself
# rather than being alphabetized.
HANDLERS = [
    Base,
    Extract,
    Redact,
    EstimateGloss,
    Recite,
    Publish,
    DraftLexicon,
    DraftClassical,
    PromoteClassical,
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
