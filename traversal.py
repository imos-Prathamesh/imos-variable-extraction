"""
Backward-compatibility shim — do not add logic here.
All shared logic lives in traversal_base.py.
All anglconi-specific logic lives in traversal_anglconi.py.
"""
from traversal_base import OccurrenceRow, ExtractionResult, _fetch_imos, _fetch_descriptor
from traversal_anglconi import extract_article, extract_all_articles, TraversalAnglconi as Traversal

__all__ = [
    "OccurrenceRow", "ExtractionResult",
    "_fetch_imos", "_fetch_descriptor",
    "extract_article", "extract_all_articles", "Traversal",
]