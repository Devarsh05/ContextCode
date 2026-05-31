import pytest
from dataclasses import FrozenInstanceError

from app.graph.extractors.base import BaseExtractor, ImportEdge


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
