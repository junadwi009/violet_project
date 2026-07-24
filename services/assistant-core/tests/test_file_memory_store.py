from __future__ import annotations

from pathlib import Path

import pytest

from violet_assistant.memory.store.file_store import FileApprovedMemoryStore


def _store(tmp_path: Path) -> FileApprovedMemoryStore:
    return FileApprovedMemoryStore(tmp_path / "memory")


def test_add_creates_file_and_index(tmp_path) -> None:
    store = _store(tmp_path)
    record = store.add(
        memory_type="profile",
        content="prefers concise updates",
        source="message:m1",
        confidence=0.65,
    )

    files = list((tmp_path / "memory" / "memories").glob("*.md"))
    assert len(files) == 1
    assert record["id"] in files[0].name
    assert files[0].name.endswith(".md")

    index = (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8")
    assert "prefers concise updates" in index
    assert "1 approved memory" in index


def test_round_trip_list_reads_frontmatter(tmp_path) -> None:
    store = _store(tmp_path)
    store.add(
        memory_type="negative_preference",
        content="does not like noisy dashboards",
        source="message:m2",
        confidence=0.8,
    )

    reloaded = FileApprovedMemoryStore(tmp_path / "memory").list()
    assert len(reloaded) == 1
    assert reloaded[0]["memory_type"] == "negative_preference"
    assert reloaded[0]["content"] == "does not like noisy dashboards"
    assert reloaded[0]["confidence"] == 0.8
    assert reloaded[0]["approved"] == 1


def test_update_keeps_filename_stable(tmp_path) -> None:
    store = _store(tmp_path)
    record = store.add(
        memory_type="profile",
        content="original text",
        source="message:m3",
        confidence=0.5,
    )
    filename_before = list((tmp_path / "memory" / "memories").glob("*.md"))[0].name

    updated = store.update(record["id"], content="edited text", memory_type="fact")
    filename_after = list((tmp_path / "memory" / "memories").glob("*.md"))[0].name

    assert updated["content"] == "edited text"
    assert updated["memory_type"] == "fact"
    assert filename_before == filename_after  # stable, keyed by id
    assert store.list()[0]["content"] == "edited text"


def test_delete_removes_file(tmp_path) -> None:
    store = _store(tmp_path)
    record = store.add(
        memory_type="profile",
        content="to be deleted",
        source="message:m4",
        confidence=0.5,
    )
    store.delete(record["id"])
    assert store.list() == []
    assert list((tmp_path / "memory" / "memories").glob("*.md")) == []


def test_update_missing_raises(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(KeyError):
        store.update("nope", content="x")


def test_import_record_is_idempotent(tmp_path) -> None:
    store = _store(tmp_path)
    record = {
        "id": "fixed-id-1",
        "memory_type": "profile",
        "content": "migrated fact",
        "source": "message:m5",
        "confidence": 0.7,
        "created_at": "2026-07-24T09:00:00+00:00",
        "updated_at": "2026-07-24T09:00:00+00:00",
    }
    first = store.import_record(record)
    second = store.import_record(record)

    assert first is not None
    assert second is None  # already present, not re-imported
    assert len(store.list()) == 1
    assert store.list()[0]["id"] == "fixed-id-1"
