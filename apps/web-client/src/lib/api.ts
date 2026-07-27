export type Artifact = {
  id: string;
  kind: "chartjs" | "html" | "docx" | "pptx";
  title: string;
  /** "inline" renders in the chat flow; "canvas" opens in the side panel. */
  display?: "inline" | "canvas";
  spec?: Record<string, unknown> | null;
  html?: string | null;
  file_base64?: string | null;
  filename?: string | null;
  mime?: string | null;
};

export type ToolTraceEntry = {
  tool: string;
  args: string;
  status: "ok" | "error" | "rejected" | "awaiting_approval";
  summary: string;
};

export type ToolRequest = {
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
  risk: "low" | "medium" | "high" | "critical";
  description: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  artifacts?: Artifact[];
  citations?: string[];
  tool_trace?: ToolTraceEntry[];
  tool_requests?: ToolRequest[];
  agent_run_id?: string | null;
};

export type SkillInfo = {
  id: string;
  name: string;
  description: string;
  kind: string;
};

export type MemoryCandidate = {
  id: string;
  memory_type: string;
  content: string;
  reason: string;
  source_message_id: string;
  confidence: number;
  status: string;
  created_at?: string;
};

export type Memory = {
  id: string;
  memory_type: string;
  content: string;
  source: string;
  confidence: number;
  approved: number;
  created_at: string;
  updated_at: string;
};

export type ChatResponse = {
  message_id: string;
  session_id: string;
  text: string;
  emotion: string;
  memory_candidates: MemoryCandidate[];
  tool_requests: ToolRequest[];
  artifacts: Artifact[];
  agent: string | null;
  citations: string[];
  tool_trace?: ToolTraceEntry[];
  agent_run_id?: string | null;
};

export type ResumeResult = {
  agent_run_id: string;
  status: string;
  text: string;
  tool_trace: ToolTraceEntry[];
  tool_requests: ToolRequest[];
  citations: string[];
  artifacts: Artifact[];
};

export async function resumeAgentRun(
  runId: string,
  toolCallId: string,
  approved: boolean,
): Promise<ResumeResult> {
  return requestJson<ResumeResult>(`/api/agent-runs/${runId}/resume`, {
    method: "POST",
    body: JSON.stringify({ tool_call_id: toolCallId, approved }),
  });
}

export type AgentInfo = {
  id: string;
  name: string;
  description: string;
  model: string;
};

export type PersonalityProfile = {
  id: string;
  name: string;
  tone: string;
  verbosity: string;
  language: string;
};

export type ProviderInfo = {
  id: string;
  label: string;
  active: boolean;
};

export type RouterInfo = {
  mode: string;
  persona_model?: string;
  technical_model?: string;
};

export type ProvidersResponse = {
  active: string;
  router?: RouterInfo;
  items: ProviderInfo[];
};

export type SessionSummary = {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type SessionMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type MemoryInfo = {
  backend: string;
  location: string;
};

const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

async function requestJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function sendChat(
  content: string,
  sessionId: string | null,
  personalityId: string,
  provider?: string | null,
  agent?: string | null,
  opts?: { skillId?: string | null; webSearch?: boolean },
): Promise<ChatResponse> {
  return requestJson<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      content,
      session_id: sessionId,
      personality_id: personalityId,
      provider: provider ?? null,
      agent: agent ?? null,
      skill_id: opts?.skillId ?? null,
      web_search: opts?.webSearch ?? false,
    }),
  });
}

export type SettingsValues = Record<string, string | number | boolean>;

export type AppSettings = {
  values: SettingsValues;
  defaults: SettingsValues;
  overridden: string[];
  locked: Record<string, string | number | boolean>;
};

export type SettingsGroup =
  | "general"
  | "appearance"
  | "model"
  | "behavior"
  | "voice"
  | "knowledge";

export async function fetchSettings(): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings");
}

export async function patchSettings(
  changes: SettingsValues,
): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export async function resetSettings(
  target: { group: SettingsGroup } | { keys: string[] },
): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings/reset", {
    method: "POST",
    body: JSON.stringify(target),
  });
}

export type KnowledgeDoc = {
  path: string;
  chunk_count: number;
  status: string;
  indexed_at: string;
};

export type SourceStatus = {
  name: string;
  connected: boolean;
  detail: string;
  folder?: string;
  folder_id?: string;
};

export type AutoSyncInfo = {
  enabled: boolean;
  interval?: number;
  gdrive_interval?: number;
  last_sync?: Record<
    string,
    { at?: string; indexed?: number; error?: string } | null
  >;
};

