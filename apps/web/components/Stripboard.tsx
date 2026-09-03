"use client";

import type { ShootDay, StripColor, Stripboard as StripboardData } from "@/lib/types";
import { Eyebrow, Headline, Panel, SectionHead, Stat, eighths } from "./ui";

/**
 * A real stripboard is a rack of coloured cardboard strips, one per scene,
 * grouped into shooting days. The colours are not a design choice: white is an
 * interior day, yellow an exterior day, blue an interior night, green an
 * exterior night, and every 1st AD reads them that way.
 *
 * These are the physical strip colours, which is why they only work on a paper
 * ground. On a dark surface a white strip is invisible.
 */

const STRIP: Record<StripColor, { fill: string; label: string }> = {
  white: { fill: "var(--strip-white)", label: "Int day" },
  yellow: { fill: "var(--strip-yellow)", label: "Ext day" },
  blue: { fill: "var(--strip-blue)", label: "Int night" },
  green: { fill: "var(--strip-green)", label: "Ext night" },
};

export function Stripboard({ board }: { board: StripboardData }) {
  const totalEighths = board.days.reduce((sum, d) => sum + d.total_eighths, 0);

  return (
    <div className="space-y-7">
      <SectionHead
        label="Stage 4 · 1st Assistant Director"
        title="The *stripboard*"
        aside={
          <div className="flex flex-wrap gap-8">
            <Stat label="Shoot days" value={board.shoot_day_count} tone="blue" />
            <Stat
              label="Company moves"
              value={board.company_moves}
              tone={board.company_moves > board.shoot_day_count / 2 ? "red" : "green"}
            />
            <Stat label="Total pages" value={eighths(totalEighths)} />
          </div>
        }
      />

      {board.rationale ? (
        <Panel className="border-l-[3px] border-l-[var(--lime)]">
          <Eyebrow>Why the board looks like this</Eyebrow>
          <p className="mt-2.5 text-[14px] leading-relaxed text-[var(--text)]">
            {board.rationale}
          </p>
        </Panel>
      ) : null}

      <div className="flex flex-wrap gap-5">
        {(Object.keys(STRIP) as StripColor[]).map((key) => (
          <span key={key} className="inline-flex items-center gap-2">
            <span
              className="h-3.5 w-7 rounded-[2px] border border-[var(--strip-edge)]"
              style={{ background: STRIP[key].fill }}
            />
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-3)]">
              {STRIP[key].label}
            </span>
          </span>
        ))}
      </div>

      <div className="space-y-4">
        {board.days.map((day) => (
          <DayBlock key={day.day_number} day={day} />
        ))}
      </div>

      {board.cast.length > 0 ? <DayOutOfDays board={board} /> : null}
    </div>
  );
}

