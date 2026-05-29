"""Tree-sitter parser for JavaScript source (.js / .jsx).

Node types:
- ``function_declaration`` / ``generator_function_declaration`` → function chunk
- ``class_declaration`` → class chunk
- ``lexical_declaration`` / ``variable_declaration`` whose single declarator's
  value is an ``arrow_function`` or ``function_expression`` (i.e.
  ``const foo = () => {...}``) → function chunk named after the binding.
- ``export_statement`` wrappers are peeled so the inner declaration drives the
  type/name, while the chunk text keeps the ``export`` prefix.
- everything else at module level (imports, plain consts, expression
  statements) → the single ``module`` chunk.
"""

from app.parsers.base import TreeSitterParser

# Sentinel: the node is not a "function assigned to a const/let".
_NOT_ARROW = object()


class JavaScriptParser(TreeSitterParser):
    language = "javascript"
    FUNCTION_NODES = frozenset({"function_declaration", "generator_function_declaration"})
    CLASS_NODES = frozenset({"class_declaration"})
    _DECL_NODES = frozenset({"lexical_declaration", "variable_declaration"})
    _FUNCTION_VALUES = frozenset({"arrow_function", "function_expression"})

    def _build_language(self, grammar_key: str):
        import tree_sitter_javascript as tsjavascript
        from tree_sitter import Language

        return Language(tsjavascript.language())

    def _unwrap(self, node):
        if node.type == "export_statement":
            inner = node.child_by_field_name("declaration") or node.child_by_field_name(
                "value"
            )
            if inner is not None:
                return inner
        return node

    def _classify(self, node) -> tuple[str | None, str | None]:
        inner = self._unwrap(node)
        if inner.type in self.FUNCTION_NODES:
            return "function", self._node_name(inner)
        if inner.type in self.CLASS_NODES:
            return "class", self._node_name(inner)
        # `export default function () {}` / `export default () => {}` — anonymous
        if inner.type in self._FUNCTION_VALUES:
            return "function", None
        # `const foo = () => {}` / `const foo = function () {}`
        if inner.type in self._DECL_NODES:
            name = self._arrow_const_name(inner)
            if name is not _NOT_ARROW:
                return "function", name
        return None, None

    def _arrow_const_name(self, decl):
        declarators = [
            c for c in decl.named_children if c.type == "variable_declarator"
        ]
        if len(declarators) != 1:
            return _NOT_ARROW
        value = declarators[0].child_by_field_name("value")
        if value is not None and value.type in self._FUNCTION_VALUES:
            name_node = declarators[0].child_by_field_name("name")
            return name_node.text.decode("utf8") if name_node is not None else None
        return _NOT_ARROW
