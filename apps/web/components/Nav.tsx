"use client";

import { useEffect, useState } from "react";
import { Wordmark } from "./Logo";

/**
 * The top bar.
 *
 * Fixed rather than sticky on purpose: it used to live inside the hero's
 * `overflow-hidden` block, where `position: sticky` is inert, so it scrolled
 * away and there was no way back to the top of a long page.
 *
 * It is transparent while the hero is under it and takes on an ink background
 * once the page scrolls, so the wordmark stays legible against both the blue
 * photograph and the paper ground below it.
 *
 * The links were previously `hidden md:flex` with nothing in their place,
 * which made every section unreachable on a phone. Now they collapse into a
 * disclosure.
 */

const LINKS: [label: string, href: string][] = [
  ["The crew", "#crew"],
  ["How it works", "#how"],
  ["The package", "#results"],
  ["Sample", "#submit"],
];

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<string>("");

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  /* Highlight whichever section is currently in view. Without this a fixed bar
     is just decoration on a long single page. */
  useEffect(() => {
    const targets = LINKS.map(([, href]) => document.querySelector(href)).filter(
      (el): el is Element => el !== null,
    );
    if (targets.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target.id) setActive(`#${visible.target.id}`);
      },
      // Bias the band towards the upper middle of the viewport so the section
      // you are reading wins, not the one just entering from the bottom.
      { rootMargin: "-88px 0px -55% 0px", threshold: [0.1, 0.5] },
    );

    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  }, []);

  // Close the mobile sheet on escape, and stop the page scrolling behind it.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        scrolled || open
          ? "border-b border-[var(--line-ink)] bg-[var(--ink)]/95 backdrop-blur-md"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <nav className="mx-auto flex max-w-[1400px] items-center justify-between gap-4 px-5 py-3.5 sm:px-8">
        <a href="#top" className="press shrink-0" onClick={() => setOpen(false)}>
          <Wordmark size={26} tone="lime" showRole />
        </a>

        <div className="hidden items-center gap-7 md:flex">
          {LINKS.map(([label, href]) => (
            <a
              key={href}
              href={href}
              className={`press text-[13.5px] transition-colors ${
                active === href
                  ? "text-[var(--lime)]"
                  : "text-white/80 hover:text-white"
              }`}
            >
              {label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <a
            href="#submit"
            className="pill hidden border border-white/35 bg-white/12 text-white backdrop-blur-sm hover:bg-white/20 sm:inline-flex"
          >
            Run a script
          </a>

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="nav-sheet"
            aria-label={open ? "Close menu" : "Open menu"}
            className="press flex h-10 w-10 items-center justify-center rounded-full border border-white/30 text-white md:hidden"
          >
            <Burger open={open} />
          </button>
        </div>
      </nav>

      {/* Mobile disclosure. */}
      <div
        id="nav-sheet"
        hidden={!open}
        className="border-t border-[var(--line-ink)] bg-[var(--ink)] px-5 pb-5 pt-2 md:hidden"
      >
        <ul className="flex flex-col">
          {LINKS.map(([label, href]) => (
            <li key={href}>
              <a
                href={href}
                onClick={() => setOpen(false)}
                className={`block border-b border-[var(--line-ink)] py-3.5 text-[15px] ${
                  active === href ? "text-[var(--lime)]" : "text-white/85"
                }`}
              >
                {label}
              </a>
            </li>
          ))}
        </ul>
        <a
          href="#submit"
          onClick={() => setOpen(false)}
          className="pill pill-lime mt-4 w-full justify-center"
        >
          Run a script
        </a>
      </div>
    </header>
  );
}

/** Two bars that cross into an X. Cheaper than shipping an icon set for one glyph. */
function Burger({ open }: { open: boolean }) {
  return (
    <span className="relative block h-3.5 w-4.5" aria-hidden>
      <span
        className="absolute left-0 block h-[1.5px] w-full bg-current transition-transform duration-200"
        style={{ top: open ? "50%" : "2px", transform: open ? "rotate(45deg)" : "none" }}
      />
      <span
        className="absolute left-0 block h-[1.5px] w-full bg-current transition-transform duration-200"
        style={{ bottom: open ? "50%" : "2px", transform: open ? "rotate(-45deg)" : "none" }}
      />
    </span>
  );
}