export type KnowledgeInfo = {
  dir: string;
  provider: string;
  enabled: boolean;
  doc_count: number;
  chunk_count: number;
  docs: KnowledgeDoc[];
  sources: SourceStatus[];
  auto_sync: AutoSyncInfo;
};

export async function fetchKnowledge(): Promise<KnowledgeInfo> {
  return requestJson<KnowledgeInfo>("/api/knowledge");
}

export async function connectGDrive(): Promise<SourceStatus> {
  return requestJson<SourceStatus>("/api/knowledge/gdrive/connect", {
    method: "POST",
  });
}

export async function disconnectGDrive(): Promise<SourceStatus> {
  return requestJson<SourceStatus>("/api/knowledge/gdrive/disconnect", {
    method: "POST",
  });
}

export type ReindexReport = {
  indexed: number;
  skipped: number;
  removed: number;
  chunks: number;
  errors: { path: string; error: string }[];
};

export async function reindexKnowledge(
  full = false,
  source?: string,
): Promise<ReindexReport> {
  return requestJson<ReindexReport>("/api/knowledge/reindex", {
    method: "POST",
    body: JSON.stringify({ full, source: source ?? null }),
  });
}

export type FetchResult = {
  url: string;
  title: string;
  text: string;
  chars: number;
  truncated: boolean;
};

