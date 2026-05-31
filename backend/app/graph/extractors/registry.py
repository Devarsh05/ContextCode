"""Extractor registry: map file extensions to the right extractor.

Cache is keyed by extractor class (not by language string), so all
JS/TS extensions share a single JavaScriptExtractor instance.
"""

import os

from app.graph.extractors.base import BaseExtractor
from app.graph.extractors.javascript_extractor import JavaScriptExtractor
from app.graph.extractors.python_extractor import PythonExtractor

_EXT_TO_CLASS: dict[str, type[BaseExtractor]] = {
    ".py": PythonExtractor,
    ".js": JavaScriptExtractor,
    ".jsx": JavaScriptExtractor,
    ".ts": JavaScriptExtractor,
    ".tsx": JavaScriptExtractor,
}

_EXTRACTOR_CACHE: dict[type[BaseExtractor], BaseExtractor] = {}


def get_extractor(file_path: str) -> BaseExtractor | None:
    """Return a cached extractor for file_path by extension, or None."""
    _, ext = os.path.splitext(file_path)
    cls = _EXT_TO_CLASS.get(ext.lower())
    if cls is None:
        return None
    if cls not in _EXTRACTOR_CACHE:
        _EXTRACTOR_CACHE[cls] = cls()
    return _EXTRACTOR_CACHE[cls]
