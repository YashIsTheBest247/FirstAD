"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getCrew,
  getDemo,
  getHealth,
  getRun,
  getRuns,
  getSample,
  streamAnalysis,
  type HealthStatus,
  type RunSummary,
} from "@/lib/api";
import type { CrewMember, ProductionPackage, StageTrace } from "@/lib/types";
import { ClearancePanel } from "@/components/ClearancePanel";
import { CrewBoard } from "@/components/CrewBoard";
import { Hero } from "@/components/Hero";
import { IntroVideo, shouldPlayIntro } from "@/components/IntroVideo";
import { Nav } from "@/components/Nav";
import { Deliverables, Footer, StatsBento, TheProblem } from "@/components/Marketing";
import {
  BreakdownPanel,
  BudgetPanel,
  CallSheetsPanel,
  CompliancePanel,
  LocationsPanel,
} from "@/components/Panels";
import { ExportBar, RecordedNotice, RunHistory } from "@/components/RunTools";
import { ScriptViewer } from "@/components/ScriptViewer";
import { Stripboard } from "@/components/Stripboard";
import { SubmitCard } from "@/components/SubmitCard";
import { Eyebrow, Headline } from "@/components/ui";

type Tab =
  | "stripboard"
  | "clearance"
  | "script"
  | "locations"
  | "compliance"
  | "budget"
  | "callsheets"
  | "breakdown";

