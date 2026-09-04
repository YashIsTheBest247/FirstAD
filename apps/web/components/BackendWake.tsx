"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getHealth, type HealthStatus } from "@/lib/api";

/**
 * Keeps the API awake while someone is on the page, and says something
 * truthful while it wakes.
 *
 * The API runs on a free instance that sleeps after fifteen minutes idle and
 * takes roughly a minute to come back. Two separate problems follow from that,
 * and this handles both:
 *
 *   Sleeping mid-visit. Somebody reads the page for twenty minutes, then
 *   submits a script and hits a cold start. A poll on a twelve minute interval
 *   sits comfortably inside the fifteen minute window and prevents it.
 *
 *   Arriving cold. The first visitor of the hour waits about a minute with no
 *   explanation, which reads as broken rather than as waking. The overlay
 *   below only appears when the first probe is genuinely slow, so a warm
 *   instance never shows it.
 *
 * What this cannot do: keep the instance alive when nobody has the site open.
 * A browser cannot ping anything once the tab is closed. Preventing sleep
 * around the clock needs an external pinger, and there is a note about that in
 * the README.
 */

const PING_INTERVAL_MS = 12 * 60 * 1000;

// Below this, showing a "waking up" panel would be a flash of noise on an
// instance that was already awake.
const SLOW_AFTER_MS = 1500;

/** Written to be accurate. Each line names something that is actually happening. */
const WAKING_LINES = [
  "Reaching the production office",
  "Waking the server, it sleeps when idle",
  "Starting the container",
  "Loading nine agents",
  "Checking Gemini and Parallel",
  "Almost there, a cold start takes about a minute",
];

export type WakeState = "checking" | "waking" | "online" | "offline";

export function useBackendWake(onHealth: (h: HealthStatus | null) => void) {
  const [state, setState] = useState<WakeState>("checking");
  const slowTimer = useRef<number | null>(null);
  const everOnline = useRef(false);

  const ping = useCallback(async () => {
    // Only claim to be waking if this is the first contact. A later poll that
    // is slow should not throw an overlay over someone mid-read.
    if (!everOnline.current) {
      slowTimer.current = window.setTimeout(() => setState("waking"), SLOW_AFTER_MS);
    }

    const health = await getHealth();

    if (slowTimer.current) {
      window.clearTimeout(slowTimer.current);
      slowTimer.current = null;
    }

    onHealth(health);
    if (health) {
      everOnline.current = true;
      setState("online");
    } else {
      setState(everOnline.current ? "online" : "offline");
    }
  }, [onHealth]);

  useEffect(() => {
    // Deferred so the first probe does not update state during mount.
    const first = window.setTimeout(() => void ping(), 0);

    const id = window.setInterval(() => void ping(), PING_INTERVAL_MS);

    // Background tabs get their timers throttled hard, so a tab left open for
    // an hour may have missed several polls. Probe again on return.
    const onVisible = () => {
      if (document.visibilityState === "visible") void ping();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      window.clearTimeout(first);
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
      if (slowTimer.current) window.clearTimeout(slowTimer.current);
    };
  }, [ping]);

  return state;
}

export function WakingOverlay({ state }: { state: WakeState }) {
  // Mounted only while it should be on screen, so its counters start fresh
  // every time rather than needing a reset inside an effect.
  if (state !== "waking" && state !== "offline") return null;
  return <WakingPanel failed={state === "offline"} />;
}

function WakingPanel({ failed }: { failed: boolean }) {
  const [line, setLine] = useState(0);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const lines = window.setInterval(
      () => setLine((i) => (i + 1) % WAKING_LINES.length),
      2600,
    );
    const clock = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => {
      window.clearInterval(lines);
      window.clearInterval(clock);
    };
  }, []);

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-[var(--ink)]/95 backdrop-blur-sm">
      <div className="w-full max-w-md px-8 text-center">
        {/* A strip of cells filling left to right, like film running through a
            gate. Indeterminate on purpose: we cannot know how long a cold
            start will take, and a fake progress bar that stalls at 90% is
            worse than none. */}
        <div className="mx-auto mb-8 flex w-fit gap-1.5" aria-hidden>
          {Array.from({ length: 8 }).map((_, i) => (
            <span
              key={i}
              className="block h-5 w-2.5 rounded-[2px] bg-[var(--lime)] opacity-25"
              style={{
                animation: failed ? "none" : "gate 1.4s ease-in-out infinite",
                animationDelay: `${i * 0.11}s`,
              }}
            />
          ))}
        </div>

        {failed ? (
          <>
            <p className="font-[family-name:var(--font-grotesk)] text-[22px] font-bold uppercase tracking-[-0.02em] text-[var(--on-ink)]">
              Cannot reach the API
            </p>
            <p className="mt-3 text-[13.5px] leading-relaxed text-[var(--on-ink-2)]">
              The production office is not answering. It may still be starting up, or the
              backend may be down.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="pill pill-lime mt-6"
            >
              Try again
            </button>
          </>
        ) : (
          <>
            <p
              key={line}
              className="rise font-[family-name:var(--font-grotesk)] text-[20px] font-bold uppercase tracking-[-0.015em] text-[var(--on-ink)]"
            >
              {WAKING_LINES[line]}
            </p>
            <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--on-ink-2)]">
              {seconds}s
            </p>
            <p className="mx-auto mt-6 max-w-xs text-[12.5px] leading-relaxed text-[var(--on-ink-2)]">
              The API sleeps when nobody has used it for a quarter of an hour. This only
              happens on the first visit.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
