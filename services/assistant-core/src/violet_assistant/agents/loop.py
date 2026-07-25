from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from violet_assistant.llm.base import LLMOptions, Message
from violet_assistant.tools.base import wrap_untrusted
from violet_assistant.tools.registry import requires_confirmation


@dataclass
class LoopOutcome:
    status: str                    # completed | awaiting_approval | exhausted | failed
    text: str = ""
    trace: list[dict] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    iterations: int = 0


def _summarize(value, limit: int = 120) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text[:limit] + ("…" if len(text) > limit else "")


class AgentLoop:
    """Model <-> tool iteration with a server-side risk gate and hard caps."""

    def __init__(self, provider_factory, registry, settings, audit=None) -> None:
        self.provider_factory = provider_factory
        self.registry = registry
        self.settings = settings
        self.audit = audit

    # -- public ---------------------------------------------------------
    async def run(self, agent, history) -> LoopOutcome:
        turns = [m for m in history if m.role != "system"]
        messages = [Message(role="system", content=agent.system_prompt), *turns]
        return await self._iterate(agent, messages, iterations=0)

    async def continue_run(
        self, agent, messages, iterations, pending, approved: bool
    ) -> LoopOutcome:
        outcome = LoopOutcome(
            status="running", messages=list(messages), iterations=iterations
        )
        tool = self.registry.get(pending["tool"])
        if approved and tool is not None:
            await self._execute(
                tool, pending["arguments"], pending["id"], outcome, approved=True
            )
        else:
            self._record_audit(
                pending["tool"], pending["arguments"], pending["risk"], False,
                "rejected by user",
            )
            outcome.trace.append(
                {
                    "tool": pending["tool"],
                    "args": _summarize(pending["arguments"]),
                    "status": "rejected",
                    "summary": "declined by user",
                }
            )
            outcome.messages.append(
                Message(
                    role="tool",
                    content="The user declined this tool call. Answer without it.",
                    tool_call_id=pending["id"],
                )
            )
        outcome.pending = []
        return await self._iterate(
            agent, outcome.messages, iterations=outcome.iterations, carried=outcome
        )

    # -- internals ------------------------------------------------------
    async def _iterate(self, agent, messages, iterations: int, carried=None) -> LoopOutcome:
        outcome = carried or LoopOutcome(status="running")
        outcome.messages = list(messages)
        outcome.iterations = iterations
        provider = self.provider_factory(agent.base_url or "")
        # Frozen once: no tool result can widen this (SECURITY_RULES #3).
        specs = self.registry.specs() or None
        deadline = time.monotonic() + self.settings.tool_timeout_seconds

        while True:
            if (
                outcome.iterations >= self.settings.max_tool_iterations
                or time.monotonic() > deadline
            ):
                return await self._final_answer(provider, agent, outcome)

            response = await provider.chat(
                outcome.messages,
                LLMOptions(model=agent.model, temperature=0.4, tools=specs),
            )
            outcome.iterations += 1

            if not response.tool_calls:
                outcome.status = "completed"
                outcome.text = response.text
                return outcome

            outcome.messages.append(
                Message(
                    role="assistant",
                    content=response.text or "",
                    tool_calls=[
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                        for call in response.tool_calls
                    ],
                )
            )

            for call in response.tool_calls:
                tool = self.registry.get(call.name)
                if tool is None:
                    outcome.trace.append(
                        {
                            "tool": call.name,
                            "args": _summarize(call.arguments),
                            "status": "error",
                            "summary": "unknown tool",
                        }
                    )
                    outcome.messages.append(
                        Message(
                            role="tool",
                            content=(
                                f"Unknown tool '{call.name}'. Available: "
                                f"{', '.join(t.name for t in self.registry.enabled())}."
                            ),
                            tool_call_id=call.id,
                        )
                    )
                    continue

                if requires_confirmation(tool, self.settings):
                    self._record_audit(
                        tool.name, call.arguments, tool.risk, False, "awaiting approval"
                    )
                    outcome.status = "awaiting_approval"
                    outcome.pending = [
                        {
                            "id": call.id,
                            "tool": tool.name,
                            "arguments": call.arguments,
                            "risk": tool.risk,
                            "description": tool.description,
                        }
                    ]
                    outcome.trace.append(
                        {
                            "tool": tool.name,
                            "args": _summarize(call.arguments),
                            "status": "awaiting_approval",
                            "summary": "needs your approval",
                        }
                    )
                    return outcome  # stop at the first gated call

                await self._execute(tool, call.arguments, call.id, outcome, approved=True)

    async def _execute(self, tool, arguments, call_id, outcome, approved: bool) -> None:
        try:
            result = await tool.run(arguments)
        except Exception as exc:  # noqa: BLE001 — a bad tool must not kill the run
            result = None
            text, status, summary = f"Tool '{tool.name}' failed: {exc}", "error", str(exc)
        else:
            text = result.text
            status = "error" if result.error else "ok"
            summary = result.error or _summarize(result.text)

        if result is not None:
            outcome.citations.extend(
                c for c in result.citations if c not in outcome.citations
            )
            outcome.artifacts.extend(result.artifacts)
            if result.untrusted:
                text = wrap_untrusted(text)

        capped = text[: self.settings.max_tool_result_chars]
        outcome.messages.append(Message(role="tool", content=capped, tool_call_id=call_id))
        outcome.trace.append(
            {
                "tool": tool.name,
                "args": _summarize(arguments),
                "status": status,
                "summary": summary,
            }
        )
        self._record_audit(tool.name, arguments, tool.risk, approved, summary)

    async def _final_answer(self, provider, agent, outcome) -> LoopOutcome:
        """Cap or timeout reached: ask once more with tools disabled so we still answer."""
        try:
            response = await provider.chat(
                outcome.messages, LLMOptions(model=agent.model, temperature=0.4, tools=None)
            )
            outcome.text = response.text
        except Exception as exc:  # noqa: BLE001
            outcome.status = "failed"
            outcome.text = f"The agent could not complete this run: {exc}"
            return outcome
        outcome.status = "exhausted"
        outcome.iterations += 1
        return outcome

    def _record_audit(self, tool_name, arguments, risk, approved, summary) -> None:
        if self.audit is None:
            return
        try:
            self.audit(
                tool_name, _summarize(arguments, 400), risk, approved, _summarize(summary, 400)
            )
        except Exception:  # noqa: BLE001 — auditing must never break the run
            pass
