"use client";

import type { HealthStatus } from "@/lib/api";
import { Wordmark } from "./Logo";

/**
 * The hero follows the reference layout: navigation inside the coloured block,
 * a full-bleed photograph with a single strong object at its centre, and a
 * two-line headline that alternates heavy sans caps with serif italic.
 *
 * The reference marks its left and right edges with dashed ticks. Here those
 * become film perforations, which is the same rhythm doing thematic work.
 */
export function Hero({ health }: { health: HealthStatus | null }) {
  return (
    <section id="top" className="px-3 pt-3 sm:px-5 sm:pt-5">
      <div className="relative overflow-hidden rounded-[var(--r-xl)] bg-[var(--blue-deep)]">
        {/* Photograph */}
        <div className="absolute inset-0">
          <img
            src="/img/hero-clapper.jpg"
            alt="A film slate held up against an open sky"
            className="h-full w-full object-cover object-[center_38%]"
          />
          {/* Graded so the sky reads as the brand blue and the type stays legible. */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(178deg, rgba(11,71,173,0.80) 0%, rgba(26,106,232,0.52) 38%, rgba(11,45,110,0.72) 100%)",
            }}
          />
        </div>

        <Perforations side="left" />
        <Perforations side="right" />

        <Nav />

        <div className="relative px-6 pt-10 pb-8 sm:px-14 sm:pt-14">
          <h1 className="max-w-5xl">
            <span className="block text-[clamp(2.7rem,8.4vw,6.4rem)] leading-[0.94]">
              <span className="display text-[var(--lime)]">Where </span>
              <span className="script text-white">Script</span>
            </span>
            <span className="block text-[clamp(2.7rem,8.4vw,6.4rem)] leading-[0.94]">
              <span className="script text-white">Meets </span>
              <span className="display text-[var(--lime)]">Schedule</span>
            </span>
          </h1>

          <a href="#submit" className="pill pill-lime mt-8">
            Break down a script
          </a>

          {/* Bottom band: a headline stat on the left, live provider state on
              the right, mirroring the reference's stat and play-button pair. */}
          <div className="mt-16 flex flex-col gap-8 sm:mt-24 sm:flex-row sm:items-end sm:justify-between">
            <div className="max-w-xs">
              <p className="text-[38px] leading-none text-white">
                <span className="script">Nine</span>
                <span className="display ml-2 text-[30px] tracking-[-0.02em]">agents</span>
              </p>
              <p className="mt-3 text-[12.5px] leading-relaxed text-white/80">
                Script breakdown, scheduling, and clearance are the unautomated gap between a
                finished draft and a first day of principal photography. This closes it in
                about two minutes.
              </p>
            </div>

            <div className="flex items-center gap-3.5">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--lime)]">
                <StripGlyph />
              </span>
              <div className="flex flex-col gap-1">
                <Lamp on={!!health?.gemini_configured} label={geminiLabel(health)} />
                <Lamp on={!!health?.parallel_configured} label={parallelLabel(health)} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Nav() {
  return (
    <nav className="relative flex items-center justify-between px-6 pt-6 sm:px-14">
      <a href="#top" className="flex items-center gap-2.5">
        <Wordmark size={28} tone="lime" />
      </a>

      <div className="hidden items-center gap-8 md:flex">
        {[
          ["The crew", "#crew"],
          ["How it works", "#how"],
          ["The package", "#results"],
          ["Sample", "#submit"],
        ].map(([label, href]) => (
          <a
            key={href}
            href={href}
            className="text-[13.5px] text-white/85 transition hover:text-white"
          >
            {label}
          </a>
        ))}
      </div>

      <a
        href="#submit"
        className="pill border border-white/35 bg-white/12 text-white backdrop-blur-sm hover:bg-white/20"
      >
        Run a script
      </a>
    </nav>
  );
}

function geminiLabel(health: HealthStatus | null): string {
  if (!health) return "Checking Gemini";
  if (!health.gemini_configured) return "Gemini not configured";
  return `Gemini · ${health.gemini_backend}`;
}

function parallelLabel(health: HealthStatus | null): string {
  if (!health) return "Checking Parallel";
  return health.parallel_configured ? "Parallel Search · live" : "Parallel not configured";
}

function Lamp({ on, label }: { on: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className="h-1.5 w-1.5 shrink-0 rounded-full"
        style={{
          background: on ? "var(--lime)" : "rgba(255,255,255,0.5)",
          boxShadow: on ? "0 0 8px var(--lime)" : "none",
        }}
      />
      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-white/85">
        {label}
      </span>
    </span>
  );
}

/** The four stripboard colours as a tiny rack, used as the brand glyph. */
function StripGlyph() {
  return (
    <span className="flex gap-[2px]">
      {["#ffffff", "#fbe58f", "#aecbf5", "#a9dcb6"].map((c) => (
        <span
          key={c}
          className="block h-4 w-[3px] rounded-[1px] border border-black/15"
          style={{ background: c }}
        />
      ))}
    </span>
  );
}

/** Film perforations down an edge, standing in for the reference's tick marks. */
function Perforations({ side }: { side: "left" | "right" }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute top-0 bottom-0 hidden w-6 flex-col items-center justify-center gap-3.5 sm:flex ${
        side === "left" ? "left-1" : "right-1"
      }`}
    >
      {Array.from({ length: 12 }).map((_, i) => (
        <span key={i} className="block h-3.5 w-2.5 rounded-[2px] bg-white/22" />
      ))}
    </div>
  );
}
