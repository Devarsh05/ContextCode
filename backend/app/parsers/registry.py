"""Parser registry: map files/languages to the right parser.

Supported languages (MVP, per CLAUDE.md): Python, JavaScript, TypeScript.
"""

import os

from app.parsers.base import BaseParser
from app.parsers.javascript_parser import JavaScriptParser
from app.parsers.python_parser import PythonParser
from app.parsers.typescript_parser import TypeScriptParser

_EXT_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

_PARSER_CLASSES = {
    "python": PythonParser,
    "javascript": JavaScriptParser,
    "typescript": TypeScriptParser,
}

# Cache parser instances so the lazily built Tree-sitter Language/Parser is
# reused across files within a process.
_PARSER_CACHE: dict[str, BaseParser] = {}


def get_language_for_file(path: str) -> str | None:
    """Return the language for a file path by extension, or None if unsupported."""
    _, ext = os.path.splitext(path)
    return _EXT_TO_LANGUAGE.get(ext.lower())


def get_parser_for_language(language: str) -> BaseParser | None:
    """Return a cached parser for the language, or None if unsupported."""
    cls = _PARSER_CLASSES.get(language)
    if cls is None:
        return None
    if language not in _PARSER_CACHE:
        _PARSER_CACHE[language] = cls()
    return _PARSER_CACHE[language]
