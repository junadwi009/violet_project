export type Artifact = {
  id: string;
  kind: "chartjs" | "html" | "docx" | "pptx";
  title: string;
  spec?: Record<string, unknown> | null;
  html?: string | null;
  file_base64?: string | null;
  filename?: string | null;
  mime?: string | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  artifacts?: Artifact[];
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
  tool_requests: unknown[];
  artifacts: Artifact[];
  agent: string | null;
};

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
): Promise<ChatResponse> {
  return requestJson<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      content,
      session_id: sessionId,
      personality_id: personalityId,
      provider: provider ?? null,
      agent: agent ?? null,
    }),
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

export { apiBaseUrl };
