import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.graph import FileDependency, FileNode
from app.models.repository import Repository


async def test_create_file_node(db_session):
    repo = Repository(url="https://github.com/org/fn-repo", name="fn-repo")
    db_session.add(repo)
    await db_session.flush()

    node = FileNode(repo_id=repo.id, file_path="src/main.py", language="python")
    db_session.add(node)
    await db_session.flush()
    await db_session.refresh(node)

    assert isinstance(node.id, uuid.UUID)
    assert node.repo_id == repo.id
    assert node.file_path == "src/main.py"
    assert node.language == "python"
    assert node.import_count == 0
    assert node.imported_by_count == 0
    assert node.created_at is not None


async def test_create_file_dependency(db_session):
    repo = Repository(url="https://github.com/org/fd-repo", name="fd-repo")
    db_session.add(repo)
    await db_session.flush()

    dep = FileDependency(
        repo_id=repo.id,
        source_file="src/main.py",
        target_file="src/utils.py",
        import_raw="from src import utils",
    )
    db_session.add(dep)
    await db_session.flush()
    await db_session.refresh(dep)

    assert isinstance(dep.id, uuid.UUID)
    assert dep.repo_id == repo.id
    assert dep.source_file == "src/main.py"
    assert dep.target_file == "src/utils.py"
    assert dep.import_raw == "from src import utils"
    assert dep.created_at is not None


async def test_cascade_delete_removes_file_nodes_and_dependencies(db_session):
    repo = Repository(url="https://github.com/org/cascade-repo", name="cascade-repo")
    db_session.add(repo)
    await db_session.flush()

    node = FileNode(repo_id=repo.id, file_path="src/main.py", language="python")
    dep = FileDependency(
        repo_id=repo.id,
        source_file="src/main.py",
        target_file="src/utils.py",
        import_raw="import utils",
    )
    db_session.add(node)
    db_session.add(dep)
    await db_session.flush()

    await db_session.delete(repo)
    await db_session.flush()

    nodes = (await db_session.execute(select(FileNode))).scalars().all()
    deps = (await db_session.execute(select(FileDependency))).scalars().all()
    assert len(nodes) == 0
    assert len(deps) == 0


async def test_file_node_unique_constraint(db_session):
    repo = Repository(url="https://github.com/org/uq-repo", name="uq-repo")
    db_session.add(repo)
    await db_session.flush()

    db_session.add(FileNode(repo_id=repo.id, file_path="src/main.py", language="python"))
    await db_session.flush()

    db_session.add(FileNode(repo_id=repo.id, file_path="src/main.py", language="python"))
    try:
        await db_session.flush()
        pytest.fail("Expected IntegrityError was not raised")
    except IntegrityError:
        pass
