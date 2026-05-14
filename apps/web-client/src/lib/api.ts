export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
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
};

export type PersonalityProfile = {
  id: string;
  name: string;
  tone: string;
  verbosity: string;
  language: string;
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
): Promise<ChatResponse> {
  return requestJson<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      content,
      session_id: sessionId,
      personality_id: personalityId,
    }),
  });
}

export async function fetchPersonalities(): Promise<PersonalityProfile[]> {
  const result = await requestJson<{ items: PersonalityProfile[] }>(
    "/api/personalities",
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
