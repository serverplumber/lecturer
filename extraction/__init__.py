"""Extract running text and footnotes from monographs in various formats."""

from pathlib import Path

from extraction.base import Extraction, Extractor, Footnote, Section, UnsupportedFormatError
from extraction.epub import EpubExtractor
from extraction.pdf import PdfExtractor

__all__ = [
    "Extraction",
    "Extractor",
    "Footnote",
    "Section",
    "UnsupportedFormatError",
    "extract",
]

_EXTRACTORS: dict[str, Extractor] = {
    ".epub": EpubExtractor(),
    ".pdf": PdfExtractor(),
}


def extract(document: Path) -> Extraction:
    """Extract ``document`` using the strategy registered for its suffix."""
    suffix = document.suffix.lower()
    if suffix not in _EXTRACTORS:
        raise UnsupportedFormatError(suffix)
    return _EXTRACTORS[suffix].extract(document)
