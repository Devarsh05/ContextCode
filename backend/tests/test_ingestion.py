"""
Unit tests for IngestionService.

All tests are synchronous (no DB, no network).
Uses tmp_path for filesystem operations.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.ingestion import IngestionService


# ── validate_github_url ────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://github.com/owner/repo",
    "https://github.com/my-org/my.repo",
    "https://github.com/user123/project_name",
    "https://github.com/owner/repo/",          # trailing slash OK
])
def test_validate_github_url_accepts_valid(url):
    IngestionService.validate_github_url(url)  # must not raise


@pytest.mark.parametrize("url", [
    "http://github.com/owner/repo",             # http, not https
    "https://gitlab.com/owner/repo",            # wrong host
    "https://github.com/owner",                 # missing repo
    "https://github.com/owner/repo/extra",      # extra path segments
    "not-a-url",
    "",
])
def test_validate_github_url_rejects_invalid(url):
    with pytest.raises(ValueError):
        IngestionService.validate_github_url(url)


# ── clone_repository ───────────────────────────────────────────────────────────

def test_clone_repository_calls_gitpython_with_correct_args(tmp_path):
    dest = str(tmp_path / "dest")
    with patch("git.Repo.clone_from") as mock_clone:
        result = IngestionService.clone_repository("https://github.com/org/repo", dest)

    mock_clone.assert_called_once_with(
        "https://github.com/org/repo",
        dest,
        depth=1,
        single_branch=True,
    )
    assert result == dest


def test_clone_repository_propagates_git_errors(tmp_path):
    import git

    dest = str(tmp_path / "dest")
    with patch("git.Repo.clone_from", side_effect=git.GitCommandError("clone", 128)):
        with pytest.raises(git.GitCommandError):
            IngestionService.clone_repository("https://github.com/org/repo", dest)


# ── walk_repository ────────────────────────────────────────────────────────────

def test_walk_repository_yields_text_files(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# readme")

    results = list(IngestionService.walk_repository(str(tmp_path)))
    names = {Path(p).name for p in results}

    assert "main.py" in names
    assert "README.md" in names


def test_walk_repository_skips_node_modules(tmp_path):
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "lodash.js").write_text("module.exports = {}")
    (tmp_path / "index.js").write_text("const x = 1")

    results = list(IngestionService.walk_repository(str(tmp_path)))
    names = {Path(p).name for p in results}

    assert "lodash.js" not in names
    assert "index.js" in names


@pytest.mark.parametrize("skip_dir", ["dist", "build", ".git"])
def test_walk_repository_skips_excluded_dirs(tmp_path, skip_dir):
    d = tmp_path / skip_dir
    d.mkdir()
    (d / "output.js").write_text("bundled")
    (tmp_path / "src.py").write_text("x = 1")

    results = list(IngestionService.walk_repository(str(tmp_path)))
    names = {Path(p).name for p in results}

    assert "output.js" not in names
    assert "src.py" in names


def test_walk_repository_skips_binary_extensions(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "archive.zip").write_bytes(b"PK\x03\x04")
    (tmp_path / "code.py").write_text("x = 1")

    results = list(IngestionService.walk_repository(str(tmp_path)))
    names = {Path(p).name for p in results}

    assert "image.png" not in names
    assert "archive.zip" not in names
    assert "code.py" in names


def test_walk_repository_skips_null_byte_files(tmp_path):
    binary_file = tmp_path / "data.bin"
    binary_file.write_bytes(b"some text\x00more bytes")  # contains null byte
    (tmp_path / "text.txt").write_text("normal text")

    results = list(IngestionService.walk_repository(str(tmp_path)))
    names = {Path(p).name for p in results}

    assert "data.bin" not in names
    assert "text.txt" in names


def test_walk_repository_yields_absolute_paths(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")

    results = list(IngestionService.walk_repository(str(tmp_path)))

    assert len(results) == 1
    assert Path(results[0]).is_absolute()


# ── enforce_size_limits ────────────────────────────────────────────────────────

def test_enforce_size_limits_passes_for_small_repo(tmp_path):
    for i in range(10):
        (tmp_path / f"file{i}.py").write_text(f"x = {i}")

    IngestionService.enforce_size_limits(str(tmp_path))  # must not raise


def test_enforce_size_limits_raises_on_file_count(tmp_path):
    # Mock os.walk so no real files are created on disk.
    fake_walk = [(str(tmp_path), [], [f"file{i}.txt" for i in range(10_001)])]
    with patch("os.walk", return_value=fake_walk), \
         patch("os.path.getsize", return_value=0):
        with pytest.raises(ValueError, match="10,0"):
            IngestionService.enforce_size_limits(str(tmp_path))


def test_enforce_size_limits_raises_on_total_size(tmp_path):
    # Mock os.walk and os.path.getsize — no 501 MB file written to disk.
    fake_walk = [(str(tmp_path), [], ["big.bin"])]
    with patch("os.walk", return_value=fake_walk), \
         patch("os.path.getsize", return_value=501 * 1024 * 1024):
        with pytest.raises(ValueError, match="500 MB"):
            IngestionService.enforce_size_limits(str(tmp_path))


def test_enforce_size_limits_skips_excluded_dirs(tmp_path):
    nm = tmp_path / "node_modules"
    nm.mkdir()
    # Put 10_001 files in node_modules — should not trigger limit.
    for i in range(10_001):
        (nm / f"pkg{i}.js").write_bytes(b"x")
    (tmp_path / "main.py").write_text("x = 1")

    IngestionService.enforce_size_limits(str(tmp_path))  # must not raise
