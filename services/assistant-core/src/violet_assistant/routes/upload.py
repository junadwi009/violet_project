from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile

from violet_assistant.ingestion.extractors import extract_text, is_image
from violet_assistant.ingestion.ocr import VisionOCR, mime_for


def create_upload_router(vision: VisionOCR | None, max_upload_mb: int) -> APIRouter:
    router = APIRouter()
    max_bytes = max_upload_mb * 1024 * 1024

    @router.post("/api/upload")
    async def upload(file: UploadFile) -> dict:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty file.")
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=413, detail=f"File exceeds {max_upload_mb} MB limit."
            )

        filename = file.filename or "upload"
        if is_image(filename):
            if vision is None:
                raise HTTPException(
                    status_code=503,
                    detail="OCR is unavailable (no vision model key configured).",
                )
            try:
                text = await vision.ocr(data, mime_for(filename))
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            if not text:
                raise HTTPException(status_code=422, detail="No text found in the image.")
            return {
                "filename": filename,
                "kind": "image-ocr",
                "text": text,
                "chars": len(text),
                "truncated": False,
                "ocr": True,
            }

        try:
            result = extract_text(filename, data)
        except Exception as exc:  # ExtractionError and parser errors → 422
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"filename": filename, "ocr": False, **result}

    return router
