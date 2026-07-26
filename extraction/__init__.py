"""Extract running text and footnotes from monographs in various formats."""

from collections.abc import Callable
from pathlib import Path

from extraction.base import (
    Extraction,
    Extractor,
    Footnote,
    Metadata,
    Section,
    UnsupportedFormatError,
)
from extraction.epub import EpubExtractor
from extraction.epub import read_metadata as _epub_metadata
from extraction.pdf import PdfExtractor
from extraction.pdf import read_metadata as _pdf_metadata

__all__ = [
    "Extraction",
    "Extractor",
    "Footnote",
    "Metadata",
    "Section",
    "UnsupportedFormatError",
    "extract",
    "read_metadata",
]

_EXTRACTORS: dict[str, Extractor] = {
    ".epub": EpubExtractor(),
    ".pdf": PdfExtractor(),
}

_METADATA_READERS: dict[str, Callable[[Path], Metadata]] = {
    ".epub": _epub_metadata,
    ".pdf": _pdf_metadata,
}


def extract(document: Path) -> Extraction:
    """Extract ``document`` using the strategy registered for its suffix."""
    suffix = document.suffix.lower()
    if suffix not in _EXTRACTORS:
        raise UnsupportedFormatError(suffix)
    return _EXTRACTORS[suffix].extract(document)


def read_metadata(document: Path) -> Metadata:
    """The document's own bibliographic metadata, for tagging published audio."""
    suffix = document.suffix.lower()
    if suffix not in _METADATA_READERS:
        raise UnsupportedFormatError(suffix)
    return _METADATA_READERS[suffix](document)