export async function fetchUrl(url: string): Promise<FetchResult> {
  return requestJson<FetchResult>("/api/fetch", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function fetchAgents(): Promise<{ enabled: boolean; items: AgentInfo[] }> {
  return requestJson<{ enabled: boolean; items: AgentInfo[] }>("/api/agents");
}

export type LibraryItem = {
  id: string;
  kind: "skill" | "agent";
  name: string;
  description: string;
};

export type CheckResponse = {
  candidate: { name: string; triggers: string[]; chars: number };
  rule: { verdict: string; reason: string };
  nearest: {
    id: string;
    kind: string;
    name: string;
    similarity: number;
    shared_triggers: string[];
  }[];
  llm: { verdict?: string; closest?: string; reason?: string } | null;
};

export async function fetchSkillLibrary(): Promise<{
  judge_enabled: boolean;
  items: LibraryItem[];
}> {
  return requestJson("/api/skills/library");
}

export async function checkSkill(
  content: string,
  judge: boolean,
): Promise<CheckResponse> {
  return requestJson<CheckResponse>("/api/skills/check", {
    method: "POST",
    body: JSON.stringify({ content, judge }),
  });
}

export async function mergeSkills(
  refs: string[],
  name: string,
): Promise<{ skill_md: string }> {
  return requestJson<{ skill_md: string }>("/api/skills/merge", {
    method: "POST",
    body: JSON.stringify({ refs, name }),
  });
}

export async function installSkill(
  skillMd: string,
): Promise<{ id: string; name: string; path: string; updated: boolean }> {
  return requestJson("/api/skills/install", {
    method: "POST",
    body: JSON.stringify({ skill_md: skillMd }),
  });
}

export async function fetchPersonalities(): Promise<PersonalityProfile[]> {
  const result = await requestJson<{ items: PersonalityProfile[] }>(
    "/api/personalities",
  );
  return result.items;
}

export async function fetchProviders(): Promise<ProvidersResponse> {
  return requestJson<ProvidersResponse>("/api/providers");
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  const result = await requestJson<{ items: SessionSummary[] }>("/api/sessions");
  return result.items;
}

export async function fetchSessionMessages(
  sessionId: string,
): Promise<SessionMessage[]> {
  const result = await requestJson<{ items: SessionMessage[] }>(
    `/api/sessions/${sessionId}/messages`,
  );
  return result.items;
}

export async function fetchMemoryCandidates(): Promise<MemoryCandidate[]> {
  const result = await requestJson<{ items: MemoryCandidate[] }>(
    "/api/memory/candidates",
  );
  return result.items;
}

export async function updateMemoryCandidate(
  candidate: MemoryCandidate,
): Promise<MemoryCandidate> {
  return requestJson<MemoryCandidate>(`/api/memory/candidates/${candidate.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      content: candidate.content,
      memory_type: candidate.memory_type,
    }),
  });
}

export async function approveMemoryCandidate(id: string): Promise<void> {
  await requestJson(`/api/memory/candidates/${id}/approve`, {
    method: "POST",
  });
}

export async function rejectMemoryCandidate(id: string): Promise<void> {
  await requestJson(`/api/memory/candidates/${id}/reject`, {
    method: "POST",
  });
}

export async function fetchMemories(): Promise<Memory[]> {
  const result = await requestJson<{ items: Memory[] }>("/api/memory");
  return result.items;
}

export async function fetchMemoryInfo(): Promise<MemoryInfo> {
  return requestJson<MemoryInfo>("/api/memory/info");
}

export async function fetchSkills(): Promise<{ enabled: boolean; items: SkillInfo[] }> {
  return requestJson<{ enabled: boolean; items: SkillInfo[] }>("/api/skills");
}

export type UploadResult = {
  filename: string;
  kind: string;
  text: string;
  chars: number;
  truncated: boolean;
  ocr: boolean;
};

export async function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  // No manual Content-Type: the browser sets the multipart boundary.
  const response = await fetch(`${apiBaseUrl}/api/upload`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Upload failed with ${response.status}`);
  }
  return response.json() as Promise<UploadResult>;
}

export async function updateMemory(memory: Memory): Promise<Memory> {
  return requestJson<Memory>(`/api/memory/${memory.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      content: memory.content,
      memory_type: memory.memory_type,
    }),
  });
}

export async function deleteMemory(id: string): Promise<void> {
  await requestJson(`/api/memory/${id}`, { method: "DELETE" });
}

export type DeleteReport = {
  deleted_sessions: number;
  deleted_messages: number;
  deleted_candidates: number;
  deleted_agent_runs: number;
};

export async function deleteSession(id: string): Promise<DeleteReport> {
  return requestJson<DeleteReport>(`/api/sessions/${id}`, { method: "DELETE" });
}

export async function deleteAllSessions(): Promise<DeleteReport> {
  return requestJson<DeleteReport>("/api/sessions", { method: "DELETE" });
}

// --- Export ---
//
// GET /api/export is gated behind a bearer token (VIOLET_API_TOKEN on the
// server). A plain anchor-tag download link cannot carry an Authorization
// header, so a bare URL is not usable here -- the request has to be made
// with fetch, and the resulting blob turned into a download manually.
//
// The two failure modes that matter to callers are distinct and must not be
// collapsed into one generic failure message:
//   - 503: the *server* has no VIOLET_API_TOKEN configured at all. Export is
//     disabled outright; no client token would help.
//   - 401: the server has a token configured, but the client's token
//     (VITE_VIOLET_API_TOKEN) is missing or does not match.
// ExportOutcome is a discriminated union so callers can branch on
// error.kind instead of matching on message strings.

export type ExportError =
  | { kind: "client_token_missing" }
  | { kind: "server_not_configured" }
  | { kind: "unauthorized" }
  | { kind: "http_error"; status: number; detail: string }
  | { kind: "network_error"; message: string };

export type ExportOutcome =
  | { ok: true; filename: string }
  | { ok: false; error: ExportError };

function parseContentDispositionFilename(
  header: string | null,
): string | null {
  if (!header) return null;
  const starMatch = /filename\*=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  if (starMatch) {
    try {
      return decodeURIComponent(starMatch[1]);
    } catch {
      return starMatch[1];
    }
  }
  const plainMatch = /filename="?([^";]+)"?/i.exec(header);
  return plainMatch ? plainMatch[1] : null;
}

/** Downloads the export bundle from GET /api/export.
 *
 * Requires VITE_VIOLET_API_TOKEN to be set in the client build/dev env; if
 * it is not, no request is made (there is no way it could succeed) and
 * `{ ok: false, error: { kind: "client_token_missing" } }` is returned
 * immediately.
 */
export async function downloadExport(): Promise<ExportOutcome> {
  const token = import.meta.env.VITE_VIOLET_API_TOKEN;
  if (!token) {
    return { ok: false, error: { kind: "client_token_missing" } };
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}/api/export`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (err) {
    return {
      ok: false,
      error: {
        kind: "network_error",
        message: err instanceof Error ? err.message : String(err),
      },
    };
  }

  if (response.status === 503) {
    return { ok: false, error: { kind: "server_not_configured" } };
  }
  if (response.status === 401) {
    return { ok: false, error: { kind: "unauthorized" } };
  }
  if (!response.ok) {
    const detail = await response.text();
    return {
      ok: false,
      error: {
        kind: "http_error",
        status: response.status,
        detail: detail || `Request failed with ${response.status}`,
      },
    };
  }

  const blob = await response.blob();
  const filename =
    parseContentDispositionFilename(
      response.headers.get("Content-Disposition"),
    ) ?? "violet-export.json";

  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  // Deferred so the browser has a tick to pick up the object URL before it
  // is revoked; revoking synchronously has been flaky in some browsers.
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);

  return { ok: true, filename };
}

export { apiBaseUrl };
