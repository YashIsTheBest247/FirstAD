"use client";

import { useMemo, useState } from "react";
import type { ClearanceReport, ParsedScript, RiskLevel } from "@/lib/types";
import { Empty, Eyebrow, SectionHead, Stat } from "./ui";

/**
 * The annotated script.
 *
 * A clearance report as a list is a chore to act on, because the writer has to
 * hold a scene number in their head and go find the line. Marking the risks in
 * the script itself is how a clearance firm actually delivers: an annotated
 * copy you read top to bottom. Click a mark to see the verdict and its sources.
 */

const RISK_STYLE: Record<RiskLevel, { bg: string; border: string; text: string }> = {
  red: { bg: "rgba(217,58,58,0.16)", border: "var(--risk-red)", text: "#8f1f1f" },
  amber: { bg: "rgba(221,139,22,0.18)", border: "var(--risk-amber)", text: "#7d4c05" },
  green: { bg: "rgba(44,158,87,0.14)", border: "var(--risk-green)", text: "#1c6338" },
};

interface Mark {
  text: string;
  entityId: string;
  risk: RiskLevel;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function ScriptViewer({
  script,
  clearance,
}: {
  script: ParsedScript;
  clearance: ClearanceReport;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [onlyFlagged, setOnlyFlagged] = useState(false);

  const riskByEntity = useMemo(() => {
    const map = new Map<string, RiskLevel>();
    for (const finding of clearance.findings) map.set(finding.entity_id, finding.risk);
    return map;
  }, [clearance.findings]);

  /* Marks are indexed by scene so each scene only pays for its own entities. */
  const marksByScene = useMemo(() => {
    const map = new Map<string, Mark[]>();
    for (const entity of clearance.entities) {
      const risk = riskByEntity.get(entity.id);
      if (!risk) continue;
      for (const sceneNumber of entity.scene_numbers) {
        const list = map.get(sceneNumber) ?? [];
        list.push({ text: entity.text, entityId: entity.id, risk });
        map.set(sceneNumber, list);
      }
    }
    // Longest first, so "Grant Holloway" wins over "Holloway".
    for (const list of map.values()) list.sort((a, b) => b.text.length - a.text.length);
    return map;
  }, [clearance.entities, riskByEntity]);

  const entityById = useMemo(
    () => new Map(clearance.entities.map((e) => [e.id, e])),
    [clearance.entities],
  );
  const findingById = useMemo(
    () => new Map(clearance.findings.map((f) => [f.entity_id, f])),
    [clearance.findings],
  );

  const counts = useMemo(() => {
    const c = { red: 0, amber: 0, green: 0 } as Record<RiskLevel, number>;
    for (const risk of riskByEntity.values()) c[risk] += 1;
    return c;
  }, [riskByEntity]);

  const scenes = onlyFlagged
    ? script.scenes.filter((s) =>
        (marksByScene.get(s.number) ?? []).some((m) => m.risk !== "green"),
      )
    : script.scenes;

  const selectedEntity = selected ? entityById.get(selected) : undefined;
  const selectedFinding = selected ? findingById.get(selected) : undefined;

  return (
    <div className="space-y-6">
      <SectionHead
        label="Annotated script"
        title="Read it with the risks marked"
        aside={
          <div className="flex gap-7">
            <Stat label="Marked" value={riskByEntity.size} />
            <Stat label="Red" value={counts.red} />
          </div>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-[13.5px] leading-relaxed text-[var(--text-2)]">
          Every reference the clearance crew checked is marked where it appears. Click a
          mark to see the verdict and the sources behind it.
        </p>
        <button
          type="button"
          onClick={() => setOnlyFlagged((v) => !v)}
          className={`rounded-full border px-3.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] transition ${
            onlyFlagged
              ? "border-[var(--ink)] bg-[var(--ink)] text-[var(--on-ink)]"
              : "border-[var(--line)] text-[var(--text-2)] hover:border-[var(--ink)]"
          }`}
        >
          {onlyFlagged ? "Showing flagged scenes" : "Show all scenes"}
        </button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.55fr_1fr]">
        <div className="space-y-4">
          {scenes.length === 0 ? (
            <Empty>No scenes carry a flagged reference.</Empty>
          ) : (
            scenes.map((scene) => {
              const marks = marksByScene.get(scene.number) ?? [];
              return (
                <article key={scene.number} className="card overflow-hidden">
                  <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] bg-[var(--paper)] px-4 py-2.5">
                    <span className="font-mono text-[12px] font-medium text-[var(--text)]">
                      {scene.number}. {scene.slugline}
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-3)]">
                      p{scene.page_start} · {scene.eighths}/8
                      {marks.length ? ` · ${marks.length} marked` : ""}
                    </span>
                  </header>

                  <pre className="overflow-x-auto whitespace-pre-wrap px-4 py-3.5 font-mono text-[12.5px] leading-[1.75] text-[var(--text)]">
                    {highlight(scene.raw_text || scene.synopsis, marks, selected, setSelected)}
                  </pre>
                </article>
              );
            })
          )}
        </div>

