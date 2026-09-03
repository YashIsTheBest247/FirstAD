"use client";

import { useState } from "react";
import { CSV_DOCUMENTS, csvUrl, jsonUrl, type RunSummary } from "@/lib/api";
import { Eyebrow } from "./ui";

const DOC_LABELS: Record<string, string> = {
  stripboard: "Stripboard",
  "day-out-of-days": "Day out of days",
  breakdown: "Breakdown",
  clearance: "Clearance report",
  budget: "Budget top sheet",
  "call-sheets": "Call sheets",
};

/**
 * Downloads for a finished package.
 *
 * Plain anchors rather than fetch-and-blob, so the browser owns the save
 * dialog and the Content-Disposition filename the API already sets is the one
 * the user gets. A production office moves these as spreadsheets, so CSV is
 * the primary format and the whole package as JSON is the escape hatch.
 */
export function ExportBar({ runId, recorded }: { runId: string; recorded: boolean }) {
  const [copied, setCopied] = useState(false);

  async function copyPermalink() {
    const url = `${window.location.origin}${window.location.pathname}?run=${encodeURIComponent(runId)}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* Clipboard is blocked in some contexts; the link is still in the URL bar. */
    }
  }

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>Take it with you</Eyebrow>
          <p className="mt-1.5 max-w-lg text-[13px] leading-relaxed text-[var(--text-2)]">
            Each document exports as CSV with the column names scheduling software and
            clearance firms already use, so a row pastes into an existing sheet.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!recorded ? (
            <button type="button" onClick={copyPermalink} className="pill pill-ghost">
              {copied ? "Link copied" : "Copy permalink"}
            </button>
          ) : null}
          <a href={jsonUrl(runId)} className="pill pill-ink" download>
            Whole package · JSON
          </a>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--line)] pt-4">
        {CSV_DOCUMENTS.map((doc) => (
          <a
            key={doc}
            href={csvUrl(runId, doc)}
            download
            className="rounded-full border border-[var(--line)] px-3.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-2)] transition hover:border-[var(--ink)] hover:text-[var(--text)]"
          >
            {DOC_LABELS[doc] ?? doc} · CSV
          </a>
        ))}
      </div>
    </div>
  );
}

/** Previously produced packages, so a run is never a one-shot. */
export function RunHistory({
  runs,
  activeRunId,
  onOpen,
}: {
  runs: RunSummary[];
  activeRunId: string | null;
  onOpen: (runId: string) => void;
}) {
  if (runs.length === 0) return null;

  return (
    <section className="mx-auto max-w-[1240px] px-5">
      <div className="mb-4 flex items-end justify-between gap-4 border-b border-[var(--line)] pb-3">
        <div>
          <Eyebrow>History</Eyebrow>
          <h2 className="mt-1.5 font-[family-name:var(--font-grotesk)] text-2xl font-extrabold uppercase leading-none tracking-[-0.025em]">
            Earlier packages
          </h2>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-3)]">
          {runs.length} stored
        </span>
      </div>

      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {runs.map((run) => {
          const active = run.run_id === activeRunId;
          return (
            <button
              key={run.run_id}
              type="button"
              onClick={() => onOpen(run.run_id)}
              className={`card p-4 text-left transition hover:border-[var(--ink)] ${
                active ? "border-[var(--ink)] ring-1 ring-[var(--ink)]" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="font-[family-name:var(--font-grotesk)] text-[15px] font-bold uppercase leading-tight tracking-[-0.015em]">
                  {run.title}
                </span>
                {run.red_flags > 0 ? (
                  <span className="shrink-0 rounded-full bg-[rgba(217,58,58,0.12)] px-2 py-0.5 font-mono text-[10px] text-[#8f1f1f]">
                    {run.red_flags} red
                  </span>
                ) : null}
              </div>

              <p className="mt-2 font-mono text-[10.5px] uppercase tracking-[0.1em] text-[var(--text-3)]">
                {run.scene_count} scenes · {run.shoot_days} days · {run.searches} sources
              </p>
              {run.saved_at ? (
                <p className="mt-1 font-mono text-[10.5px] text-[var(--text-3)]">
                  {formatWhen(run.saved_at)}
                </p>
              ) : null}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function formatWhen(iso: string): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;

  const minutes = Math.round((Date.now() - then.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)}h ago`;
  return then.toLocaleDateString();
}

/** Said plainly, so a captured run is never mistaken for a live one. */
export function RecordedNotice({ savedAt }: { savedAt: string }) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3 rounded-[var(--r-md)] border border-[var(--lime-deep)] bg-[var(--lime-wash)] px-4 py-3">
      <span className="rounded-full bg-[var(--ink)] px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--on-ink)]">
        Recorded run
      </span>
      <p className="text-[13px] text-[#3d5406]">
        This is a captured pipeline output bundled with the repository, not a live result.
        {savedAt ? ` Produced ${formatWhen(savedAt)}.` : ""} Add API keys and submit a
        script to run the crew yourself.
      </p>
    </div>
  );
}
