import type { CrewMember, PipelineEvent } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "http://localhost:8000";

export interface HealthStatus {
  status: string;
  gemini_configured: boolean;
  gemini_backend: string;
  parallel_configured: boolean;
  models: { reasoning: string; fast: string };
}

export async function getHealth(): Promise<HealthStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as HealthStatus;
  } catch {
    return null;
  }
}

export async function getCrew(): Promise<CrewMember[]> {
  const res = await fetch(`${API_BASE}/api/crew`, { cache: "no-store" });
  if (!res.ok) throw new Error("Could not load the crew roster.");
  const data = (await res.json()) as { crew: CrewMember[] };
  return data.crew;
}

export async function getSample(): Promise<{ filename: string; setting: string; text: string }> {
  const res = await fetch(`${API_BASE}/api/sample`, { cache: "no-store" });
  if (!res.ok) throw new Error("Could not load the sample screenplay.");
  return res.json();
}

/**
 * Read the pipeline's server-sent event stream.
 *
 * Uses fetch rather than EventSource because the run is a POST carrying the
 * screenplay, and EventSource is GET only. That means parsing the SSE framing
 * by hand, which is a few lines: split on the blank-line record separator and
 * keep whatever partial record is left in the buffer.
 */
export async function* streamAnalysis(
  body: { text: string; filename: string; setting: string },
  signal?: AbortSignal,
): AsyncGenerator<PipelineEvent> {
  const res = await fetch(`${API_BASE}/api/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    let detail = `Request failed with ${res.status}`;
    try {
      const err = await res.json();
      if (err?.detail) detail = err.detail;
    } catch {
      /* keep the status-code message */
    }
    throw new Error(detail);
  }
  if (!res.body) throw new Error("The server returned no stream.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let separator = buffer.indexOf("\n\n");
    while (separator !== -1) {
      const record = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      separator = buffer.indexOf("\n\n");

      const line = record.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;

      const payload = line.slice(6);
      if (payload === "[DONE]") return;

      try {
        yield JSON.parse(payload) as PipelineEvent;
      } catch {
        /* A truncated record is not worth killing the run over. */
      }
    }
  }
}
