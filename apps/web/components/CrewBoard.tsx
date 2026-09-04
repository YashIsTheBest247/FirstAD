"use client";

import type { CrewMember, StageTrace } from "@/lib/types";
import { Eyebrow, Headline, Ordinal } from "./ui";

/**
 * The crew board draws the pipeline as it actually runs.
 *
 * Rows are stages in fixed order. Two rows hold a pair of agents, because that
 * work is genuinely independent and runs concurrently. Everything else is
 * strictly sequential: you cannot schedule before you have broken down, and
 * you cannot budget before you have a schedule. The shape of this board is the
 * architecture, not an illustration of it.
 */

const PIPELINE: { n: number; label: string; stages: string[]; concurrent?: boolean }[] = [
  { n: 1, label: "Read it", stages: ["script"] },
  { n: 2, label: "Break it apart", stages: ["breakdown", "clearance_extract"], concurrent: true },
  { n: 3, label: "Check the real world", stages: ["locations", "clearance_risk"], concurrent: true },
  { n: 4, label: "Board it", stages: ["schedule"] },
  { n: 5, label: "Check the rules", stages: ["compliance"] },
  { n: 6, label: "Price it", stages: ["budget"] },
  { n: 7, label: "Cut the sheets", stages: ["call_sheets"] },
];

export function CrewBoard({
  crew,
  traces,
  searchesRun,
}: {
  crew: CrewMember[];
  traces: Record<string, StageTrace>;
  searchesRun: number;
}) {
  const byStage = new Map(crew.map((c) => [c.stage, c]));
  const done = Object.values(traces).filter((t) => t.status === "done").length;
  const pct = Math.round((done / 9) * 100);

  return (
    <section className="mx-auto max-w-[1240px] px-5">
      <div className="slab-ink px-6 py-9 sm:px-10 sm:py-12">
        <div className="mb-9 flex flex-col gap-6 border-b border-[var(--line-ink)] pb-7 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <Eyebrow onInk>The crew</Eyebrow>
            <h2 className="mt-2 text-[32px] text-[var(--on-ink)] sm:text-[42px]">
              <Headline onInk>Nine agents, *one package*</Headline>
            </h2>
            <p className="mt-3 max-w-lg text-[13.5px] leading-relaxed text-[var(--on-ink-2)]">
              Each agent stands in for a real job on a production. That is not a metaphor,
              it is how the work divides on a film, and dividing the agents the same way
              keeps every instruction narrow enough to be reliable.
            </p>
          </div>

          <div className="shrink-0 sm:text-right">
            <Eyebrow onInk>Progress</Eyebrow>
            <div className="display mt-1.5 text-[38px] leading-none text-[var(--lime)]">
              {done}
              <span className="text-[var(--on-ink-2)]">/9</span>
            </div>
            <div className="mt-3 h-1 w-32 overflow-hidden rounded-full bg-[var(--line-ink)] sm:ml-auto">
              <div
                className="h-full rounded-full bg-[var(--lime)] transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </div>

        <div id="how" className="space-y-2.5">
          {PIPELINE.map((row) => (
            <div key={row.n} className="grid gap-2.5 lg:grid-cols-[172px_1fr] lg:gap-5">
              <div className="flex items-center gap-3 lg:pt-3.5">
                <Ordinal n={row.n} onInk />
                <span className="display text-[15px] tracking-[-0.01em] text-[var(--on-ink)]">
                  {row.label}
                </span>
                {row.concurrent ? (
                  <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-[var(--lime-deep)]">
                    ×2
                  </span>
                ) : null}
              </div>

              <div
                className={`grid gap-2.5 ${row.stages.length > 1 ? "sm:grid-cols-2" : "grid-cols-1"}`}
              >
                {row.stages.map((stage) => {
                  const member = byStage.get(stage);
                  if (!member) return null;
                  return (
                    <AgentRow
                      key={stage}
                      member={member}
                      trace={traces[stage]}
                      concurrent={row.concurrent}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-7 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--on-ink-2)]">
          Steps run in order. Paired agents run concurrently.
          {searchesRun > 0 ? ` ${searchesRun} live web searches this run.` : ""}
        </p>
      </div>
    </section>
  );
}

function AgentRow({
  member,
  trace,
  concurrent,
}: {
  member: CrewMember;
  trace?: StageTrace;
  concurrent?: boolean;
}) {
  const status = trace?.status ?? "pending";

  const shell =
    status === "running"
      ? "relative overflow-hidden border-[var(--lime)] bg-[#1f241c]"
      : status === "done"
        ? "border-[#3d4a34] bg-[var(--ink-2)]"
        : status === "failed"
          ? "border-[#5c2b2b] bg-[#211917]"
          : "border-[var(--line-ink)] bg-[var(--ink-2)] opacity-70";

  return (
    <div className={`flex items-start gap-3.5 rounded-[var(--r-sm)] border px-4 py-3 ${shell}`}>
      <Dot status={status} />

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
          <span className="display text-[15px] tracking-[-0.005em] text-[var(--on-ink)]">
            {member.crew_role}
          </span>
          {member.grounded ? (
            <span className="rounded-full bg-[var(--lime)] px-1.5 py-[1px] font-mono text-[8.5px] font-medium uppercase tracking-[0.1em] text-[var(--ink)]">
              Parallel
            </span>
          ) : null}
        </div>
        <p className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-[var(--on-ink-2)]">
          {trace?.detail || member.does}
        </p>
      </div>

      <div className="shrink-0 text-right">
        {trace?.model ? (
          <div className="font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--on-ink-2)]">
            {trace.model.replace("gemini-", "")}
          </div>
        ) : concurrent ? (
          <div className="font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--on-ink-2)]">
            concurrent
          </div>
        ) : null}
        {trace?.duration_s != null ? (
          <div className="mt-0.5 font-mono text-[10px] text-[var(--on-ink)]">
            {trace.duration_s.toFixed(1)}s
          </div>
        ) : null}
        {trace?.searches ? (
          <div className="mt-0.5 font-mono text-[10px] text-[var(--lime)]">
            {trace.searches} sourced
          </div>
        ) : null}
      </div>

      {status === "running" ? <span className="sweeping absolute inset-0" /> : null}
    </div>
  );
}

function Dot({ status }: { status: string }) {
  const colour =
    status === "running"
      ? "var(--lime)"
      : status === "done"
        ? "var(--lime-deep)"
        : status === "failed"
          ? "var(--risk-red)"
          : "#4b524d";

  return (
    <span className="mt-1.5 flex h-2 w-2 shrink-0">
      <span
        className={`h-2 w-2 rounded-full ${status === "running" ? "breathe" : ""}`}
        style={{
          background: colour,
          boxShadow: status === "pending" ? "none" : `0 0 9px ${colour}`,
        }}
      />
    </span>
  );
}
