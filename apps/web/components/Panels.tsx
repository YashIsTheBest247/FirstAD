"use client";

import { useState } from "react";
import type {
  Breakdown as BreakdownData,
  BudgetLine,
  BudgetTopSheet,
  CallSheet,
  ComplianceReport,
  ComplianceSeverity,
  LocationsIntel,
} from "@/lib/types";
import { Empty, Eyebrow, Panel, SectionHead, Stat, Tag, money, shootDate } from "./ui";

/* -------------------------------------------------------------------------
   Locations
   ------------------------------------------------------------------------- */

export function LocationsPanel({ intel }: { intel: LocationsIntel }) {
  const permitted = intel.locations.filter((l) => l.permit_required).length;

  return (
    <div className="space-y-7">
      <SectionHead
        label="Stage 3 · Location Manager"
        title="Location *intelligence*"
        aside={
          <div className="flex flex-wrap gap-8">
            <Stat label="Sets" value={intel.locations.length} />
            <Stat label="Need permits" value={permitted} tone="blue" />
          </div>
        }
      />

      {intel.locations.length === 0 ? (
        <Empty>No sets were resolved.</Empty>
      ) : (
        <div className="grid gap-3.5 lg:grid-cols-2">
          {intel.locations.map((loc) => (
            <div key={loc.location} className="card p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="display text-[19px] tracking-[-0.015em]">{loc.location}</h3>
                  {loc.jurisdiction ? (
                    <p className="mt-1.5 font-mono text-[11px] text-[var(--text-3)]">
                      {loc.jurisdiction}
                    </p>
                  ) : null}
                </div>
                <Tag tone={loc.permit_required ? "amber" : "neutral"}>
                  {loc.permit_required ? "Permit" : "No permit"}
                </Tag>
              </div>

              <dl className="mt-4 space-y-2.5">
                {loc.permit_cost_note ? <Row label="Cost">{loc.permit_cost_note}</Row> : null}
                {loc.lead_time_days != null ? (
                  <Row label="Lead time">{loc.lead_time_days} days</Row>
                ) : null}
                {loc.weather_window ? <Row label="Weather">{loc.weather_window}</Row> : null}
              </dl>

              {loc.hazards.length > 0 ? (
                <div className="mt-4">
                  <Eyebrow>Hazards</Eyebrow>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {loc.hazards.map((h, i) => (
                      <Tag key={i} tone="amber">
                        {h}
                      </Tag>
                    ))}
                  </div>
                </div>
              ) : null}

              {loc.vendor_notes.length > 0 ? (
                <ul className="mt-4 space-y-1.5">
                  {loc.vendor_notes.map((n, i) => (
                    <li key={i} className="text-[12.5px] leading-relaxed text-[var(--text-2)]">
                      {n}
                    </li>
                  ))}
                </ul>
              ) : null}

              {loc.citations.length > 0 ? (
                <details className="group mt-4">
                  <summary className="inline-flex cursor-pointer items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-2)] transition hover:text-[var(--blue)]">
                    <span className="transition group-open:rotate-90">›</span>
                    {loc.citations.length} source{loc.citations.length === 1 ? "" : "s"}
                  </summary>
                  <ul className="mt-2 space-y-1.5 border-l-2 border-[var(--line)] pl-3.5">
                    {loc.citations.map((c, i) => (
                      <li key={i}>
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[12px] text-[var(--blue)] underline underline-offset-2"
                        >
                          {c.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <dt className="w-20 shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-3)]">
        {label}
      </dt>
      <dd className="flex-1 text-[12.5px] leading-relaxed text-[var(--text)]">{children}</dd>
    </div>
  );
}

/* -------------------------------------------------------------------------
   Budget
   ------------------------------------------------------------------------- */

export function BudgetPanel({ budget }: { budget: BudgetTopSheet }) {
  const groups: { title: string; lines: BudgetLine[] }[] = [
    { title: "Above the line", lines: budget.above_the_line },
    { title: "Below the line", lines: budget.below_the_line },
    { title: "Post and other", lines: budget.post_and_other },
  ];

  const subtotal = groups.reduce(
    (sum, g) => sum + g.lines.reduce((s, l) => s + l.amount_usd, 0),
    0,
  );
  const total = subtotal * (1 + budget.contingency_pct / 100);

  return (
    <div className="space-y-7">
      <SectionHead
        label="Stage 6 · Line Producer"
        title="Budget *top sheet*"
        aside={
          <div className="flex flex-wrap gap-8">
            <Stat label="Subtotal" value={money(subtotal)} />
            <Stat label="Total" value={money(total)} tone="blue" />
          </div>
        }
      />

      <div className="space-y-4">
        {groups.map((group) =>
          group.lines.length === 0 ? null : (
            <div key={group.title} className="card overflow-hidden">
              <div className="flex items-center justify-between border-b border-[var(--line)] bg-[var(--paper)] px-5 py-3">
                <span className="display text-[17px] tracking-[-0.015em]">{group.title}</span>
                <span className="font-mono text-[12.5px] text-[var(--text-2)]">
                  {money(group.lines.reduce((s, l) => s + l.amount_usd, 0))}
                </span>
              </div>
              <div>
                {group.lines.map((line, i) => (
                  <div
                    key={`${line.account}-${i}`}
                    className="flex items-start gap-3.5 border-b border-[var(--line)] px-5 py-3 last:border-b-0"
                  >
                    <span className="mt-px w-11 shrink-0 font-mono text-[11px] text-[var(--text-3)]">
                      {line.account}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13.5px] text-[var(--text)]">{line.detail}</div>
                      <div className="mt-1 text-[11.5px] leading-relaxed text-[var(--text-2)]">
                        {line.driver}
                      </div>
                    </div>
                    <span className="shrink-0 font-mono text-[13px] text-[var(--text)]">
                      {money(line.amount_usd)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ),
        )}

        <div className="card px-5 py-4">
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-[var(--text-2)]">Contingency</span>
            <span className="font-mono text-[var(--text-2)]">
              {budget.contingency_pct}% · {money(total - subtotal)}
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[var(--line)] pt-3">
            <span className="display text-[20px] tracking-[-0.02em]">Total</span>
            <span className="display text-[26px] tracking-[-0.02em] text-[var(--blue)]">
              {money(total)}
            </span>
          </div>
        </div>

        {budget.assumptions.length > 0 ? (
          <Panel className="border-l-[3px] border-l-[var(--lime)]">
            <Eyebrow>Assumptions</Eyebrow>
            <ul className="mt-2.5 space-y-2">
              {budget.assumptions.map((a, i) => (
                <li key={i} className="text-[12.5px] leading-relaxed text-[var(--text)]">
                  {a}
                </li>
              ))}
            </ul>
          </Panel>
        ) : null}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
   Compliance
   ------------------------------------------------------------------------- */

const SEVERITY: Record<ComplianceSeverity, { bar: string; label: string; tone: "red" | "amber" | "blue" }> =
  {
    blocker: { bar: "var(--risk-red)", label: "Blocker", tone: "red" },
    warning: { bar: "var(--risk-amber)", label: "Warning", tone: "amber" },
    advisory: { bar: "var(--blue)", label: "Advisory", tone: "blue" },
  };

export function CompliancePanel({ report }: { report: ComplianceReport }) {
  const counts = report.flags.reduce<Record<string, number>>(
    (acc, f) => ({ ...acc, [f.severity]: (acc[f.severity] ?? 0) + 1 }),
    {},
  );

  return (
    <div className="space-y-7">
      <SectionHead
        label="Stage 5 · Unit Production Manager"
        title="Schedule *compliance*"
        aside={
          <div className="flex flex-wrap gap-8">
            <Stat
              label="Blockers"
              value={counts.blocker ?? 0}
              tone={counts.blocker ? "red" : "green"}
            />
            <Stat label="Warnings" value={counts.warning ?? 0} tone="ink" />
          </div>
        }
      />

      {report.flags.length === 0 ? (
        <Empty>No compliance issues were raised against this schedule.</Empty>
      ) : (
        <div className="space-y-3">
          {report.flags.map((flag, i) => {
            const sev = SEVERITY[flag.severity] ?? SEVERITY.advisory;
            return (
              <div key={i} className="card flex items-stretch overflow-hidden">
                <span className="w-1.5 shrink-0" style={{ background: sev.bar }} />
                <div className="min-w-0 flex-1 px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="display text-[17px] tracking-[-0.015em]">{flag.rule}</span>
                      {flag.day_number != null ? (
                        <span className="font-mono text-[10px] text-[var(--text-3)]">
                          Day {flag.day_number}
                        </span>
                      ) : null}
                      {flag.scene_numbers.length > 0 ? (
                        <span className="font-mono text-[10px] text-[var(--text-3)]">
                          sc. {flag.scene_numbers.join(", ")}
                        </span>
                      ) : null}
                    </div>
                    <Tag tone={sev.tone}>{sev.label}</Tag>
                  </div>

                  <p className="mt-2.5 text-[13.5px] leading-relaxed text-[var(--text)]">
                    {flag.detail}
                  </p>

                  <div className="mt-3 rounded-[var(--r-sm)] bg-[var(--lime-wash)] px-3.5 py-2.5">
                    <Eyebrow>Remedy</Eyebrow>
                    <p className="mt-1 text-[12.5px] leading-relaxed text-[#3f5405]">
                      {flag.remedy}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
   Call sheets
   ------------------------------------------------------------------------- */

export function CallSheetsPanel({ sheets }: { sheets: CallSheet[] }) {
  const [active, setActive] = useState(0);
  if (sheets.length === 0) return <Empty>No call sheets were produced.</Empty>;

  const sheet = sheets[Math.min(active, sheets.length - 1)];

  return (
    <div className="space-y-7">
      <SectionHead label="Stage 7 · 2nd Assistant Director" title="The *call sheets*" />

      <div className="flex flex-wrap gap-2">
        {sheets.map((s, i) => (
          <button
            key={s.day_number}
            type="button"
            onClick={() => setActive(i)}
            className={`press rounded-full border px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] ${
              i === active
                ? "border-[var(--ink)] bg-[var(--ink)] text-[var(--on-ink)]"
                : "border-[var(--line)] bg-[var(--white)] text-[var(--text-2)] hover:border-[var(--ink)]"
            }`}
          >
            Day {s.day_number}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--line)] bg-[var(--paper)] px-6 py-4">
          <div>
            <div className="display text-[24px] tracking-[-0.02em]">Day {sheet.day_number}</div>
            {sheet.shoot_date ? (
              <div className="mt-0.5 font-mono text-[12px] text-[var(--text-2)]">
                {shootDate(sheet.shoot_date)}
              </div>
            ) : null}
            <div className="mt-1 text-[13.5px] text-[var(--text-2)]">{sheet.location}</div>
          </div>
          <div className="sm:text-right">
            <Eyebrow>General crew call</Eyebrow>
            <div className="display mt-1 text-[30px] leading-none tracking-[-0.02em] text-[var(--blue)]">
              {sheet.general_call}
            </div>
          </div>
        </div>

        <div className="grid gap-7 p-6 lg:grid-cols-2">
          <div>
            <Eyebrow>Scenes</Eyebrow>
            <ul className="mt-2.5 space-y-2">
              {sheet.scenes.map((s) => (
                <li key={s.scene_number} className="flex gap-3">
                  <span className="w-7 shrink-0 font-mono text-[12px] text-[var(--text-3)]">
                    {s.scene_number}
                  </span>
                  <span className="flex-1 font-mono text-[12px] text-[var(--text)]">
                    {s.slugline}
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-[var(--text-2)]">
                    {s.eighths}/8
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-6">
            {sheet.cast_calls.length > 0 ? (
              <div>
                <Eyebrow>Cast calls</Eyebrow>
                <ul className="mt-2.5 space-y-2">
                  {sheet.cast_calls.map((c, i) => (
                    <li key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                      <span className="w-14 shrink-0 font-mono text-[12px] text-[var(--blue)]">
                        {c.time}
                      </span>
                      <span className="text-[13px] text-[var(--text)]">{c.who}</span>
                      {c.note ? (
                        <span className="text-[11.5px] text-[var(--text-3)]">{c.note}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {sheet.department_calls.length > 0 ? (
              <div>
                <Eyebrow>Department pre-calls</Eyebrow>
                <ul className="mt-2.5 space-y-2">
                  {sheet.department_calls.map((c, i) => (
                    <li key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                      <span className="w-14 shrink-0 font-mono text-[12px] text-[#4a6206]">
                        {c.time}
                      </span>
                      <span className="text-[13px] text-[var(--text)]">{c.who}</span>
                      {c.note ? (
                        <span className="text-[11.5px] text-[var(--text-3)]">{c.note}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>

        {sheet.safety_notes.length > 0 ? (
          <div className="border-t border-[var(--line)] bg-[#fdeded] px-6 py-4">
            <Eyebrow>Safety</Eyebrow>
            <ul className="mt-2 space-y-1.5">
              {sheet.safety_notes.map((n, i) => (
                <li key={i} className="text-[12.5px] leading-relaxed text-[#7a2020]">
                  {n}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {sheet.weather_note ? (
          <div className="flex flex-wrap gap-3 border-t border-[var(--line)] px-6 py-3.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-3)]">
              Weather
            </span>
            <span className="text-[12.5px] text-[var(--text-2)]">{sheet.weather_note}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
   Breakdown
   ------------------------------------------------------------------------- */

export function BreakdownPanel({ breakdown }: { breakdown: BreakdownData }) {
  const total = breakdown.scenes.reduce((n, s) => n + s.elements.length, 0);
  const flagged = breakdown.scenes.reduce(
    (n, s) => n + s.elements.filter((e) => e.flags_department).length,
    0,
  );

  return (
    <div className="space-y-7">
      <SectionHead
        label="Stage 2 · 1st Assistant Director"
        title="Script *breakdown*"
        aside={
          <div className="flex flex-wrap gap-8">
            <Stat label="Elements" value={total} />
            <Stat label="Need a department" value={flagged} tone="blue" />
          </div>
        }
      />

      <div className="space-y-3">
        {breakdown.scenes.map((scene) => (
          <div key={scene.scene_number} className="card px-5 py-4">
            <div className="flex items-baseline justify-between gap-3">
              <span className="display text-[17px] tracking-[-0.015em]">
                Scene {scene.scene_number}
              </span>
              <span className="font-mono text-[11px] text-[var(--text-2)]">
                {scene.estimated_setup_hours}h setup
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {scene.elements.map((el, i) => (
                <span
                  key={i}
                  className={`rounded-full border px-2.5 py-0.5 text-[11.5px] ${
                    el.flags_department
                      ? "border-[#f2dcae] bg-[#fdf4e3] text-[#9a5f08]"
                      : "border-[var(--line)] bg-[var(--paper)] text-[var(--text-2)]"
                  }`}
                  title={`${el.category.replace(/_/g, " ")}${el.note ? ` · ${el.note}` : ""}`}
                >
                  {el.name}
                </span>
              ))}
              {scene.elements.length === 0 ? (
                <span className="text-[12px] text-[var(--text-3)]">No elements tagged.</span>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
