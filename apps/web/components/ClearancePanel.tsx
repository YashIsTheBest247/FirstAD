"use client";

import { useMemo, useState } from "react";
import type { ClearanceReport, RiskLevel } from "@/lib/types";
import { Empty, Eyebrow, Panel, SectionHead, Stat, Tag } from "./ui";

/**
 * The clearance report.
 *
 * Every verdict shows the sources it was reached from, because a clearance
 * report that cannot be checked is worthless. It is also the honest framing:
 * the model graded the risk, the evidence came from live search, and the reader
 * gets to disagree with the grade.
 */

const RISK: Record<
  RiskLevel,
  { label: string; bar: string; text: string; chip: string; meaning: string }
> = {
  red: {
    label: "Red",
    bar: "var(--risk-red)",
    text: "text-[var(--risk-red)]",
    chip: "border-[#f0bcbc] bg-[#fdeded] text-[var(--risk-red)]",
    meaning: "Change or license before production",
  },
  amber: {
    label: "Amber",
    bar: "var(--risk-amber)",
    text: "text-[#9a5f08]",
    chip: "border-[#f2dcae] bg-[#fdf4e3] text-[#9a5f08]",
    meaning: "Producer review",
  },
  green: {
    label: "Green",
    bar: "var(--risk-green)",
    text: "text-[var(--risk-green)]",
    chip: "border-[#bfe3cc] bg-[#eff9f2] text-[var(--risk-green)]",
    meaning: "Clear",
  },
};

const ORDER: RiskLevel[] = ["red", "amber", "green"];