        <aside className="lg:sticky lg:top-5 lg:self-start">
          {selectedEntity && selectedFinding ? (
            <div className="card p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Eyebrow>{selectedEntity.category.replace(/_/g, " ")}</Eyebrow>
                  <h3 className="mt-1.5 font-[family-name:var(--font-grotesk)] text-xl font-bold uppercase tracking-[-0.02em]">
                    {selectedEntity.text}
                  </h3>
                </div>
                <span
                  className="shrink-0 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em]"
                  style={{
                    borderColor: RISK_STYLE[selectedFinding.risk].border,
                    color: RISK_STYLE[selectedFinding.risk].text,
                    background: RISK_STYLE[selectedFinding.risk].bg,
                  }}
                >
                  {selectedFinding.risk}
                </span>
              </div>

              <p className="mt-3 text-[13.5px] leading-relaxed text-[var(--text)]">
                {selectedFinding.rationale}
              </p>

              <dl className="mt-4 space-y-2.5">
                <Field label="Portrayal">{selectedEntity.portrayal}</Field>
                <Field label="Scenes">{selectedEntity.scene_numbers.join(", ")}</Field>
                {selectedFinding.real_world_matches.length > 0 ? (
                  <Field label="Collides">
                    {selectedFinding.real_world_matches.join("; ")}
                  </Field>
                ) : null}
                {!selectedFinding.searched ? (
                  <Field label="Research">
                    Not researched in this run. Reported unreviewed rather than cleared.
                  </Field>
                ) : null}
              </dl>

              {selectedFinding.suggested_alternatives.length > 0 ? (
                <div className="mt-4">
                  <Eyebrow>Pre-verified replacements</Eyebrow>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {selectedFinding.suggested_alternatives.map((alt) => (
                      <span
                        key={alt}
                        className="rounded-full border border-[var(--lime-deep)] bg-[var(--lime-wash)] px-2.5 py-0.5 font-mono text-[11px] text-[#3d5406]"
                      >
                        {alt}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              {selectedFinding.citations.length > 0 ? (
                <div className="mt-4 border-t border-[var(--line)] pt-3">
                  <Eyebrow>Sources</Eyebrow>
                  <ul className="mt-2 space-y-2">
                    {selectedFinding.citations.map((c, i) => (
                      <li key={i}>
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[12.5px] font-medium text-[var(--blue)] underline underline-offset-2"
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
                </div>
              ) : null}
            </div>
          ) : (
            <div className="card px-5 py-8 text-center">
              <p className="text-[13px] text-[var(--text-2)]">
                Click any marked reference in the script to see its verdict.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {(["red", "amber", "green"] as RiskLevel[]).map((risk) => (
                  <span
                    key={risk}
                    className="rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em]"
                    style={{
                      borderColor: RISK_STYLE[risk].border,
                      color: RISK_STYLE[risk].text,
                      background: RISK_STYLE[risk].bg,
                    }}
                  >
                    {risk} {counts[risk]}
                  </span>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <dt className="w-20 shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-3)]">
        {label}
      </dt>
      <dd className="flex-1 text-[12.5px] leading-relaxed text-[var(--text-2)]">{children}</dd>
    </div>
  );
}

/**
 * Split scene text on the marked references and wrap each hit.
 *
 * One pass with a single alternation regex, rather than a replace per entity,
 * so overlapping names cannot double-wrap. Alternatives are pre-sorted longest
 * first by the caller, which is what makes the longest match win.
 */
function highlight(
  text: string,
  marks: Mark[],
  selected: string | null,
  onSelect: (id: string) => void,
): React.ReactNode {
  if (marks.length === 0 || !text) return text;

  const lookup = new Map<string, Mark>();
  for (const mark of marks) {
    const key = mark.text.toLowerCase();
    if (!lookup.has(key)) lookup.set(key, mark);
  }

  const pattern = new RegExp(`(${marks.map((m) => escapeRegExp(m.text)).join("|")})`, "gi");
  const parts = text.split(pattern);

  return parts.map((part, i) => {
    const mark = lookup.get(part.toLowerCase());
    if (!mark) return part;

    const style = RISK_STYLE[mark.risk];
    const isSelected = selected === mark.entityId;

    return (
      <button
        key={i}
        type="button"
        onClick={() => onSelect(mark.entityId)}
        title={`${mark.risk.toUpperCase()} · click for the verdict`}
        className="rounded-[3px] px-0.5 font-mono transition"
        style={{
          background: style.bg,
          color: style.text,
          borderBottom: `2px solid ${style.border}`,
          outline: isSelected ? `2px solid ${style.border}` : "none",
          outlineOffset: "1px",
        }}
      >
        {part}
      </button>
    );
  });
}
