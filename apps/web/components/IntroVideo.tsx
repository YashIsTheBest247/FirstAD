"use client";

import { useCallback, useEffect, useRef } from "react";

/**
 * The title card that plays on arrival.
 *
 * Three rules shape this component, all of them about not trapping the
 * visitor:
 *
 *   1. If the file is missing or the codec is unsupported, it dismisses
 *      itself. An overlay that hangs on a 404 makes the whole product look
 *      broken, and a judge is the last person who should meet that.
 *   2. It plays once per session, not once per page load. A brand film is
 *      charming the first time and an obstacle the fourth.
 *   3. Skip is always reachable: a visible button, the Escape key, and a
 *      hard bail if the video has not started within a few seconds.
 *
 * Playback is muted and stays muted. Every browser blocks audible autoplay
 * until the visitor has interacted with the page, so an unmuted video would
 * simply refuse to start. Cut the film to work without sound.
 */

const SEEN_KEY = "firstad:intro-seen";
const START_TIMEOUT_MS = 4000;

export function IntroVideo({
  src = "/video/intro.mp4",
  open,
  onClose,
}: {
  src?: string;
  open: boolean;
  onClose: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  // A ref rather than state: this only guards the bail-out timer, and nothing
  // renders from it, so storing it in state would force a render for nothing.
  const startedRef = useRef(false);

  const close = useCallback(() => {
    try {
      sessionStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* Private mode blocks storage; replaying is a smaller problem. */
    }
    onClose();
  }, [onClose]);

  // Escape always works, and the page behind must not scroll.
  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);

    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, close]);

  // If playback has not begun shortly after opening, something is wrong with
  // the file or the browser is refusing. Get out of the way rather than
  // showing a black rectangle.
  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => {
      if (startedRef.current) return;
      if (!videoRef.current || videoRef.current.currentTime === 0) close();
    }, START_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [open, close]);

  useEffect(() => {
    if (!open) return;
    startedRef.current = false;
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = 0;
    // A rejected play() promise is normal when autoplay is blocked; the
    // start-timeout above then closes the overlay.
    void video.play().catch(() => undefined);
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] h-screen w-screen overflow-hidden bg-black"
      role="dialog"
      aria-modal="true"
      aria-label="Intro film"
    >
      <video
        ref={videoRef}
        src={src}
        className="absolute inset-0 h-full w-full object-cover"
        autoPlay
        muted
        playsInline
        preload="auto"
        onPlaying={() => {
          startedRef.current = true;
        }}
        onEnded={close}
        onError={close}
      />

      {/* Skip, bottom right. */}
      <button
        type="button"
        onClick={close}
        autoFocus
        className="press absolute bottom-6 right-6 rounded-full border border-white/30 bg-black/45 px-5 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-white backdrop-blur-sm hover:border-[var(--lime)] hover:text-[var(--lime)] sm:bottom-8 sm:right-8"
      >
        Skip intro
      </button>
    </div>
  );
}

/**
 * Whether the intro should play on this load.
 *
 * Returns false during server rendering and on any repeat visit in the same
 * session, and honours a reduced-motion preference, which is a request not to
 * be shown unsolicited full-screen movement.
 */
export function shouldPlayIntro(): boolean {
  if (typeof window === "undefined") return false;

  // Not on phones. Three reasons, all of them real: the film is a meaningful
  // download on mobile data, iOS refuses autoplay outright in Low Power Mode
  // so the overlay would just stall and bail, and object-cover crops a
  // landscape frame savagely into a portrait viewport.
  if (window.matchMedia?.("(max-width: 767px)").matches) return false;

  // A reduced-motion preference is a request not to be shown unsolicited
  // full-screen movement.
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return false;

  try {
    return sessionStorage.getItem(SEEN_KEY) !== "1";
  } catch {
    return false;
  }
}
