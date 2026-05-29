"""Tree-sitter parser for TypeScript source (.ts / .tsx).

Reuses all JavaScript chunking logic (function_declaration, class_declaration,
arrow/function assigned to const, export unwrapping). The only differences:

- Grammar is chosen per file: ``.tsx`` uses the TSX grammar (so JSX parses),
  everything else uses the plain TypeScript grammar.
- ``interface_declaration`` and ``type_alias_declaration`` are NOT executable
  code, so they get no dedicated chunk. They fall through ``_classify`` like any
  other top-level statement and are therefore folded into the single ``module``
  chunk — keeping the type definitions searchable via RAG without inflating the
  function/class chunk count. (Decision per planning step.)
"""

from app.parsers.javascript_parser import JavaScriptParser


class TypeScriptParser(JavaScriptParser):
    language = "typescript"

    def _grammar_key(self, file_path: str) -> str:
        return "tsx" if file_path.endswith(".tsx") else "typescript"

    def _build_language(self, grammar_key: str):
        import tree_sitter_typescript as tstypescript
        from tree_sitter import Language

        if grammar_key == "tsx":
            return Language(tstypescript.language_tsx())
        return Language(tstypescript.language_typescript())
