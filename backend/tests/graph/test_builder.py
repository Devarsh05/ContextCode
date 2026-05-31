import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.graph.builder import GraphBuilder, GraphBuildResult, resolve_import
from app.models.database import Base
from app.models.graph import FileDependency, FileNode
from app.models.repository import Repository


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sync_db(tmp_path):
    """Sync SQLite session with all tables — no Postgres required."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Factory = sessionmaker(engine, expire_on_commit=False)
    with Factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def repo_row(sync_db):
    repo = Repository(url="https://github.com/test/graph-repo", name="graph-repo")
    sync_db.add(repo)
    sync_db.commit()
    return repo


def _write(root, rel_path, content=""):
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return rel_path


def _deps(session, repo_id):
    return (
        session.execute(select(FileDependency).where(FileDependency.repo_id == repo_id))
        .scalars()
        .all()
    )


def _nodes(session, repo_id):
    return (
        session.execute(select(FileNode).where(FileNode.repo_id == repo_id))
        .scalars()
        .all()
    )


# ── Python fixture repo ─────────────────────────────────────────────────────

@pytest.fixture
def py_repo(tmp_path):
    """app/main.py imports os (3rd-party/stdlib), .utils, and .config."""
    _write(tmp_path, "app/main.py",
           "import os\n"
           "from .utils import helper\n"
           "from . import config\n")
    _write(tmp_path, "app/utils.py", "def helper():\n    pass\n")
    _write(tmp_path, "app/config.py", "VALUE = 1\n")
    files = ["app/main.py", "app/utils.py", "app/config.py"]
    return str(tmp_path), files


# ── resolve_import unit coverage ────────────────────────────────────────────

class TestResolveImport:
    def test_python_relative_from_module_strips_symbol(self):
        paths = {"app/main.py", "app/utils.py"}
        assert resolve_import("app/main.py", ".utils.helper", "/root", paths) == "app/utils.py"

    def test_python_relative_no_module(self):
        paths = {"app/main.py", "app/config.py"}
        assert resolve_import("app/main.py", ".config", "/root", paths) == "app/config.py"

    def test_python_absolute_unresolved_is_none(self):
        paths = {"app/main.py"}
        assert resolve_import("app/main.py", "os", "/root", paths) is None
        assert resolve_import("app/main.py", "requests.sessions", "/root", paths) is None

    def test_python_absolute_resolves_to_package(self):
        paths = {"app/main.py", "app/pkg/__init__.py"}
        assert resolve_import("app/main.py", "app.pkg", "/root", paths) == "app/pkg/__init__.py"

    def test_js_relative_with_suffix(self):
        paths = {"web/index.js", "web/util.js"}
        assert resolve_import("web/index.js", "./util", "/root", paths) == "web/util.js"

    def test_js_relative_index_file(self):
        paths = {"web/index.js", "web/lib/index.js"}
        assert resolve_import("web/index.js", "./lib", "/root", paths) == "web/lib/index.js"

    def test_js_bare_specifier_is_none(self):
        paths = {"web/index.js"}
        assert resolve_import("web/index.js", "react", "/root", paths) is None

    def test_never_raises_on_garbage(self):
        assert resolve_import("a.py", "", "/root", set()) is None


# ── GraphBuilder ─────────────────────────────────────────────────────────────

class TestPythonGraph:
    def test_nodes_and_dependencies_created(self, sync_db, repo_row, py_repo):
        repo_root, files = py_repo
        result = GraphBuilder(sync_db, repo_root, files).build(repo_row.id)

        nodes = _nodes(sync_db, repo_row.id)
        deps = _deps(sync_db, repo_row.id)
        assert {n.file_path for n in nodes} == set(files)
        # 3 import statements on main.py → 3 dependency rows.
        assert len(deps) == 3
        assert result.node_count == 3
        assert result.edge_count == 3

    def test_relative_import_resolves(self, sync_db, repo_row, py_repo):
        repo_root, files = py_repo
        GraphBuilder(sync_db, repo_root, files).build(repo_row.id)

        deps = _deps(sync_db, repo_row.id)
        resolved = {(d.source_file, d.target_file) for d in deps if d.target_file}
        assert ("app/main.py", "app/utils.py") in resolved
        assert ("app/main.py", "app/config.py") in resolved

    def test_unresolvable_import_has_none_target(self, sync_db, repo_row, py_repo):
        repo_root, files = py_repo
        result = GraphBuilder(sync_db, repo_root, files).build(repo_row.id)

        deps = _deps(sync_db, repo_row.id)
        os_dep = [d for d in deps if d.import_raw == "import os"]
        assert len(os_dep) == 1
        assert os_dep[0].target_file is None
        assert os_dep[0].import_raw == "import os"  # raw preserved
        assert result.unresolved_count == 1

    def test_import_and_imported_by_counts(self, sync_db, repo_row, py_repo):
        repo_root, files = py_repo
        GraphBuilder(sync_db, repo_root, files).build(repo_row.id)

        by_path = {n.file_path: n for n in _nodes(sync_db, repo_row.id)}
        assert by_path["app/main.py"].import_count == 2  # utils + config (os unresolved)
        assert by_path["app/main.py"].imported_by_count == 0
        assert by_path["app/utils.py"].imported_by_count == 1
        assert by_path["app/config.py"].imported_by_count == 1


class TestJavaScriptGraph:
    @pytest.fixture
    def js_repo(self, tmp_path):
        _write(tmp_path, "web/index.js",
               "import React from 'react';\n"
               "import { util } from './util';\n"
               "import helpers from './lib';\n")
        _write(tmp_path, "web/util.js", "export const util = 1;\n")
        _write(tmp_path, "web/lib/index.js", "export default {};\n")
        files = ["web/index.js", "web/util.js", "web/lib/index.js"]
        return str(tmp_path), files

    def test_relative_import_resolves(self, sync_db, repo_row, js_repo):
        repo_root, files = js_repo
        GraphBuilder(sync_db, repo_root, files).build(repo_row.id)

        deps = _deps(sync_db, repo_row.id)
        resolved = {(d.source_file, d.target_file) for d in deps if d.target_file}
        assert ("web/index.js", "web/util.js") in resolved
        assert ("web/index.js", "web/lib/index.js") in resolved

    def test_node_modules_import_is_none(self, sync_db, repo_row, js_repo):
        repo_root, files = js_repo
        GraphBuilder(sync_db, repo_root, files).build(repo_row.id)

        deps = _deps(sync_db, repo_row.id)
        react_dep = [d for d in deps if "react" in d.import_raw]
        assert len(react_dep) == 1
        assert react_dep[0].target_file is None


class TestIdempotency:
    def test_rebuild_replaces_rows(self, sync_db, repo_row, py_repo):
        repo_root, files = py_repo
        first = GraphBuilder(sync_db, repo_root, files).build(repo_row.id)
        second = GraphBuilder(sync_db, repo_root, files).build(repo_row.id)

        assert (second.node_count, second.edge_count, second.unresolved_count) == (
            first.node_count, first.edge_count, first.unresolved_count
        )
        # No accumulation across runs.
        assert len(_nodes(sync_db, repo_row.id)) == first.node_count
        assert len(_deps(sync_db, repo_row.id)) == first.edge_count


class TestErrorHandling:
    def test_missing_file_skipped_rest_built(self, sync_db, repo_row, tmp_path):
        _write(tmp_path, "app/main.py", "from .utils import helper\n")
        _write(tmp_path, "app/utils.py", "def helper():\n    pass\n")
        # ghost.py is in the file list but never written to disk.
        files = ["app/main.py", "app/utils.py", "app/ghost.py"]

        result = GraphBuilder(sync_db, str(tmp_path), files).build(repo_row.id)

        deps = _deps(sync_db, repo_row.id)
        resolved = {(d.source_file, d.target_file) for d in deps if d.target_file}
        # main.py's edge survived despite ghost.py read error.
        assert ("app/main.py", "app/utils.py") in resolved
        # ghost.py produced no dependency rows.
        assert all(d.source_file != "app/ghost.py" for d in deps)
        assert isinstance(result, GraphBuildResult)


class TestResultCounts:
    def test_counts_match_known_fixture(self, sync_db, repo_row, py_repo):
        repo_root, files = py_repo
        result = GraphBuilder(sync_db, repo_root, files).build(repo_row.id)

        assert result.node_count == len(_nodes(sync_db, repo_row.id))
        assert result.edge_count == len(_deps(sync_db, repo_row.id))
        assert result.unresolved_count == sum(
            1 for d in _deps(sync_db, repo_row.id) if d.target_file is None
        )
        assert (result.node_count, result.edge_count, result.unresolved_count) == (3, 3, 1)
