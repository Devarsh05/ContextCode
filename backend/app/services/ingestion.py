import os
import re
from pathlib import Path

import git

SKIP_DIRS: frozenset[str] = frozenset({"node_modules", "dist", "build", ".git"})

BINARY_EXTENSIONS: frozenset[str] = frozenset({
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    # Documents
    ".pdf",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    # Compiled / executables
    ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm", ".o", ".a",
    # Python bytecode
    ".pyc", ".pyo",
    # JVM
    ".class", ".jar", ".war",
    # Media
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac", ".mkv", ".webm",
    # Fonts
    ".ttf", ".woff", ".woff2", ".eot", ".otf",
    # Databases
    ".db", ".sqlite", ".sqlite3",
})

# Matches exactly: https://github.com/<owner>/<repo> with optional trailing slash.
# Owner/repo must consist of alphanumerics, hyphens, underscores, or dots.
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$"
)

_MAX_FILES = 10_000
_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


class IngestionService:
    @staticmethod
    def validate_github_url(url: str) -> None:
        """Raise ValueError if url is not a valid public GitHub repository URL."""
        if not _GITHUB_URL_RE.match(url):
            raise ValueError(
                f"Invalid GitHub URL {url!r}. "
                "Expected format: https://github.com/owner/repo"
            )

    @staticmethod
    def clone_repository(url: str, dest_dir: str) -> str:
        """
        Shallow-clone (depth=1, single branch) url into dest_dir.

        dest_dir must exist and be empty (TemporaryDirectory satisfies this).
        Returns dest_dir for convenience.
        """
        git.Repo.clone_from(url, dest_dir, depth=1, single_branch=True)
        return dest_dir

    @staticmethod
    def walk_repository(repo_path: str):
        """
        Yield absolute paths of indexable files under repo_path.

        Skips:
        - Directories in SKIP_DIRS (node_modules, dist, build, .git)
        - Files whose extension is in BINARY_EXTENSIONS
        - Files whose first 1024 bytes contain a null byte
        """
        for dirpath, dirnames, filenames in os.walk(repo_path):
            # Prune excluded directories in-place so os.walk won't descend.
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)

                # Extension check (fast path).
                ext = Path(filename).suffix.lower()
                if ext in BINARY_EXTENSIONS:
                    continue

                # Null-byte sniff for binaries without a recognised extension.
                try:
                    with open(filepath, "rb") as fh:
                        chunk = fh.read(1024)
                    if b"\x00" in chunk:
                        continue
                except OSError:
                    continue

                yield filepath

    @staticmethod
    def enforce_size_limits(repo_path: str) -> None:
        """
        Raise ValueError if the repository exceeds 10,000 files or 500 MB.

        Applies the same SKIP_DIRS as walk_repository so that node_modules
        etc. do not inflate the count.
        """
        total_files = 0
        total_bytes = 0

        for dirpath, dirnames, filenames in os.walk(repo_path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            total_files += len(filenames)
            for filename in filenames:
                try:
                    total_bytes += os.path.getsize(
                        os.path.join(dirpath, filename)
                    )
                except OSError:
                    pass

        if total_files > _MAX_FILES:
            raise ValueError(
                f"Repository has {total_files:,} files, "
                f"exceeding the 10,000 file limit."
            )
        if total_bytes > _MAX_BYTES:
            raise ValueError(
                f"Repository is {total_bytes // (1024 ** 2)} MB, "
                f"exceeding the 500 MB limit."
            )
