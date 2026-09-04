"use client";

import { useState } from "react";
import { Headline, Ordinal } from "./ui";

/* -------------------------------------------------------------------------
   The problem, stated once, in the reference's two-tone paragraph treatment:
   the first clause carries full contrast, the rest drops back.
   ------------------------------------------------------------------------- */

export function TheProblem() {
  return (
    <section className="mx-auto max-w-[1240px] px-5 py-20 sm:py-28">
      <div className="grid gap-10 lg:grid-cols-[200px_1fr]">
        <div>
          <p className="text-[13px]">
            <span className="display text-[13px] tracking-[0.02em]">The </span>
            <span className="script text-[15px] text-[var(--blue)]">gap</span>
          </p>
        </div>
        <p className="max-w-3xl text-[clamp(1.35rem,2.6vw,2rem)] leading-[1.32] tracking-[-0.01em]">
          <span className="text-[var(--text)]">
            Between a finished draft and a first day of photography sits two to three weeks
            of work nobody has automated.
          </span>{" "}
          <span className="text-[var(--text-3)]">
            A 1st AD tags every prop and stunt onto a breakdown sheet, then packs the scenes
            into days that minimise company moves without stranding an actor on hold pay. A
            clearance researcher checks every name, business, plate and address against the
            real world, because no film gets insured without it. A line producer turns all
            of it into a top sheet a financier will read.
          </span>
        </p>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------
   Bento: two headline numbers and three image cards, laid out asymmetrically
   the way the reference does.
   ------------------------------------------------------------------------- */

export function StatsBento() {
  return (
    <section className="mx-auto max-w-[1240px] px-5 pb-20 sm:pb-28">
      <div className="grid gap-4 lg:grid-cols-4">
        {/* Number, top left */}
        <div className="flex flex-col justify-between lg:col-span-1">
          <div>
            <div className="display text-[clamp(3.4rem,7vw,5.2rem)] leading-[0.86] tracking-[-0.04em]">
              9
            </div>
            <p className="mt-2 text-[13px] leading-snug text-[var(--text-2)]">
              Agents in the crew, each standing in for a real job on a production.
            </p>
          </div>

          <div className="mt-6 overflow-hidden rounded-[var(--r-md)]">
            <div className="relative">
              <img
                src="/img/cinema-neon.jpg"
                alt="A cinema frontage lit in neon"
                className="h-56 w-full object-cover"
              />
              <div className="absolute inset-x-3 bottom-3 flex flex-wrap gap-1.5">
                <Chip>Breakdown</Chip>
                <Chip>Clearance</Chip>
              </div>
            </div>
          </div>
        </div>

        {/* Pale product card, centre */}
        <div className="lg:col-span-1">
          <div className="flex h-full flex-col items-center justify-between rounded-[var(--r-md)] border border-[var(--line)] bg-[#f7f9ee] p-6">
            <img
              src="/img/reels.jpg"
              alt="Reels of film on a white surface"
              className="w-full rounded-[var(--r-sm)] object-cover"
            />
            <p className="mt-5 text-center text-[13px] leading-relaxed text-[var(--text-2)]">
              Typed contracts between every stage, so nothing downstream has to re-read prose.
            </p>
            <a href="#how" className="pill pill-lime mt-5">
              How it works
            </a>
          </div>
        </div>

        {/* Wide image, right */}
        <div className="lg:col-span-2">
          <div className="relative h-full overflow-hidden rounded-[var(--r-md)]">
            <img
              src="/img/audience.jpg"
              alt="An audience seated in a cinema"
              className="h-full min-h-[19rem] w-full object-cover"
            />
            <div className="absolute inset-x-4 top-4 flex flex-wrap gap-1.5">
              <Chip>Stripboard</Chip>
              <Chip>Day out of days</Chip>
              <Chip>Call sheets</Chip>
            </div>
            <div className="absolute inset-x-4 bottom-4 rounded-[var(--r-sm)] bg-white/92 px-4 py-3 backdrop-blur-sm">
              <div className="display text-[clamp(2rem,4vw,3rem)] leading-none tracking-[-0.03em]">
                $2–5K
              </div>
              <p className="mt-1 text-[12.5px] text-[var(--text-2)]">
                What a single script clearance report costs, and it takes five to ten
                business days.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full bg-white/88 px-2.5 py-1 font-mono text-[9.5px] uppercase tracking-[0.1em] text-[var(--ink)] backdrop-blur-sm">
      {children}
    </span>
  );
}

/* -------------------------------------------------------------------------
   Deliverables accordion, in the reference's numbered-row pattern.
   ------------------------------------------------------------------------- */

const DELIVERABLES = [
  {
    title: "The stripboard",
    body: "Every scene as a coloured strip, grouped into shooting days that minimise company moves and keep night work contiguous. A deterministic optimiser proposes the board; the Scheduler agent applies the judgement an optimiser cannot encode.",
    meta: ["Day out of days", "Company moves", "Hold-day exposure"],
  },
  {
    title: "The clearance report",
    body: "Every name, business, phone number, plate and address in the script, checked against the live web and graded red, amber or green. Every verdict carries the sources it was reached from, and suggested replacements are themselves searched before they are offered.",
    meta: ["Cited", "Risk graded", "Replacements verified"],
  },
  {
    title: "The budget top sheet",
    body: "Above the line, below the line, and post, scaled to the shoot-day count from the schedule. Every line names what in the script drives the cost, and permit figures come from the location research rather than a guess.",
    meta: ["15 to 25 lines", "Contingency", "Stated assumptions"],
  },
  {
    title: "The call sheets",
    body: "One per shooting day, with a crew call worked back from the day's rigging load, cast calls that allow for makeup and wardrobe, department pre-calls, and safety notes drawn from the flagged breakdown elements.",
    meta: ["Per day", "Safety notes", "Weather"],
  },
];

export function Deliverables() {
  const [open, setOpen] = useState(0);

  return (
    <section id="how" className="mx-auto max-w-[1240px] px-5 pb-20 sm:pb-28">
      <div className="grid gap-10 lg:grid-cols-2 lg:items-start">
        <div>
          <h2 className="max-w-md text-[clamp(2rem,4.4vw,3.1rem)]">
            <Headline>What comes *back* when the crew wraps</Headline>
          </h2>

          <div className="mt-9 divide-y divide-[var(--line)] border-t border-[var(--line)]">
            {DELIVERABLES.map((d, i) => {
              const isOpen = open === i;
              return (
                <div key={d.title} className="py-4">
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? -1 : i)}
                    className="flex w-full items-center gap-4 text-left"
                    aria-expanded={isOpen}
                  >
                    <Ordinal n={i + 1} />
                    <span
                      className={`flex-1 text-[16.5px] transition ${
                        isOpen ? "text-[var(--text)]" : "text-[var(--text-2)]"
                      }`}
                    >
                      {d.title}
                    </span>
                    <span
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border transition ${
                        isOpen
                          ? "border-[var(--lime)] bg-[var(--lime)] text-[var(--ink)]"
                          : "border-[var(--line)] text-[var(--text-2)]"
                      }`}
                    >
                      <span className={`text-[11px] transition ${isOpen ? "rotate-180" : ""}`}>
                        ▾
                      </span>
                    </span>
                  </button>

                  {isOpen ? (
                    <div className="rise mt-3 pl-[3.1rem]">
                      <p className="max-w-lg text-[13.5px] leading-relaxed text-[var(--text-2)]">
                        {d.body}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {d.meta.map((m) => (
                          <span
                            key={m}
                            className="rounded-full border border-[var(--line)] bg-[var(--paper)] px-2.5 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.1em] text-[var(--text-2)]"
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>

        <div className="overflow-hidden rounded-[var(--r-lg)]">
          <img
            src="/img/seats-red.jpg"
            alt="Rows of red cinema seats"
            className="h-full min-h-[26rem] w-full object-cover"
          />
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------
   Footer, with the wordmark ghosted into the image the way the reference does.
   ------------------------------------------------------------------------- */

export function Footer() {
  return (
    <footer className="px-3 pb-3 sm:px-5 sm:pb-5">
      <div className="relative overflow-hidden rounded-[var(--r-xl)] bg-[var(--ink)]">
        <img
          src="/img/screen-dark.jpg"
          alt=""
          aria-hidden
          className="absolute inset-0 h-full w-full object-cover opacity-25"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[var(--ink)] via-[var(--ink)]/85 to-transparent" />

        <div className="relative px-6 py-14 sm:px-14 sm:py-16">
          <div className="mx-auto max-w-lg text-center">
            <h2 className="text-[clamp(1.85rem,4.2vw,2.9rem)] text-[var(--on-ink)]">
              <Headline onInk>Ready to *roll*?</Headline>
            </h2>
            <p className="mx-auto mt-4 max-w-sm text-[13.5px] leading-relaxed text-[var(--on-ink-2)]">
              Load the sample screenplay and watch nine agents turn it into a shooting
              schedule, a clearance report and a call sheet.
            </p>
            <a href="#submit" className="pill pill-lime mt-7">
              Break down a script
            </a>
          </div>

          {/* The ghosted wordmark, bled off the bottom edge. */}
          <div
            aria-hidden
            className="pointer-events-none mt-9 select-none overflow-hidden text-center"
          >
            <span className="display block text-[clamp(2rem,6.5vw,4.5rem)] leading-[0.74] tracking-[-0.05em] text-white/[0.09]">
              First AD
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
