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
