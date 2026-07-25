from __future__ import annotations

import pytest

from violet_assistant.config import load_settings
from violet_assistant.knowledge.sources.google_drive import GoogleDriveSource


class _Exec:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _FakeFiles:
    def __init__(self, tree, exports, media):
        self._tree = tree       # parent_id -> list[file dicts]
        self._exports = exports  # file_id -> bytes
        self._media = media     # file_id -> bytes
        self.list_kwargs = []

    def list(self, **kwargs):
        self.list_kwargs.append(kwargs)
        parent = kwargs["q"].split("'")[1]
        return _Exec({"files": self._tree.get(parent, []), "nextPageToken": None})

    def export_media(self, fileId, mimeType):
        return _Exec(self._exports[fileId])

    def get_media(self, fileId, supportsAllDrives=True):
        return _Exec(self._media[fileId])


class _FakeService:
    def __init__(self, files):
        self._files = files

    def files(self):
        return self._files


def _source(tmp_path, tree, exports, media, folder="root", shared=""):
    import os

    os.environ["GDRIVE_FOLDER_ID"] = folder
    os.environ["GDRIVE_SHARED_DRIVE_ID"] = shared
    os.environ["GOOGLE_OAUTH_CLIENT_SECRETS"] = "dummy.json"
    try:
        settings = load_settings(tmp_path)
    finally:
        for k in ("GDRIVE_FOLDER_ID", "GDRIVE_SHARED_DRIVE_ID", "GOOGLE_OAUTH_CLIENT_SECRETS"):
            os.environ.pop(k, None)
    return GoogleDriveSource(settings, service=_FakeService(_FakeFiles(tree, exports, media)))


def test_lists_recursively_and_reads_binary_and_native(tmp_path):
    tree = {
        "root": [
            {"id": "f1", "name": "report.pdf", "mimeType": "application/pdf",
             "md5Checksum": "abc", "modifiedTime": "t1"},
            {"id": "sub", "name": "Sub", "mimeType": "application/vnd.google-apps.folder",
             "modifiedTime": "t0"},
        ],
        "sub": [
            {"id": "d1", "name": "Notes", "mimeType": "application/vnd.google-apps.document",
             "modifiedTime": "t2"},
        ],
    }
    exports = {"d1": b"# Notes\nbody"}
    media = {"f1": b"%PDF-1.4 ..."}
    source = _source(tmp_path, tree, exports, media)

    docs = {d.doc_id: d for d in source.list_documents()}
    assert set(docs) == {"gdrive:f1", "gdrive:d1"}
    assert docs["gdrive:f1"].filename == "report.pdf"
    assert docs["gdrive:f1"].version == "abc"        # md5 preferred
    assert docs["gdrive:d1"].filename == "Notes.md"  # exported doc gets .md
    assert docs["gdrive:d1"].version == "t2"         # native → modifiedTime

    assert source.read(docs["gdrive:f1"]) == b"%PDF-1.4 ..."
    assert source.read(docs["gdrive:d1"]) == b"# Notes\nbody"


def test_shared_drive_params_passed(tmp_path):
    source = _source(tmp_path, {"root": []}, {}, {}, folder="root", shared="SD1")
    list(source.list_documents())
    kwargs = source._service.files().list_kwargs[0]
    assert kwargs["supportsAllDrives"] is True
    assert kwargs["includeItemsFromAllDrives"] is True
    assert kwargs["corpora"] == "drive"
    assert kwargs["driveId"] == "SD1"


def test_status_needs_config(tmp_path):
    settings = load_settings(tmp_path)  # nothing configured
    source = GoogleDriveSource(settings, service=None)
    st = source.status()
    assert st["name"] == "gdrive"
    assert st["connected"] is False
    assert st["detail"] in {"not_configured", "needs_auth"}


@pytest.mark.asyncio
async def test_gdrive_source_indexes_through_pipeline(tmp_path):
    from violet_assistant.knowledge.indexer import KnowledgeIndexer
    from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder
    from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore

    tree = {"root": [
        {"id": "d1", "name": "Notes", "mimeType": "application/vnd.google-apps.document",
         "modifiedTime": "t2"},
    ]}
    source = _source(tmp_path, tree, {"d1": b"# Notes\nsome body text"}, {})
    store = SqliteVectorStore(tmp_path / "k.db"); store.initialize()
    indexer = KnowledgeIndexer(MockEmbedder(), store, [source])

    report = await indexer.reindex()
    assert report["sources"]["gdrive"]["indexed"] == 1
    assert store.stats(origin="gdrive")["doc_count"] == 1
    # incremental: same modifiedTime → skipped
    report2 = await indexer.reindex()
    assert report2["sources"]["gdrive"]["skipped"] == 1
