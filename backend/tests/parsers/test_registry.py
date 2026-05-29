import pytest

from app.parsers.base import BaseParser
from app.parsers.javascript_parser import JavaScriptParser
from app.parsers.python_parser import PythonParser
from app.parsers.registry import get_language_for_file, get_parser_for_language
from app.parsers.typescript_parser import TypeScriptParser


class TestGetLanguageForFile:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("a/b/foo.py", "python"),
            ("foo.js", "javascript"),
            ("foo.jsx", "javascript"),
            ("foo.ts", "typescript"),
            ("Button.tsx", "typescript"),
        ],
    )
    def test_supported_extensions(self, path, expected):
        assert get_language_for_file(path) == expected

    @pytest.mark.parametrize("path", ["foo.go", "README.md", "Makefile", "noext"])
    def test_unsupported_returns_none(self, path):
        assert get_language_for_file(path) is None


class TestGetParserForLanguage:
    @pytest.mark.parametrize(
        "lang,cls",
        [
            ("python", PythonParser),
            ("javascript", JavaScriptParser),
            ("typescript", TypeScriptParser),
        ],
    )
    def test_returns_correct_parser(self, lang, cls):
        parser = get_parser_for_language(lang)
        assert isinstance(parser, cls)
        assert isinstance(parser, BaseParser)

    def test_unsupported_returns_none(self):
        assert get_parser_for_language("go") is None

    def test_parser_instances_are_cached(self):
        assert get_parser_for_language("python") is get_parser_for_language("python")
