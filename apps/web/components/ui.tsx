import type { ReactNode } from "react";

/**
 * A headline in the house style: heavy sans caps interrupted by serif italic.
 *
 * Wrap the italic words in asterisks, so the copy stays readable in the JSX:
 *   <Headline>FROM *Script* TO *Call Sheet*</Headline>
 */
export function Headline({
  children,
  className = "",
  onInk = false,
}: {
  children: string;
  className?: string;
  onInk?: boolean;
}) {
  const parts = children.split("*");
  return (
    <span className={`display ${className}`}>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className={`script ${onInk ? "text-[var(--lime)]" : "text-[var(--blue)]"}`}>
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </span>
  );
}

export function Eyebrow({
  children,
  onInk = false,
}: {
  children: ReactNode;
  onInk?: boolean;
}) {
  return <div className={`eyebrow ${onInk ? "eyebrow-on-ink" : ""}`}>{children}</div>;
}

export function SectionHead({
  label,
  title,
  aside,
  onInk = false,
}: {
  label: string;
  title: string;
  aside?: ReactNode;
  onInk?: boolean;
}) {
  return (
    <div
      className={`mb-7 flex flex-col gap-5 border-b pb-5 sm:flex-row sm:items-end sm:justify-between ${
        onInk ? "border-[var(--line-ink)]" : "border-[var(--line)]"
      }`}
    >
      <div>
        <Eyebrow onInk={onInk}>{label}</Eyebrow>
        <h2 className="mt-2 text-[30px] sm:text-[38px]">
          <Headline onInk={onInk}>{title}</Headline>
        </h2>
      </div>
      {aside ? <div className="shrink-0">{aside}</div> : null}
    </div>
  );
}

export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`card p-6 ${className}`}>{children}</div>;
}

export function Stat({
  label,
  value,
  tone = "ink",
  onInk = false,
}: {
  label: string;
  value: ReactNode;
  tone?: "ink" | "blue" | "lime" | "red" | "green";
  onInk?: boolean;
}) {
  const colour =
    tone === "blue"
      ? "text-[var(--blue)]"
      : tone === "lime"
        ? "text-[var(--lime-deep)]"
        : tone === "red"
          ? "text-[var(--risk-red)]"
          : tone === "green"
            ? "text-[var(--risk-green)]"
            : onInk
              ? "text-[var(--on-ink)]"
              : "text-[var(--text)]";

  return (
    <div>
      <Eyebrow onInk={onInk}>{label}</Eyebrow>
      <div className={`display mt-1.5 text-[32px] leading-none ${colour}`}>{value}</div>
    </div>
  );
}

export function Tag({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "lime" | "blue" | "red" | "amber";
}) {
  const styles: Record<string, string> = {
    neutral: "border-[var(--line)] text-[var(--text-2)] bg-[var(--paper)]",
    lime: "border-[var(--lime-deep)] text-[#4a6206] bg-[var(--lime-wash)]",
    blue: "border-[#b9d1f7] text-[var(--blue-deep)] bg-[#eaf2fd]",
    red: "border-[#f0bcbc] text-[var(--risk-red)] bg-[#fdeded]",
    amber: "border-[#f2dcae] text-[#9a5f08] bg-[#fdf4e3]",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] ${styles[tone]}`}
    >
      {children}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-[var(--r-md)] border border-dashed border-[var(--line)] bg-[var(--white)] px-6 py-14 text-center text-sm text-[var(--text-3)]">
      {children}
    </div>
  );
}

/** A big outlined ordinal, the way the reference numbers its steps. */
export function Ordinal({ n, onInk = false }: { n: number; onInk?: boolean }) {
  return (
    <span
      className={`font-mono text-[11px] tracking-[0.1em] ${
        onInk ? "text-[var(--on-ink-2)]" : "text-[var(--text-3)]"
      }`}
    >
      /{String(n).padStart(2, "0")}
    </span>
  );
}

export function money(value: number): string {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

/** Page eighths render the way they are written on a stripboard: 3 4/8. */
export function eighths(total: number): string {
  const pages = Math.floor(total / 8);
  const rest = total % 8;
  if (pages === 0) return `${rest}/8`;
  if (rest === 0) return `${pages}`;
  return `${pages} ${rest}/8`;
}


/** A shooting date as a call sheet prints it: "Mon 14 Sep 2026". */
export function shootDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