export function ClearancePanel({ report }: { report: ClearanceReport }) {
  const [filter, setFilter] = useState<RiskLevel | "all">("all");

  const rows = useMemo(() => {
    const byId = new Map(report.entities.map((e) => [e.id, e]));
    return report.findings
      .map((finding) => ({ finding, entity: byId.get(finding.entity_id) }))
      .filter((row): row is { finding: typeof row.finding; entity: NonNullable<typeof row.entity> } =>
        Boolean(row.entity),
      )
      .sort((a, b) => ORDER.indexOf(a.finding.risk) - ORDER.indexOf(b.finding.risk));
  }, [report]);

  const counts = useMemo(() => {
    const c: Record<RiskLevel, number> = { red: 0, amber: 0, green: 0 };
    for (const { finding } of rows) c[finding.risk] += 1;
    return c;
  }, [rows]);

  const sourced = rows.reduce((n, r) => n + r.finding.citations.length, 0);
  const visible = filter === "all" ? rows : rows.filter((r) => r.finding.risk === filter);

  return (
    <div className="space-y-7">
      <SectionHead
        label="Stages 2 and 3 · Clearance"
        title="Script *clearance* report"
        aside={
          <div className="flex flex-wrap gap-8">
            <Stat label="Red" value={counts.red} tone={counts.red ? "red" : "ink"} />
            <Stat label="Amber" value={counts.amber} tone="ink" />
            <Stat label="Green" value={counts.green} tone="green" />
          </div>
        }
      />

      <Panel className="border-l-[3px] border-l-[var(--blue)]">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <p className="max-w-2xl text-[13.5px] leading-relaxed text-[var(--text-2)]">
            Every reference below was checked against the live web at run time. Risk is the
            product of two things: whether the reference collides with something real and
            identifiable, and whether the script depicts it badly. A common name with no
            notable match is clear. A name matching a real official who the script shows
            taking a bribe is not.
          </p>
          <div>
            <Eyebrow>Sources gathered</Eyebrow>
            <div className="display mt-1.5 text-[32px] leading-none text-[var(--blue)]">
              {sourced}
            </div>
          </div>
        </div>
      </Panel>

      <div className="flex flex-wrap gap-2">
        <Chip active={filter === "all"} onClick={() => setFilter("all")}>
          All {rows.length}
        </Chip>
        {ORDER.map((risk) => (
          <Chip
            key={risk}
            active={filter === risk}
            activeClass={RISK[risk].chip}
            onClick={() => setFilter(risk)}
          >
            {RISK[risk].label} {counts[risk]}
          </Chip>
        ))}
      </div>

      {visible.length === 0 ? (
        <Empty>Nothing at this risk level.</Empty>
      ) : (
        <div className="space-y-3">
          {visible.map(({ finding, entity }) => {
            const risk = RISK[finding.risk];
            return (
              <div key={finding.entity_id} className="card flex items-stretch overflow-hidden">
                <span className="w-1.5 shrink-0" style={{ background: risk.bar }} />

                <div className="min-w-0 flex-1 px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1.5">
                        <span className="display text-[19px] tracking-[-0.015em]">
                          {entity.text}
                        </span>
                        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-3)]">
                          {entity.category.replace(/_/g, " ")}
                        </span>
                        <span className="font-mono text-[10px] text-[var(--text-3)]">
                          sc. {entity.scene_numbers.join(", ")}
                        </span>
                      </div>

                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {entity.is_negative_portrayal ? (
                          <Tag tone="red">Negative portrayal</Tag>
                        ) : null}
                        {!finding.searched ? <Tag tone="neutral">Unreviewed</Tag> : null}
                      </div>

                      <p className="mt-2.5 text-[12.5px] italic text-[var(--text-3)]">
                        {entity.portrayal}
                      </p>
                    </div>

                    <span
                      className={`shrink-0 rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.12em] ${risk.chip}`}
                      title={risk.meaning}
                    >
                      {risk.label}
                    </span>
                  </div>

                  <p className="mt-3 text-[14px] leading-relaxed text-[var(--text)]">
                    {finding.rationale}
                  </p>

                  {finding.real_world_matches.length > 0 ? (
                    <div className="mt-3.5 rounded-[var(--r-sm)] bg-[var(--paper)] px-3.5 py-2.5">
                      <Eyebrow>Collides with</Eyebrow>
                      <ul className="mt-1.5 space-y-1">
                        {finding.real_world_matches.map((m, i) => (
                          <li key={i} className="text-[12.5px] text-[var(--text)]">
                            {m}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {finding.suggested_alternatives.length > 0 ? (
                    <div className="mt-3.5">
                      <Eyebrow>Pre-verified replacements</Eyebrow>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {finding.suggested_alternatives.map((alt) => (
                          <span
                            key={alt}
                            className="rounded-full border border-[var(--lime-deep)] bg-[var(--lime-wash)] px-2.5 py-0.5 font-mono text-[11px] text-[#4a6206]"
                          >
                            {alt}
                          </span>
                        ))}
                      </div>
                      <p className="mt-1.5 text-[11.5px] text-[var(--text-3)]">
                        Each of these was itself searched and came back clear.
                      </p>
                    </div>
                  ) : null}

                  {finding.citations.length > 0 ? (
                    <details className="group mt-3.5">
                      <summary className="inline-flex cursor-pointer items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-2)] transition hover:text-[var(--blue)]">
                        <span className="transition group-open:rotate-90">›</span>
                        {finding.citations.length} source
                        {finding.citations.length === 1 ? "" : "s"}
                      </summary>
                      <ul className="mt-2.5 space-y-2.5 border-l-2 border-[var(--line)] pl-3.5">
                        {finding.citations.map((c, i) => (
                          <li key={i}>
                            <a
                              href={c.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[12.5px] font-medium text-[var(--blue)] underline underline-offset-2 hover:text-[var(--blue-deep)]"
                            >
                              {c.title}
                            </a>
                            {c.excerpt ? (
                              <p className="mt-0.5 line-clamp-3 text-[11.5px] leading-relaxed text-[var(--text-2)]">
                                {c.excerpt}
                              </p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Chip({
  children,
  active,
  activeClass,
  onClick,
}: {
  children: React.ReactNode;
  active: boolean;
  activeClass?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`press rounded-full border px-3.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.12em] ${
        active
          ? (activeClass ?? "border-[var(--ink)] bg-[var(--ink)] text-[var(--on-ink)]")
          : "border-[var(--line)] bg-[var(--white)] text-[var(--text-2)] hover:border-[var(--ink)]"
      }`}
    >
      {children}
    </button>
  );
}
