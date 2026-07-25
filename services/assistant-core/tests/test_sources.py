from __future__ import annotations

from violet_assistant.knowledge.sources.local_folder import LocalFolderSource


def test_local_source_lists_and_reads(tmp_path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "skip.xyz").write_text("no", encoding="utf-8")
    source = LocalFolderSource(tmp_path)
    docs = list(source.list_documents())
    assert len(docs) == 1
    doc = docs[0]
    assert doc.doc_id == "local:a.txt"
    assert doc.filename == "a.txt"
    assert source.read(doc) == b"hello"
    assert source.status()["connected"] is True
