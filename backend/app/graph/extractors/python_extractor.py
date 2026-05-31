"""Python import extractor using the stdlib ast module.

Produces one ImportEdge per imported name:
  - `import foo, bar`           → two edges, target_module "foo" and "bar"
  - `from foo import bar, baz`  → two edges, "foo.bar" and "foo.baz"
  - `from .relative import x`   → one edge, ".relative.x"
  - `from . import foo`         → one edge, ".foo"
  - `from foo import *`         → one edge, "foo.*"

import_raw is reconstructed from AST fields (not verbatim source text).
Uses ast.walk so imports inside `if TYPE_CHECKING:` blocks are included.
Never raises — logs a warning on SyntaxError and returns [].
"""

import ast
import logging

from app.graph.extractors.base import BaseExtractor, ImportEdge

logger = logging.getLogger(__name__)


class PythonExtractor(BaseExtractor):
    def extract(self, file_path: str, source_code: str) -> list[ImportEdge]:
        edges: list[ImportEdge] = []
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as exc:
            logger.warning("SyntaxError extracting imports from %s: %s", file_path, exc)
            return edges

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                raw = _reconstruct_import(node)
                for alias in node.names:
                    edges.append(ImportEdge(
                        source_file=file_path,
                        import_raw=raw,
                        target_module=alias.name,
                    ))
            elif isinstance(node, ast.ImportFrom):
                raw = _reconstruct_from_import(node)
                base = _base_module(node)
                for alias in node.names:
                    edges.append(ImportEdge(
                        source_file=file_path,
                        import_raw=raw,
                        target_module=_target_for_alias(base, alias),
                    ))
        return edges


def _reconstruct_import(node: ast.Import) -> str:
    parts = [
        f"{a.name} as {a.asname}" if a.asname else a.name
        for a in node.names
    ]
    return "import " + ", ".join(parts)


def _reconstruct_from_import(node: ast.ImportFrom) -> str:
    module_part = "." * (node.level or 0) + (node.module or "")
    names_part = ", ".join(
        f"{a.name} as {a.asname}" if a.asname else a.name
        for a in node.names
    )
    return f"from {module_part} import {names_part}"


def _base_module(node: ast.ImportFrom) -> str:
    """Return the dot-prefix + module string, e.g. '.pkg', '..', 'foo'."""
    return "." * (node.level or 0) + (node.module or "")


def _target_for_alias(base: str, alias: ast.alias) -> str:
    """Combine base module path with a single imported name.

    Handles the `from . import foo` case where base ends with '.' —
    concatenate directly to avoid producing '..foo' instead of '.foo'.
    """
    name = alias.name
    if name == "*":
        return base + ".*"
    if base.endswith("."):
        # relative-only (level > 0, no module): from . import foo → ".foo"
        return base + name
    if base:
        return base + "." + name
    return name