function DayBlock({ day }: { day: ShootDay }) {
  const heavy = day.total_eighths > 48;

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] bg-[var(--paper)] px-5 py-3.5">
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="display text-[21px] tracking-[-0.015em]">Day {day.day_number}</span>
          <span className="text-[13.5px] text-[var(--text-2)]">{day.location}</span>
          {day.company_move ? (
            <span className="rounded-full border border-[#f2dcae] bg-[#fdf4e3] px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-[#9a5f08]">
              Company move
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-4 font-mono text-[10.5px] uppercase tracking-[0.12em]">
          <span className={heavy ? "text-[var(--risk-amber)]" : "text-[var(--text-2)]"}>
            {eighths(day.total_eighths)} pages
          </span>
          <span className="text-[var(--text-3)]">{day.scenes.length} scenes</span>
        </div>
      </div>

      <div>
        {day.scenes.map((scene) => {
          const strip = STRIP[scene.strip_color] ?? STRIP.white;
          return (
            <div
              key={scene.scene_number}
              className="flex items-start gap-0 border-b border-[var(--line)] last:border-b-0"
            >
              {/* The strip itself: a physical band of colour down the left edge. */}
              <span
                className="w-2.5 shrink-0 self-stretch border-r border-[var(--strip-edge)]"
                style={{ background: strip.fill }}
              />
              <div className="flex flex-1 items-start gap-3 px-4 py-3">
                <span className="mt-px w-8 shrink-0 font-mono text-[12px] text-[var(--text-3)]">
                  {scene.scene_number}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-mono text-[12px] text-[var(--text)]">
                    {scene.slugline}
                  </div>
                  <div className="mt-1 truncate text-[12.5px] text-[var(--text-2)]">
                    {scene.synopsis}
                  </div>
                </div>
                {scene.cast_ids.length > 0 ? (
                  <span className="mt-px shrink-0 font-mono text-[11px] text-[var(--text-3)]">
                    {scene.cast_ids.join(", ")}
                  </span>
                ) : null}
                <span className="mt-px w-11 shrink-0 text-right font-mono text-[11.5px] text-[var(--text-2)]">
                  {scene.eighths}/8
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {day.notes.length > 0 ? (
        <div className="border-t border-[var(--line)] bg-[var(--lime-wash)] px-5 py-3">
          {day.notes.map((note, i) => (
            <p key={i} className="text-[12.5px] leading-relaxed text-[#4a6206]">
              {note}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** The day-out-of-days grid: who works when, and who is being held for nothing. */
function DayOutOfDays({ board }: { board: StripboardData }) {
  const days = board.days.map((d) => d.day_number);

  return (
    <div className="pt-4">
      <div className="mb-5">
        <Eyebrow>Cast</Eyebrow>
        <h3 className="mt-2 text-[26px]">
          <Headline>Day out of *days*</Headline>
        </h3>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--line)] bg-[var(--paper)]">
              <th className="px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-3)]">
                #
              </th>
              <th className="px-3 py-2.5 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-3)]">
                Character
              </th>
              {days.map((d) => (
                <th
                  key={d}
                  className="px-2 py-2.5 text-center font-mono text-[10px] text-[var(--text-3)]"
                >
                  {d}
                </th>
              ))}
              <th className="px-4 py-2.5 text-right font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-3)]">
                Held
              </th>
            </tr>
          </thead>
          <tbody>
            {board.cast.map((member) => {
              const work = new Set(member.work_days);
              const has = member.work_days.length > 0;
              const first = has ? Math.min(...member.work_days) : 0;
              const last = has ? Math.max(...member.work_days) : 0;
              const held = has
                ? days.filter((d) => d > first && d < last && !work.has(d)).length
                : 0;

              return (
                <tr key={member.id} className="border-b border-[var(--line)] last:border-b-0">
                  <td className="px-4 py-2.5 font-mono text-[12px] text-[var(--text-3)]">
                    {member.id}
                  </td>
                  <td className="px-3 py-2.5 text-[13.5px] text-[var(--text)]">
                    {member.character}
                  </td>
                  {days.map((d) => {
                    const isWork = work.has(d);
                    const isHold = !isWork && has && d > first && d < last;
                    return (
                      <td key={d} className="px-2 py-2.5 text-center">
                        <span
                          className="inline-block h-3 w-3 rounded-[2px]"
                          style={{
                            background: isWork
                              ? "var(--lime)"
                              : isHold
                                ? "#f3c3c3"
                                : "var(--paper-2)",
                          }}
                          title={isWork ? "Work" : isHold ? "Hold, and a hold day is paid" : ""}
                        />
                      </td>
                    );
                  })}
                  <td
                    className={`px-4 py-2.5 text-right font-mono text-[12px] ${
                      held > 0 ? "text-[var(--risk-red)]" : "text-[var(--text-3)]"
                    }`}
                  >
                    {held || ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2.5 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-3)]">
        Lime is a work day. Red is a hold day, and a hold day is paid.
      </p>
    </div>
  );
}
