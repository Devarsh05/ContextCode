from app.parsers.javascript_parser import JavaScriptParser


def _names_by_type(chunks):
    out = {}
    for c in chunks:
        out.setdefault(c.chunk_type, []).append(c.function_name)
    return out


class TestJavaScriptParser:
    def test_function_declaration_arrow_const_and_class(self):
        source = (
            "import { x } from './x';\n"
            "\n"
            "const PI = 3.14;\n"
            "\n"
            "function add(a, b) {\n"
            "  return a + b;\n"
            "}\n"
            "\n"
            "const mul = (a, b) => {\n"
            "  return a * b;\n"
            "};\n"
            "\n"
            "class Box {\n"
            "  area() { return 1; }\n"
            "}\n"
        )
        chunks = JavaScriptParser().parse("sample.js", source)
        names = _names_by_type(chunks)

        assert sorted(names.get("function", [])) == ["add", "mul"]
        assert names.get("class") == ["Box"]
        # imports + top-level const PI land in the single module chunk
        assert "module" in names
        module = next(c for c in chunks if c.chunk_type == "module")
        assert "import { x }" in module.content
        assert "const PI = 3.14;" in module.content
        assert "function add" not in module.content

    def test_chunk_content_is_substring_of_source(self):
        source = (
            "import { x } from './x';\n"
            "\n"
            "const PI = 3.14;\n"
            "\n"
            "function add(a, b) {\n"
            "  return a + b;\n"
            "}\n"
            "\n"
            "class Box {\n"
            "  area() { return 1; }\n"
            "}\n"
        )
        chunks = JavaScriptParser().parse("test.js", source)
        assert chunks
        for c in chunks:
            assert c.content in source, (
                f"{c.chunk_type} chunk content is not a verbatim slice of source"
            )

    def test_export_const_arrow(self):
        source = "export const handler = (req, res) => {\n  res.end();\n};\n"
        chunks = JavaScriptParser().parse("h.js", source)
        fns = [c for c in chunks if c.chunk_type == "function"]
        assert len(fns) == 1
        assert fns[0].function_name == "handler"
        assert fns[0].content.startswith("export const handler")

    def test_export_function_declaration(self):
        source = "export function run() {\n  return 7;\n}\n"
        chunks = JavaScriptParser().parse("r.js", source)
        fns = [c for c in chunks if c.chunk_type == "function"]
        assert len(fns) == 1
        assert fns[0].function_name == "run"
        assert fns[0].language == "javascript"

    def test_plain_const_object_is_module_not_function(self):
        source = "const config = { port: 3000 };\n"
        chunks = JavaScriptParser().parse("c.js", source)
        assert [c.chunk_type for c in chunks] == ["module"]
