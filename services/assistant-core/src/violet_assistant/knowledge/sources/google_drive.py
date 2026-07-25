from __future__ import annotations

from typing import Iterable

from violet_assistant.config import Settings
from violet_assistant.knowledge.sources.base import SourceDocument

_FOLDER_MIME = "application/vnd.google-apps.folder"

# native google mime -> (export mime, extension)
_EXPORT = {
    "application/vnd.google-apps.document": ("text/markdown", "md"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", "csv"),
    "application/vnd.google-apps.presentation": ("text/plain", "txt"),
}
# binary mimes we can extract, keyed to the extension the extractor expects
_BINARY_EXT = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "application/json": "json",
}


class GoogleDriveSource:
    name = "gdrive"

    def __init__(self, settings: Settings, service=None) -> None:
        self.settings = settings
        self._service = service  # injected in tests; built lazily otherwise
        self._doc_meta: dict[str, dict] = {}  # file_id -> {export_mime}

    # -- service / status -------------------------------------------------
    def _get_service(self):
        if self._service is not None:
            return self._service
        from violet_assistant.knowledge import gdrive_auth

        creds = gdrive_auth.load_credentials(self.settings)
        if creds is None:
            return None
        from googleapiclient.discovery import build  # lazy

        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def status(self) -> dict:
        if not (
            self.settings.gdrive_folder_id and self.settings.google_oauth_client_secrets
        ):
            return {"name": "gdrive", "connected": False, "detail": "not_configured"}
        try:
            service = self._get_service()
        except Exception as exc:  # noqa: BLE001 — missing libs etc.
            return {"name": "gdrive", "connected": False, "detail": str(exc)}
        if service is None:
            return {
                "name": "gdrive",
                "connected": False,
                "detail": "needs_auth",
                "folder_id": self.settings.gdrive_folder_id,
            }
        return {
            "name": "gdrive",
            "connected": True,
            "detail": "connected",
            "folder_id": self.settings.gdrive_folder_id,
        }

    # -- listing ----------------------------------------------------------
    def _list_kwargs(self, parent_id: str, page_token: str | None) -> dict:
        kwargs = {
            "q": f"'{parent_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime)",
            "pageSize": 200,
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "pageToken": page_token,
        }
        if self.settings.gdrive_shared_drive_id:
            kwargs["corpora"] = "drive"
            kwargs["driveId"] = self.settings.gdrive_shared_drive_id
        else:
            kwargs["corpora"] = "allDrives"
        return kwargs

    def _children(self, service, parent_id: str) -> list[dict]:
        out: list[dict] = []
        page_token = None
        while True:
            resp = service.files().list(
                **self._list_kwargs(parent_id, page_token)
            ).execute()
            out.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    def list_documents(self) -> Iterable[SourceDocument]:
        service = self._get_service()
        if service is None:
            return
        stack = [(self.settings.gdrive_folder_id, "")]
        while stack:
            parent, prefix = stack.pop()
            for f in self._children(service, parent):
                mime = f["mimeType"]
                name = f["name"]
                rel = f"{prefix}/{name}" if prefix else name
                if mime == _FOLDER_MIME:
                    stack.append((f["id"], rel))
                    continue
                mapped = self._map(f)
                if mapped is None:
                    continue
                filename, export_mime, version = mapped
                self._doc_meta[f["id"]] = {"export_mime": export_mime}
                yield SourceDocument(
                    doc_id=f"gdrive:{f['id']}",
                    display_path=f"{rel}#{f['id'][:6]}",  # id suffix → UNIQUE path
                    version=version,
                    filename=filename,
                    mime=mime,
                )

    def _map(self, f: dict):
        """Return (filename, export_mime_or_None, version) or None if unsupported."""
        mime, name = f["mimeType"], f["name"]
        version = f.get("md5Checksum") or f.get("modifiedTime") or ""
        if mime in _EXPORT:
            export_mime, ext = _EXPORT[mime]
            filename = name if name.lower().endswith("." + ext) else f"{name}.{ext}"
            return filename, export_mime, version
        if mime in _BINARY_EXT:
            ext = _BINARY_EXT[mime]
            filename = name if name.lower().endswith("." + ext) else f"{name}.{ext}"
            return filename, None, version
        return None

    # -- read -------------------------------------------------------------
    def read(self, doc: SourceDocument) -> bytes:
        service = self._get_service()
        if service is None:
            raise RuntimeError("Google Drive is not authorized.")
        file_id = doc.doc_id.split("gdrive:", 1)[1]
        export_mime = self._doc_meta.get(file_id, {}).get("export_mime")
        if export_mime:
            return service.files().export_media(
                fileId=file_id, mimeType=export_mime
            ).execute()
        return service.files().get_media(
            fileId=file_id, supportsAllDrives=True
        ).execute()
