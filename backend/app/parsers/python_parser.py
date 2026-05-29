"""Tree-sitter parser for Python source.

Node types:
- ``function_definition`` → function chunk
- ``class_definition``    → class chunk (whole body; methods stay with the class)
- ``decorated_definition`` wraps a decorated function/class; the chunk includes
  the decorator lines, while type and name come from the inner definition.
- everything else at module level (imports, top-level constants, the module
  docstring, ``if __name__ == ...`` blocks) → the single ``module`` chunk.
"""

from app.parsers.base import TreeSitterParser


class PythonParser(TreeSitterParser):
    language = "python"
    FUNCTION_NODES = frozenset({"function_definition"})
    CLASS_NODES = frozenset({"class_definition"})

    def _build_language(self, grammar_key: str):
        import tree_sitter_python as tspython
        from tree_sitter import Language

        return Language(tspython.language())

    def _unwrap(self, node):
        if node.type == "decorated_definition":
            inner = node.child_by_field_name("definition")
            if inner is not None:
                return inner
        return node
