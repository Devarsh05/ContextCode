import logging

from app.parsers.javascript_parser import JavaScriptParser
from app.parsers.python_parser import PythonParser


class TestEmptyAndTrivialFiles:
    def test_empty_file_yields_no_chunks(self):
        assert PythonParser().parse("empty.py", "") == []

    def test_whitespace_only_yields_no_chunks(self):
        assert PythonParser().parse("blank.py", "   \n\n  \n") == []

    def test_comment_only_file_has_no_function_or_class(self):
        chunks = PythonParser().parse("c.py", "# just a comment\n")
        assert all(c.chunk_type != "function" for c in chunks)


class TestSyntaxErrors:
    def test_python_syntax_error_does_not_crash(self, caplog):
        # broken function, but a valid one follows
        source = "def broken(:\n    pass\n\ndef ok():\n    return 1\n"
        with caplog.at_level(logging.WARNING):
            chunks = PythonParser().parse("bad.py", source)
        # never raises; extracts what it can
        names = [c.function_name for c in chunks if c.chunk_type == "function"]
        assert "ok" in names
        assert any("bad.py" in r.message for r in caplog.records)

    def test_javascript_syntax_error_does_not_crash(self):
        source = "function ok(){ return 1; }\nfunction broken( { \n"
        chunks = JavaScriptParser().parse("bad.js", source)
        names = [c.function_name for c in chunks if c.chunk_type == "function"]
        assert "ok" in names
