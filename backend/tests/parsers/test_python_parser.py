from app.parsers.python_parser import PythonParser


def _by_type(chunks):
    return {c.chunk_type: c for c in chunks}


class TestPythonParser:
    def test_function_class_and_module_chunks(self):
        source = (
            "import os\n"
            "from sys import argv\n"
            "\n"
            "TIMEOUT = 30\n"
            "\n"
            "def greet(name):\n"
            "    return f'hi {name}'\n"
            "\n"
            "class Widget:\n"
            "    def render(self):\n"
            "        return 1\n"
        )
        chunks = PythonParser().parse("sample.py", source)

        by_type = _by_type(chunks)
        assert set(by_type) == {"module", "function", "class"}
        assert len(chunks) == 3

        assert by_type["function"].function_name == "greet"
        assert by_type["function"].language == "python"
        assert by_type["function"].file_path == "sample.py"

        assert by_type["class"].function_name == "Widget"
        # whole class body is one chunk, methods not split out
        assert "def render" in by_type["class"].content

        # module chunk holds imports + top-level constant, no function name
        assert by_type["module"].function_name is None
        assert "import os" in by_type["module"].content
        assert "TIMEOUT = 30" in by_type["module"].content

    def test_line_ranges_are_one_indexed(self):
        source = "def foo():\n    return 1\n"
        chunks = PythonParser().parse("f.py", source)
        fn = _by_type(chunks)["function"]
        assert fn.start_line == 1
        assert fn.end_line == 2

    def test_chunk_content_is_substring_of_source(self):
        source = (
            "import os\n"
            "from sys import argv\n"
            "\n"
            "TIMEOUT = 30\n"
            "\n"
            "def greet(name):\n"
            "    return f'hi {name}'\n"
            "\n"
            "class Widget:\n"
            "    def render(self):\n"
            "        return 1\n"
        )
        chunks = PythonParser().parse("test.py", source)
        assert chunks
        for c in chunks:
            assert c.content in source, (
                f"{c.chunk_type} chunk content is not a verbatim slice of source"
            )

    def test_module_chunk_does_not_overlap_function_or_class_chunks(self):
        # Module nodes at L1, L6, L11 — interleaved with class (L3-4) and
        # function (L8-9). The current first-to-last byte slice would span
        # L1-11, eating through both. After the fix each contiguous run of
        # module nodes becomes its own chunk.
        source = (
            "import os\n"       # L1  module
            "\n"
            "class Foo:\n"      # L3  class
            "    x = 1\n"       # L4
            "\n"
            "X = 10\n"          # L6  module (after class)
            "\n"
            "def bar():\n"      # L8  function
            "    return 1\n"    # L9
            "\n"
            "Y = 20\n"          # L11 module (after function)
        )
        chunks = PythonParser().parse("interleaved.py", source)
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
        # substring invariant must also hold for each interleaved chunk
        for c in chunks:
            assert c.content in source, (
                f"{c.chunk_type} chunk content is not a verbatim slice of source"
            )

    def test_decorated_function_includes_decorator(self):
        source = (
            "import functools\n"
            "\n"
            "@functools.cache\n"
            "def cached():\n"
            "    return 42\n"
        )
        chunks = PythonParser().parse("d.py", source)
        fn = _by_type(chunks)["function"]
        assert fn.function_name == "cached"
        assert "@functools.cache" in fn.content
