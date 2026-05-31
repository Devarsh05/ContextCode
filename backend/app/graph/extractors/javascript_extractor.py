"""JavaScript/TypeScript import extractor using regular expressions.

Produces one ImportEdge per import *statement* (not per imported symbol).
import_raw = the full matched text (match.group(0)).
target_module = the raw module specifier string ("./foo", "react", etc.).
Path resolution (relative → absolute repo path) is the graph builder's job.

Handles .js, .jsx, .ts, .tsx — no grammar difference at extraction time.

Patterns covered:
  import foo from './foo'             → static default
  import { bar, baz } from '../lib'   → static named
  import * as x from './x'           → static namespace
  import 'side-effect'               → side-effect (no from clause)
  import('./dynamic')                 → dynamic import
  require('./something')              → CommonJS require
  export { x } from './other'        → re-export named
  export * from './other'            → re-export star
"""

import re
import logging

from app.graph.extractors.base import BaseExtractor, ImportEdge

logger = logging.getLogger(__name__)

# Static ESM import: import [ clause from ] 'specifier'
# Uses [ \t]+ (not \s+) so import() with no space is not consumed here.
# Negative lookahead (?![(]) guards against `import (` with a space before (.
_STATIC_IMPORT_RE = re.compile(
    r"""import[ \t]+(?![(])(?:(?:[\w$*{][^;'"]*?)[ \t]+from[ \t]+)?['"][^'"]+['"]""",
    re.MULTILINE,
)

# Dynamic: import('specifier') or import( 'specifier' )
_DYNAMIC_IMPORT_RE = re.compile(
    r"""import\s*\(\s*['"][^'"]+['"]\s*\)""",
    re.MULTILINE,
)

# CommonJS require — lookbehind prevents matching obj.require(...)
_REQUIRE_RE = re.compile(
    r"""(?<![.\w])require\s*\(\s*['"][^'"]+['"]\s*\)""",
    re.MULTILINE,
)

# Re-export: export * from '...' or export { ... } from '...'
_REEXPORT_RE = re.compile(
    r"""export[ \t]+(?:\*|\{[^}]*\})[ \t]+from[ \t]+['"][^'"]+['"]""",
    re.MULTILINE,
)

# Extracts the specifier string from an already-matched import_raw
_SPECIFIER_RE = re.compile(r"""['"]([^'"]+)['"]""")

_ALL_PATTERNS = [
    _STATIC_IMPORT_RE,
    _DYNAMIC_IMPORT_RE,
    _REQUIRE_RE,
    _REEXPORT_RE,
]


class JavaScriptExtractor(BaseExtractor):
    def extract(self, file_path: str, source_code: str) -> list[ImportEdge]:
        # Collect (start_offset, ImportEdge); dedup by span to prevent two
        # patterns claiming the same text region.
        seen_spans: set[tuple[int, int]] = set()
        collected: list[tuple[int, ImportEdge]] = []

        for pattern in _ALL_PATTERNS:
            for match in pattern.finditer(source_code):
                span = match.span()
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                raw = match.group(0)
                specifier_match = _SPECIFIER_RE.search(raw)
                target = specifier_match.group(1) if specifier_match else raw
                collected.append((match.start(), ImportEdge(
                    source_file=file_path,
                    import_raw=raw,
                    target_module=target,
                )))

        collected.sort(key=lambda x: x[0])
        return [edge for _, edge in collected]
