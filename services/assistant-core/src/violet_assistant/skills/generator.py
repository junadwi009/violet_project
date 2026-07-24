from __future__ import annotations

import base64
import json
import re
from uuid import uuid4

from violet_assistant.documents.render import render_docx, render_pptx
from violet_assistant.llm.base import LLMOptions, LLMProvider, Message
from violet_assistant.skills.schema import Skill


_BLOCK_RE = re.compile(
    r"```(chartjs|html|docx|pptx)[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE
)
_JSON_KINDS = {"chartjs", "docx", "pptx"}


def _new_artifact(kind: str, **fields) -> dict:
    base = {
        "id": str(uuid4()),
        "kind": kind,
        "title": "",
        "spec": None,
        "html": None,
        "file_base64": None,
        "filename": None,
        "mime": None,
    }
    base.update(fields)
    return base


def parse_artifacts(text: str) -> tuple[str, list[dict]]:
    """Split model output into (intro_text, artifacts). Pure — no network, unit-testable."""
    artifacts: list[dict] = []

    def _take(match: re.Match) -> str:
        kind = match.group(1).lower()
        body = match.group(2).strip()
        if kind in _JSON_KINDS:
            try:
                spec = json.loads(body)
            except json.JSONDecodeError:
                return ""  # drop an unparseable spec block
            artifacts.append(_new_artifact(kind, spec=spec))
        else:  # html
            artifacts.append(_new_artifact("html", html=body))
        return ""

    intro = _BLOCK_RE.sub(_take, text).strip()
    return intro, artifacts


_DOC_RENDERERS = {
    "docx": (
        render_docx,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    "pptx": (
        render_pptx,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx",
    ),
}


def _render_file_artifacts(artifacts: list[dict], skill_name: str) -> None:
    """For docx/pptx artifacts, render the spec to a real file and attach base64 + filename."""
    for artifact in artifacts:
        renderer = _DOC_RENDERERS.get(artifact["kind"])
        if renderer is None or not artifact.get("spec"):
            continue
        render, mime, ext = renderer
        try:
            data = render(artifact["spec"])
        except Exception:  # noqa: BLE001 — a bad spec shouldn't kill the response
            continue
        title = (artifact["spec"].get("title") if isinstance(artifact["spec"], dict) else "") or skill_name
        slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-") or "document"
        artifact["file_base64"] = base64.b64encode(data).decode("ascii")
        artifact["filename"] = f"{slug[:48]}.{ext}"
        artifact["mime"] = mime
        artifact["spec"] = None  # the file is the payload now


class SkillEngine:
    """Generates renderable artifacts for a matched skill using the artifact (coding) model."""

    def __init__(self, provider: LLMProvider, model: str) -> None:
        self.provider = provider
        self.model = model

    async def generate(self, skill: Skill, user_content: str) -> tuple[str, list[dict]]:
        response = await self.provider.chat(
            [
                Message(role="system", content=skill.prompt),
                Message(role="user", content=user_content),
            ],
            LLMOptions(model=self.model, temperature=0.2),
        )
        intro, artifacts = parse_artifacts(response.text)
        if not artifacts:
            # Model didn't emit a well-formed artifact; return its text as-is.
            return response.text.strip(), []
        _render_file_artifacts(artifacts, skill.name)
        # Drop docx/pptx artifacts whose file failed to render.
        artifacts = [
            a for a in artifacts if a["kind"] not in _DOC_RENDERERS or a.get("file_base64")
        ]
        if not artifacts:
            return response.text.strip(), []
        if not intro:
            intro = f"Here is the {skill.name.lower()} you asked for."
        for artifact in artifacts:
            artifact["title"] = artifact["title"] or skill.name
        return intro, artifacts
