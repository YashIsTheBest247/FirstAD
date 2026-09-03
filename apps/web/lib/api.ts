import type { CrewMember, PipelineEvent, ProductionPackage } from "./types";

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

/* ---------------------------------------------------------------------------
   Stored runs

   A run is persisted server side the moment it completes, so a refresh does
   not throw away two minutes of work and a finished package has a shareable
   id.
   --------------------------------------------------------------------------- */

export interface RunSummary {
  run_id: string;
  title: string;
  saved_at: string;
  scene_count: number;
  page_count: number;
  shoot_days: number;
  red_flags: number;
  searches: number;
  recorded: boolean;
}

export interface StoredRun {
  run_id: string;
  saved_at: string;
  setting: string;
  searches: number;
  recorded: boolean;
  package: ProductionPackage;
}

export async function getRuns(limit = 25): Promise<RunSummary[]> {
  const res = await fetch(`${API_BASE}/api/runs?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) return [];
  const data = (await res.json()) as { runs: RunSummary[] };
  return data.runs;
}

export async function getRun(runId: string): Promise<StoredRun> {
  const res = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await detailOf(res, "Could not load that run."));
  return res.json();
}

/**
 * The run bundled with the repository.
 *
 * Exists so the product can be looked at without anyone holding API keys. It
 * is a real captured pipeline output, and it carries `recorded: true` so the
 * UI can say so rather than passing it off as a live result.
 */
export async function getDemo(): Promise<StoredRun> {
  const res = await fetch(`${API_BASE}/api/demo`, { cache: "no-store" });
  if (!res.ok) throw new Error(await detailOf(res, "No recorded run is bundled."));
  return res.json();
}

export const CSV_DOCUMENTS = [
  "stripboard",
  "day-out-of-days",
  "breakdown",
  "clearance",
  "budget",
  "call-sheets",
] as const;

export type CsvDocument = (typeof CSV_DOCUMENTS)[number];

/** Download links are plain URLs so the browser handles the save itself. */
export function csvUrl(runId: string, document: CsvDocument): string {
  return `${API_BASE}/api/runs/${encodeURIComponent(runId)}/export/${document}.csv`;
}

export function jsonUrl(runId: string): string {
  return `${API_BASE}/api/runs/${encodeURIComponent(runId)}/export.json`;
}

async function detailOf(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return body?.detail ?? fallback;
  } catch {
    return fallback;
  }
}
