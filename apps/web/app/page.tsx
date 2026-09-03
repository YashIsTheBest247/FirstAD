"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCrew, getHealth, getSample, streamAnalysis, type HealthStatus } from "@/lib/api";
import type { CrewMember, ProductionPackage, StageTrace } from "@/lib/types";
import { ClearancePanel } from "@/components/ClearancePanel";
import { CrewBoard } from "@/components/CrewBoard";
import { Hero } from "@/components/Hero";
import { Deliverables, Footer, StatsBento, TheProblem } from "@/components/Marketing";
import {
  BreakdownPanel,
  BudgetPanel,
  CallSheetsPanel,
  CompliancePanel,
  LocationsPanel,
} from "@/components/Panels";
import { Stripboard } from "@/components/Stripboard";
import { SubmitCard } from "@/components/SubmitCard";
import { Eyebrow, Headline } from "@/components/ui";

type Tab =
  | "stripboard"
  | "clearance"
  | "locations"
  | "compliance"
  | "budget"
  | "callsheets"
  | "breakdown";

const TABS: { id: Tab; label: string }[] = [
  { id: "stripboard", label: "Stripboard" },
  { id: "clearance", label: "Clearance" },
  { id: "locations", label: "Locations" },
  { id: "compliance", label: "Compliance" },
  { id: "budget", label: "Budget" },
  { id: "callsheets", label: "Call sheets" },
  { id: "breakdown", label: "Breakdown" },
];

export default function Home() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [crew, setCrew] = useState<CrewMember[]>([]);
  const [traces, setTraces] = useState<Record<string, StageTrace>>({});
  const [pkg, setPkg] = useState<ProductionPackage | null>(null);
  const [searches, setSearches] = useState(0);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("stripboard");

  const resultsRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    void getHealth().then(setHealth);
    getCrew()
      .then(setCrew)
      .catch(() => setError("Could not reach the Greenlight API. Is the backend running?"));
  }, []);

  const run = useCallback(async (input: { text: string; filename: string; setting: string }) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setRunning(true);
    setError(null);
    setTraces({});
    setPkg(null);
    setSearches(0);

    document.getElementById("crew")?.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      for await (const event of streamAnalysis(input, controller.signal)) {
        if (event.type === "stage") {
          setTraces((prev) => ({ ...prev, [event.stage.stage]: event.stage }));
        } else if (event.type === "complete") {
          setPkg(event.package);
          setSearches(event.searches_run);
          setTab("stripboard");
          requestAnimationFrame(() =>
            resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
          );
        } else if (event.type === "error") {
          setError(event.message);
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  }, []);

  const loadSample = useCallback(async () => {
    const sample = await getSample();
    return { text: sample.text, filename: sample.filename, setting: sample.setting };
  }, []);

  const geminiMissing = health !== null && !health.gemini_configured;

  return (
    <main>
      <Hero health={health} />
      <TheProblem />
      <StatsBento />

      <div className="space-y-20 sm:space-y-28">
        <SubmitCard
          onRun={run}
          onLoadSample={loadSample}
          running={running}
          disabled={geminiMissing}
          disabledReason={
            geminiMissing
              ? "Gemini is not configured on the API. Set GOOGLE_API_KEY in services/api/.env and restart it."
              : undefined
          }
        />

        {error ? (
          <section className="mx-auto max-w-[1240px] px-5">
            <div className="rounded-[var(--r-md)] border border-[#f0bcbc] bg-[#fdeded] px-5 py-4">
              <Eyebrow>Run failed</Eyebrow>
              <p className="mt-1.5 text-[13.5px] text-[#7a2020]">{error}</p>
            </div>
          </section>
        ) : null}

        {crew.length > 0 ? (
          <CrewBoard crew={crew} traces={traces} searchesRun={searches} />
        ) : null}

        <div ref={resultsRef} id="results">
          {pkg ? (
            <section className="mx-auto max-w-[1240px] px-5">
              <PackageHeader pkg={pkg} searches={searches} />

              <nav className="mb-9 flex flex-wrap gap-1.5 border-b border-[var(--line)] pb-4">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTab(t.id)}
                    className={`rounded-full px-3.5 py-1.5 font-[family-name:var(--font-grotesk)] text-[12px] font-bold uppercase tracking-[0.09em] transition ${
                      tab === t.id
                        ? "bg-[var(--ink)] text-[var(--on-ink)]"
                        : "text-[var(--text-2)] hover:bg-[var(--paper-2)]"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </nav>

              {tab === "stripboard" ? <Stripboard board={pkg.stripboard} /> : null}
              {tab === "clearance" ? <ClearancePanel report={pkg.clearance} /> : null}
              {tab === "locations" ? <LocationsPanel intel={pkg.locations} /> : null}
              {tab === "compliance" ? <CompliancePanel report={pkg.compliance} /> : null}
              {tab === "budget" ? <BudgetPanel budget={pkg.budget} /> : null}
              {tab === "callsheets" ? <CallSheetsPanel sheets={pkg.call_sheets} /> : null}
              {tab === "breakdown" ? <BreakdownPanel breakdown={pkg.breakdown} /> : null}
            </section>
          ) : null}
        </div>

        <Deliverables />
      </div>

      <div className="mt-20 sm:mt-28">
        <Footer />
      </div>
    </main>
  );
}

function PackageHeader({ pkg, searches }: { pkg: ProductionPackage; searches: number }) {
  const { header } = pkg.script;
  const elapsed = pkg.trace.reduce((sum, t) => sum + (t.duration_s ?? 0), 0);
  const reds = pkg.clearance.findings.filter((f) => f.risk === "red").length;

  return (
    <div className="mb-9 overflow-hidden rounded-[var(--r-lg)] bg-[var(--ink)] px-6 py-7 sm:px-9">
      <div className="flex flex-wrap items-end justify-between gap-8">
        <div>
          <Eyebrow onInk>Production package</Eyebrow>
          <h2 className="mt-2 text-[clamp(1.8rem,4vw,2.7rem)] text-[var(--on-ink)]">
            <Headline onInk>{header.title}</Headline>
          </h2>
          <p className="mt-2.5 font-mono text-[11px] text-[var(--on-ink-2)]">
            {header.scene_count} scenes · {header.page_count} pages · {header.format_detected}
            {header.author ? ` · ${header.author}` : ""}
          </p>
        </div>

        <div className="flex flex-wrap gap-8">
          <Metric label="Shoot days" value={pkg.stripboard.shoot_day_count} lime />
          <Metric label="Red flags" value={reds} red={reds > 0} />
          <Metric label="Web sources" value={searches} />
          <Metric label="Crew time" value={`${elapsed.toFixed(0)}s`} />
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  lime,
  red,
}: {
  label: string;
  value: React.ReactNode;
  lime?: boolean;
  red?: boolean;
}) {
  const colour = red
    ? "text-[#ff7a7a]"
    : lime
      ? "text-[var(--lime)]"
      : "text-[var(--on-ink)]";
  return (
    <div>
      <Eyebrow onInk>{label}</Eyebrow>
      <div className={`display mt-1.5 text-[30px] leading-none tracking-[-0.02em] ${colour}`}>
        {value}
      </div>
    </div>
  );
}
