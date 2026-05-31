"""Base types for import extractors.

Extractors turn raw source into ImportEdge objects — one per imported
name (Python) or one per import statement (JavaScript/TypeScript).
Extraction is CPU-bound and runs synchronously inside the Celery worker.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportEdge:
    source_file: str    # repo-relative path of the file doing the importing
    import_raw: str     # verbatim (or reconstructed) import statement text
    target_module: str  # normalized dot-separated module path or specifier


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str, source_code: str) -> list[ImportEdge]:
        """Extract import edges from source_code. Must never raise."""
