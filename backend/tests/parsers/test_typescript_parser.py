from app.parsers.typescript_parser import TypeScriptParser


class TestTypeScriptParser:
    def test_function_arrow_and_class_like_javascript(self):
        source = (
            "import { Req } from './types';\n"
            "\n"
            "function add(a: number, b: number): number {\n"
            "  return a + b;\n"
            "}\n"
            "\n"
            "const mul = (a: number, b: number): number => a * b;\n"
            "\n"
            "class Box {\n"
            "  area(): number { return 1; }\n"
            "}\n"
        )
        chunks = TypeScriptParser().parse("sample.ts", source)
        fns = sorted(c.function_name for c in chunks if c.chunk_type == "function")
        classes = [c.function_name for c in chunks if c.chunk_type == "class"]
        assert fns == ["add", "mul"]
        assert classes == ["Box"]
        assert all(c.language == "typescript" for c in chunks)

    def test_chunk_content_is_substring_of_source(self):
        source = (
            "import { Req } from './types';\n"
            "\n"
            "type Id = string | number;\n"
            "\n"
            "function add(a: number, b: number): number {\n"
            "  return a + b;\n"
            "}\n"
            "\n"
            "class Box {\n"
            "  area(): number { return 1; }\n"
            "}\n"
        )
        chunks = TypeScriptParser().parse("test.ts", source)
        assert chunks
        for c in chunks:
            assert c.content in source, (
                f"{c.chunk_type} chunk content is not a verbatim slice of source"
            )

    def test_module_chunk_does_not_overlap_function_or_class_chunks(self):
        # import + interface at L1-3 (module), class at L5-7, const PI at L9 (module).
        # Interfaces stay in the module chunk; the overlap invariant still holds.
        source = (
            "import { Req } from './t';\n"       # L1  module
            "\n"
            "interface User { id: number }\n"   # L3  module (no dedicated chunk)
            "\n"
            "class Box {\n"                      # L5  class
            "  area(): number { return 1; }\n"  # L6
            "}\n"                                # L7
            "\n"
            "const PI = 3.14;\n"               # L9  module (after class)
        )
        chunks = TypeScriptParser().parse("interleaved.ts", source)
        module_lines: set[int] = set()
        other_lines: set[int] = set()
        for c in chunks:
            line_range = range(c.start_line, c.end_line + 1)
            if c.chunk_type == "module":
                module_lines.update(line_range)
            else:
                other_lines.update(line_range)
        overlap = module_lines & other_lines
        assert not overlap, (
            f"module chunk overlaps function/class on lines {sorted(overlap)}"
        )
        for c in chunks:
            assert c.content in source, (
                f"{c.chunk_type} chunk content is not a verbatim slice of source"
            )

    def test_interface_and_type_alias_stay_in_module_chunk(self):
        source = (
            "interface User {\n"
            "  id: number;\n"
            "  name: string;\n"
            "}\n"
            "\n"
            "type Id = string | number;\n"
            "\n"
            "function noop(): void {}\n"
        )
        chunks = TypeScriptParser().parse("types.ts", source)

        # interfaces/types do NOT get their own chunk...
        types = [c for c in chunks if c.function_name in ("User", "Id")]
        assert types == []
        # ...but their source IS preserved in the single module chunk so it
        # stays searchable via RAG.
        module = next(c for c in chunks if c.chunk_type == "module")
        assert "interface User" in module.content
        assert "type Id = string | number;" in module.content

        # the real function is still extracted
        assert [c.function_name for c in chunks if c.chunk_type == "function"] == [
            "noop"
        ]

    def test_tsx_grammar_parses_jsx_component(self):
        source = (
            "export const Button = () => {\n"
            "  return <button>Click</button>;\n"
            "};\n"
        )
        chunks = TypeScriptParser().parse("Button.tsx", source)
        fns = [c for c in chunks if c.chunk_type == "function"]
        assert len(fns) == 1
        assert fns[0].function_name == "Button"
