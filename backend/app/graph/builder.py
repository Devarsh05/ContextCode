"""Graph builder service.

Walks an already-cloned repo's files, runs the import extractors
(app/graph/extractors), resolves each import to a repo-relative file path
where possible, computes per-file in/out degree, and persists FileNode +
FileDependency rows.

CPU-bound and DB-bound — runs inside the Celery worker with a *synchronous*
SQLAlchemy session, mirroring run_indexing_pipeline in app/workers/tasks.py.

resolve_import is a pure module-level helper that never raises. build()
catches per-file errors, logs, and continues so a single bad file never
aborts the whole graph.
"""

import logging
import os
import posixpath
import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.graph.extractors.registry import get_extractor
from app.models.graph import FileDependency, FileNode
from app.parsers.registry import get_language_for_file

logger = logging.getLogger(__name__)

_PYTHON_EXTS = (".py",)
_JS_EXTS = (".js", ".jsx", ".ts", ".tsx")
# Suffix candidates tried for an extension-less JS/TS specifier.
_JS_SUFFIXES = (".js", ".ts", ".jsx", ".tsx")
_JS_INDEX = ("index.js", "index.ts")


@dataclass
class GraphBuildResult:
    node_count: int
    edge_count: int
    unresolved_count: int


def _norm(path: str) -> str:
    """Normalize a path to forward slashes (cross-platform comparison key)."""
    return path.replace("\\", "/")


def resolve_import(
    source_file: str,
    target_module: str,
    repo_root: str,
    all_file_paths,
) -> str | None:
    """Resolve an import to a repo-relative file path, or None.

    Routes Python vs JS/TS resolution by the importing file's extension.
    Never raises; returns a forward-slash repo-relative path on success.
    """
    try:
        path_set = (
            all_file_paths
            if isinstance(all_file_paths, (set, frozenset))
            else {_norm(p) for p in all_file_paths}
        )
        src = _norm(source_file)
        _, ext = os.path.splitext(src)
        ext = ext.lower()

        if ext in _PYTHON_EXTS:
            return _resolve_python(src, target_module, path_set)
        if ext in _JS_EXTS:
            return _resolve_js(src, target_module, path_set)
        return None
    except Exception:
        logger.warning(
            "resolve_import failed: source=%s target=%s", source_file, target_module,
            exc_info=True,
        )
        return None


def _resolve_python(src: str, target_module: str, path_set: set) -> str | None:
    if target_module.startswith("."):
        # Relative import: count leading dots = level.
        level = len(target_module) - len(target_module.lstrip("."))
        remainder = target_module[level:]
        # Base = source file's directory walked up (level - 1) parents.
        base = posixpath.dirname(src)
        for _ in range(level - 1):
            base = posixpath.dirname(base)
    else:
        # Absolute import: resolve from repo root.
        level = 0
        remainder = target_module
        base = ""

    segments = [s for s in remainder.split(".") if s and s != "*"]
    return _match_python_segments(base, segments, path_set)


def _match_python_segments(base: str, segments: list[str], path_set: set) -> str | None:
    """Try full dotted path, then symbol-stripped path, as .py / __init__.py."""
    # Candidate segment lists: full, then with the trailing symbol dropped.
    candidate_segs = [segments]
    if len(segments) > 1:
        candidate_segs.append(segments[:-1])

    for segs in candidate_segs:
        if not segs:
            # `from . import x` with x stripped → the package's __init__.py.
            stem = base
        else:
            stem = posixpath.join(base, *segs) if base else "/".join(segs)
        for cand in (f"{stem}.py", posixpath.join(stem, "__init__.py")):
            cand = _norm(posixpath.normpath(cand))
            if cand in path_set:
                return cand
    return None


def _resolve_js(src: str, target_module: str, path_set: set) -> str | None:
    if not target_module.startswith("."):
        # Bare specifier → node_modules / built-in. No edge.
        return None

    base = posixpath.dirname(src)
    resolved = _norm(posixpath.normpath(posixpath.join(base, target_module)))

    # Exact match (specifier already carried an extension).
    if resolved in path_set:
        return resolved
    # Try common source extensions.
    for suffix in _JS_SUFFIXES:
        cand = resolved + suffix
        if cand in path_set:
            return cand
    # Try directory index files.
    for index in _JS_INDEX:
        cand = _norm(posixpath.join(resolved, index))
        if cand in path_set:
            return cand
    return None


class GraphBuilder:
    def __init__(self, db_session: Session, repo_root: str, all_file_paths: list[str]):
        self._session = db_session
        self._repo_root = repo_root
        self._all_file_paths = all_file_paths
        # Normalized set for O(1) resolution lookups.
        self._path_set: set[str] = {_norm(p) for p in all_file_paths}

    def build(self, repo_id) -> GraphBuildResult:
        """Rebuild the dependency graph for repo_id. Never raises per-file."""
        repo_uuid = uuid.UUID(str(repo_id))
        session = self._session

        # 1. Drop any existing graph rows for this repo.
        session.execute(
            delete(FileDependency).where(FileDependency.repo_id == repo_uuid)
        )
        session.execute(delete(FileNode).where(FileNode.repo_id == repo_uuid))
        session.commit()

        import_count: Counter = Counter()
        imported_by_count: Counter = Counter()
        dep_rows: list[FileDependency] = []

        # 2. Extract + resolve imports per file.
        for file_path in self._all_file_paths:
            rel_path = _norm(file_path)
            try:
                extractor = get_extractor(rel_path)
                if extractor is None:
                    continue

                disk_path = os.path.join(self._repo_root, file_path)
                try:
                    with open(disk_path, encoding="utf-8", errors="replace") as fh:
                        source = fh.read()
                except OSError:
                    logger.warning("Read error on %s — skipping file", disk_path)
                    continue

                for edge in extractor.extract(rel_path, source):
                    target = resolve_import(
                        rel_path, edge.target_module, self._repo_root, self._path_set
                    )
                    dep_rows.append(
                        FileDependency(
                            repo_id=repo_uuid,
                            source_file=rel_path,
                            target_file=target,
                            import_raw=edge.import_raw,
                        )
                    )
                    if target is not None:
                        import_count[rel_path] += 1
                        imported_by_count[target] += 1
            except Exception:
                logger.warning(
                    "Graph build error on %s — skipping file", file_path, exc_info=True
                )

        # 3. One FileNode per code file (those with a known language).
        node_rows: list[FileNode] = []
        for file_path in self._all_file_paths:
            rel_path = _norm(file_path)
            language = get_language_for_file(rel_path)
            if language is None:
                continue
            node_rows.append(
                FileNode(
                    repo_id=repo_uuid,
                    file_path=rel_path,
                    language=language,
                    import_count=import_count.get(rel_path, 0),
                    imported_by_count=imported_by_count.get(rel_path, 0),
                )
            )

        # 4. Persist nodes + dependencies, then commit.
        session.add_all(node_rows)
        session.add_all(dep_rows)
        session.commit()

        unresolved = sum(1 for d in dep_rows if d.target_file is None)
        logger.info(
            "Graph built: repo_id=%s nodes=%d edges=%d unresolved=%d",
            repo_uuid, len(node_rows), len(dep_rows), unresolved,
        )
        return GraphBuildResult(
            node_count=len(node_rows),
            edge_count=len(dep_rows),
            unresolved_count=unresolved,
        )