const TABS: { id: Tab; label: string }[] = [
  { id: "stripboard", label: "Stripboard" },
  { id: "clearance", label: "Clearance" },
  { id: "script", label: "Annotated script" },
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

  const [runs, setRuns] = useState<RunSummary[]>([]);
  // Starts closed so the server and the first client render agree; the
  // decision needs sessionStorage, which only exists in the browser.
  const [introOpen, setIntroOpen] = useState(false);
  const [recordedAt, setRecordedAt] = useState<string | null>(null);

  const resultsRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshRuns = useCallback(() => {
    void getRuns().then(setRuns);
  }, []);

  const showPackage = useCallback(
    (loaded: ProductionPackage, meta: { searches: number; recordedAt: string | null }) => {
      setPkg(loaded);
      setSearches(meta.searches);
      setRecordedAt(meta.recordedAt);
      setTab("stripboard");
      requestAnimationFrame(() =>
        resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    },
    [],
  );

  const openRun = useCallback(
    async (runId: string) => {
      setError(null);
      try {
        const stored = await getRun(runId);
        showPackage(stored.package, {
          searches: stored.searches,
          recordedAt: stored.recorded ? stored.saved_at : null,
        });
        const url = new URL(window.location.href);
        url.searchParams.set("run", runId);
        window.history.replaceState({}, "", url);
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [showPackage],
  );

  const openDemo = useCallback(async () => {
    setError(null);
    try {
      const stored = await getDemo();
      showPackage(stored.package, { searches: stored.searches, recordedAt: stored.saved_at });
    } catch (err) {
      setError((err as Error).message);
    }
  }, [showPackage]);

  useEffect(() => {
    if (shouldPlayIntro()) setIntroOpen(true);
  }, []);

  useEffect(() => {
    void getHealth().then(setHealth);
    getCrew()
      .then(setCrew)
      .catch(() => setError("Could not reach the First AD API. Is the backend running?"));
    refreshRuns();

    // A permalink opens straight into that package. Deferred out of the effect
    // body because openRun clears the error state synchronously, and a setState
    // during mount cascades an extra render before the first paint.
    const requested = new URLSearchParams(window.location.search).get("run");
    if (!requested) return;

    const timer = window.setTimeout(() => void openRun(requested), 0);
    return () => window.clearTimeout(timer);
  }, [openRun, refreshRuns]);

  const run = useCallback(
    async (input: {
      text: string;
      filename: string;
      setting: string;
      start_date?: string;
    }) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setRunning(true);
      setError(null);
      setTraces({});
      setPkg(null);
      setSearches(0);
      setRecordedAt(null);

      document.getElementById("crew")?.scrollIntoView({ behavior: "smooth", block: "start" });

      try {
        for await (const event of streamAnalysis(input, controller.signal)) {
          if (event.type === "stage") {
            setTraces((prev) => ({ ...prev, [event.stage.stage]: event.stage }));
          } else if (event.type === "complete") {
            showPackage(event.package, { searches: event.searches_run, recordedAt: null });
            refreshRuns();
            const url = new URL(window.location.href);
            url.searchParams.set("run", event.run_id);
            window.history.replaceState({}, "", url);
          } else if (event.type === "error") {
            setError(event.message);
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") setError((err as Error).message);
      } finally {
        setRunning(false);
      }
    },
    [refreshRuns, showPackage],
  );

  const loadSample = useCallback(async () => {
    const sample = await getSample();
    return { text: sample.text, filename: sample.filename, setting: sample.setting };
  }, []);

  const geminiMissing = health !== null && !health.gemini_configured;

  return (
    <main>
      <IntroVideo open={introOpen} onClose={() => setIntroOpen(false)} />
      <Nav />
      <Hero health={health} onReplayIntro={() => setIntroOpen(true)} />
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

        {/* Without keys the pipeline cannot run, so offer the captured run
            rather than leaving a dead interface. */}
        {!pkg && !running ? (
          <section className="mx-auto max-w-[1240px] px-5">
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--r-md)] border border-dashed border-[var(--line)] px-5 py-4">
              <p className="text-[13px] text-[var(--text-2)]">
                {geminiMissing
                  ? "No keys configured. You can still look at a package the crew produced earlier."
                  : "Want to see a finished package before running one?"}
              </p>
              <button type="button" onClick={openDemo} className="pill pill-ghost">
                Open a recorded run
              </button>
            </div>
          </section>
        ) : null}

        {error ? (
          <section className="mx-auto max-w-[1240px] px-5">
            <div className="rounded-[var(--r-md)] border border-[#f0bcbc] bg-[#fdeded] px-5 py-4">
              <Eyebrow>Something went wrong</Eyebrow>
              <p className="mt-1.5 text-[13.5px] text-[#7a2020]">{error}</p>
            </div>
          </section>
        ) : null}

        {/* The anchor lives here rather than inside CrewBoard, which only
            renders once /api/crew resolves. Navigation must not dead-end
            because a fetch failed. */}
        <section id="crew">
          {crew.length > 0 ? (
            <CrewBoard crew={crew} traces={traces} searchesRun={searches} />
          ) : (
            <div id="how" className="mx-auto max-w-[1240px] px-5">
              <div className="rounded-[var(--r-md)] border border-dashed border-[var(--line)] px-5 py-8 text-center">
                <Eyebrow>The crew</Eyebrow>
                <p className="mt-2 text-[13.5px] text-[var(--text-2)]">
                  Waiting on the API to list the nine agents. If this does not fill in, the
                  backend is unreachable.
                </p>
              </div>
            </div>
          )}
        </section>

        <div ref={resultsRef} id="results">
          {pkg ? (
            <section className="mx-auto max-w-[1240px] px-5">
              {recordedAt !== null ? <RecordedNotice savedAt={recordedAt} /> : null}

              <PackageHeader pkg={pkg} searches={searches} />

              <nav className="mb-6 flex flex-wrap gap-1.5 border-b border-[var(--line)] pb-4">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTab(t.id)}
                    className={`press rounded-full px-3.5 py-1.5 font-[family-name:var(--font-grotesk)] text-[12px] font-bold uppercase tracking-[0.09em] ${
                      tab === t.id
                        ? "bg-[var(--ink)] text-[var(--on-ink)]"
                        : "text-[var(--text-2)] hover:bg-[var(--paper-2)]"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </nav>

              <div className="mb-9">
                <ExportBar runId={pkg.run_id} recorded={recordedAt !== null} />
              </div>

              {/* Keyed on the tab so the panel remounts and replays its
                  enter animation, which makes the switch feel like a move
                  rather than a repaint. */}
              <div key={tab} className="rise">
              {tab === "stripboard" ? <Stripboard board={pkg.stripboard} /> : null}
              {tab === "clearance" ? <ClearancePanel report={pkg.clearance} /> : null}
              {tab === "script" ? (
                <ScriptViewer script={pkg.script} clearance={pkg.clearance} />
              ) : null}
              {tab === "locations" ? <LocationsPanel intel={pkg.locations} /> : null}
              {tab === "compliance" ? <CompliancePanel report={pkg.compliance} /> : null}
              {tab === "budget" ? <BudgetPanel budget={pkg.budget} /> : null}
              {tab === "callsheets" ? <CallSheetsPanel sheets={pkg.call_sheets} /> : null}
              {tab === "breakdown" ? <BreakdownPanel breakdown={pkg.breakdown} /> : null}
              </div>
            </section>
          ) : null}
        </div>

        <RunHistory runs={runs} activeRunId={pkg?.run_id ?? null} onOpen={openRun} />

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
  lime = false,
  red = false,
}: {
  label: string;
  value: React.ReactNode;
  lime?: boolean;
  red?: boolean;
}) {
  const colour = red
    ? "text-[#ff8a8a]"
    : lime
      ? "text-[var(--lime)]"
      : "text-[var(--on-ink)]";
  return (
    <div>
      <Eyebrow onInk>{label}</Eyebrow>
      <div
        className={`mt-1.5 font-[family-name:var(--font-grotesk)] text-3xl font-extrabold leading-none tracking-[-0.03em] ${colour}`}
      >
        {value}
      </div>
    </div>
  );
}
