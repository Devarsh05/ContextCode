"""Base classes for Tree-sitter AST parsers.

Parsers turn raw source files into a list of ``ParsedChunk`` objects. A chunk is
one of:

- ``function`` — a top-level function (one chunk per function)
- ``class``    — a whole top-level class body (methods stay with their class)
- ``module``   — a single per-file chunk holding everything at module level that
  isn't a function or class (imports, top-level constants, docstrings, ...)

``ParsedChunk`` carries the fields of the future ``CodeChunk`` ORM model minus
``id``/``repo_id``; the caller (the Celery indexing task) assigns those.

Parsing is CPU-bound and runs inside the Celery worker, so this interface is
synchronous (see CLAUDE.md).
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedChunk:
    file_path: str
    chunk_type: str  # 'function' | 'class' | 'module'
    function_name: str | None  # None for module chunks; name for function/class
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    content: str
    language: str  # 'python' | 'javascript' | 'typescript'


class BaseParser(ABC):
    language: str = ""

    @abstractmethod
    def parse(self, file_path: str, content: str) -> list[ParsedChunk]:
        """Parse source into chunks. Must never raise — see TreeSitterParser."""


class TreeSitterParser(BaseParser):
    """Shared Tree-sitter walk, configured by subclass node-type sets.

    Subclasses set ``language``, ``FUNCTION_NODES``, ``CLASS_NODES`` and
    implement ``_build_language``. They may override ``_unwrap`` to peel
    wrapper nodes (decorators, exports) and ``_grammar_key`` when one parser
    serves multiple grammars (e.g. .ts vs .tsx).
    """

    FUNCTION_NODES: frozenset[str] = frozenset()
    CLASS_NODES: frozenset[str] = frozenset()

    def __init__(self) -> None:
        # Lazily built Tree-sitter parsers, keyed by grammar (mirrors the
        # lazy-load pattern in app/services/embeddings.py).
        self._parsers: dict[str, object] = {}

    # ----- subclass hooks -------------------------------------------------

    def _build_language(self, grammar_key: str):
        """Return the tree_sitter.Language for the given grammar key."""
        raise NotImplementedError

    def _grammar_key(self, file_path: str) -> str:
        """Which grammar to use for this file. Default: one per language."""
        return self.language

    def _unwrap(self, node):
        """Return the node to inspect for classification.

        Override to peel wrappers such as Python ``decorated_definition`` or
        JS ``export_statement`` so the inner def/class drives type and name,
        while the original (outer) node is still used for the chunk text.
        """
        return node

    # ----- core walk ------------------------------------------------------

    def _get_parser(self, file_path: str):
        key = self._grammar_key(file_path)
        if key not in self._parsers:
            from tree_sitter import Parser

            self._parsers[key] = Parser(self._build_language(key))
        return self._parsers[key]

    def _node_name(self, node) -> str | None:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return name_node.text.decode("utf8")
        return None

    def _classify(self, node) -> tuple[str | None, str | None]:
        """Return (chunk_type, function_name) for a top-level node, or
        (None, None) if it belongs in the module chunk."""
        inner = self._unwrap(node)
        if inner.type in self.FUNCTION_NODES:
            return "function", self._node_name(inner)
        if inner.type in self.CLASS_NODES:
            return "class", self._node_name(inner)
        return None, None

    def parse(self, file_path: str, content: str) -> list[ParsedChunk]:
        chunks: list[ParsedChunk] = []
        try:
            parser = self._get_parser(file_path)
            source_bytes = content.encode("utf8")
            tree = parser.parse(source_bytes)
            root = tree.root_node
            if root.has_error:
                logger.warning(
                    "Syntax errors while parsing %s; extracting best-effort chunks",
                    file_path,
                )

            module_nodes = []
            for node in root.named_children:
                chunk_type, function_name = self._classify(node)
                if chunk_type is not None:
                    # Use the original node so wrappers (decorators/exports)
                    # are included in the chunk text.
                    chunks.append(
                        self._make_chunk(file_path, node, chunk_type, function_name)
                    )
                else:
                    module_nodes.append(node)

            module_chunk = self._build_module_chunk(
                file_path, module_nodes, source_bytes
            )
            if module_chunk is not None:
                chunks.append(module_chunk)
        except Exception:  # defensive: a parser bug must not crash indexing
            logger.warning(
                "Failed to parse %s; returning %d partial chunk(s)",
                file_path,
                len(chunks),
                exc_info=True,
            )
        return chunks

    def _make_chunk(self, file_path, node, chunk_type, function_name) -> ParsedChunk:
        return ParsedChunk(
            file_path=file_path,
            chunk_type=chunk_type,
            function_name=function_name,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            content=node.text.decode("utf8"),
            language=self.language,
        )

    def _build_module_chunk(
        self, file_path, nodes, source_bytes
    ) -> ParsedChunk | None:
        if not nodes:
            return None  # empty / no top-level statements → no module chunk
        # Verbatim contiguous slice of the original source between the first and
        # last module-level node, so the content is always a substring of the
        # source (preserves blank lines / comments). When module nodes are
        # non-contiguous, this slice also includes the intervening text.
        content = source_bytes[nodes[0].start_byte : nodes[-1].end_byte].decode("utf8")
        return ParsedChunk(
            file_path=file_path,
            chunk_type="module",
            function_name=None,
            start_line=nodes[0].start_point[0] + 1,
            end_line=nodes[-1].end_point[0] + 1,
            content=content,
            language=self.language,
        )
