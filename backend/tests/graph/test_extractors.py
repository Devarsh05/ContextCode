import pytest
from dataclasses import FrozenInstanceError

from app.graph.extractors.base import BaseExtractor, ImportEdge
from app.graph.extractors.python_extractor import PythonExtractor


class TestImportEdgeDataclass:
    def test_fields_accessible(self):
        edge = ImportEdge(source_file="a.py", import_raw="import os", target_module="os")
        assert edge.source_file == "a.py"
        assert edge.import_raw == "import os"
        assert edge.target_module == "os"

    def test_frozen_raises_on_assignment(self):
        edge = ImportEdge(source_file="a.py", import_raw="import os", target_module="os")
        with pytest.raises((FrozenInstanceError, AttributeError)):
            edge.target_module = "changed"  # type: ignore

    def test_equality_by_value(self):
        e1 = ImportEdge("a.py", "import os", "os")
        e2 = ImportEdge("a.py", "import os", "os")
        assert e1 == e2

    def test_hashable(self):
        edge = ImportEdge("a.py", "import os", "os")
        s = {edge}
        assert len(s) == 1


class TestPythonExtractor:
    def test_simple_import(self):
        edges = PythonExtractor().extract("a.py", "import os")
        assert len(edges) == 1
        assert edges[0].source_file == "a.py"
        assert edges[0].target_module == "os"
        assert edges[0].import_raw == "import os"

    def test_dotted_import(self):
        edges = PythonExtractor().extract("a.py", "import foo.bar.baz")
        assert len(edges) == 1
        assert edges[0].target_module == "foo.bar.baz"
        assert edges[0].import_raw == "import foo.bar.baz"

    def test_multi_alias_import_yields_two_edges(self):
        edges = PythonExtractor().extract("a.py", "import foo, bar")
        assert len(edges) == 2
        targets = {e.target_module for e in edges}
        assert targets == {"foo", "bar"}
        # Both edges share the same import_raw
        assert {e.import_raw for e in edges} == {"import foo, bar"}

    def test_from_import_single(self):
        edges = PythonExtractor().extract("a.py", "from foo import bar")
        assert len(edges) == 1
        assert edges[0].target_module == "foo.bar"
        assert edges[0].import_raw == "from foo import bar"

    def test_from_import_multi_yields_two_edges(self):
        edges = PythonExtractor().extract("a.py", "from foo import bar, baz")
        assert len(edges) == 2
        targets = {e.target_module for e in edges}
        assert targets == {"foo.bar", "foo.baz"}
        # Both edges share the same import_raw
        assert len({e.import_raw for e in edges}) == 1

    def test_from_import_aliased(self):
        # import_raw includes the alias; target_module uses the real name
        edges = PythonExtractor().extract("a.py", "from foo import bar as b")
        assert len(edges) == 1
        assert edges[0].target_module == "foo.bar"
        assert "bar as b" in edges[0].import_raw

    def test_relative_import_with_module(self):
        edges = PythonExtractor().extract("pkg/a.py", "from .relative import x")
        assert len(edges) == 1
        assert edges[0].target_module == ".relative.x"
        assert edges[0].import_raw == "from .relative import x"

    def test_relative_import_no_module(self):
        # from . import foo → level=1, module=None → target ".foo"
        edges = PythonExtractor().extract("pkg/a.py", "from . import foo")
        assert len(edges) == 1
        assert edges[0].target_module == ".foo"

    def test_double_relative_import(self):
        # from .. import bar → level=2, module=None → target "..bar"
        edges = PythonExtractor().extract("pkg/sub/a.py", "from .. import bar")
        assert len(edges) == 1
        assert edges[0].target_module == "..bar"

    def test_star_import(self):
        edges = PythonExtractor().extract("a.py", "from foo import *")
        assert len(edges) == 1
        assert edges[0].target_module == "foo.*"

    def test_parenthesized_from_import(self):
        source = "from foo import (\n    bar,\n    baz,\n)"
        edges = PythonExtractor().extract("a.py", source)
        targets = {e.target_module for e in edges}
        assert "foo.bar" in targets
        assert "foo.baz" in targets

    def test_syntax_error_returns_empty_with_warning(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="app.graph.extractors.python_extractor"):
            edges = PythonExtractor().extract("bad.py", "import (")
        assert edges == []
        assert any("bad.py" in r.message for r in caplog.records)

    def test_empty_file_returns_empty(self):
        assert PythonExtractor().extract("a.py", "") == []

    def test_no_imports_returns_empty(self):
        assert PythonExtractor().extract("a.py", "x = 1\nprint(x)") == []
