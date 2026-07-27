from __future__ import annotations

import asyncio
import base64
import json
from urllib import error, request


_OCR_PROMPT = (
    "Extract ALL text from this image exactly as written, preserving reading order and structure "
    "(tables, lists, headings). Output only the extracted text — no commentary."
)

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def mime_for(filename: str) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MIME_BY_EXT.get(ext, "image/png")


class VisionOCR:
    """OCR via an OpenRouter vision model (default qwen/qwen3-vl-32b-instruct)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 120,
        resolver=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._resolver = resolver

    def _effective_model(self) -> str:
        if self._resolver is None:
            return self.model
        return self._resolver.resolve("vision_model")

    async def ocr(self, data: bytes, mime: str) -> str:
        return await asyncio.to_thread(self._ocr_sync, data, mime)

    def _ocr_sync(self, data: bytes, mime: str) -> str:
        data_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        payload = {
            # VisionOCR builds a raw request body rather than LLMOptions, so the
            # resolved id goes straight into the payload. Read here (in the worker
            # thread) so the preferences file read never blocks the event loop.
            "model": self._effective_model(),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _OCR_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0.0,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://localhost/violet",
            "X-Title": "Violet Assistant",
        }
        req = request.Request(
            f"{self.base_url}/chat/completions", data=body, headers=headers, method="POST"
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OCR provider returned HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OCR provider is unreachable: {exc.reason}") from exc
        return (result["choices"][0]["message"]["content"] or "").strip()
