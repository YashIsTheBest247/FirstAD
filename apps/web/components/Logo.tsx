/**
 * The First AD mark.
 *
 * A clapper slate with a numeral 1 in the body: the diagonal teeth make the
 * film context immediate, which matters because "AD" on its own reads as
 * advertisement to anyone outside the industry. The 1 carries the name.
 *
 * Drawn as geometry rather than type so it renders identically everywhere and
 * survives down to a 16px favicon. Three teeth rather than five, because at
 * favicon size more than three turns into grey mush.
 */

export function Logo({
  size = 28,
  className = "",
  body = "var(--lime)",
  ink = "var(--ink)",
}: {
  size?: number;
  className?: string;
  body?: string;
  ink?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      role="img"
      aria-label="First AD"
    >
      <rect x="1.5" y="1.5" width="29" height="29" rx="7" fill={body} />

      {/* Clapper teeth. */}
      <g fill={ink}>
        <path d="M4.2 12.6 L7.6 6.4 H11.2 L7.8 12.6 Z" />
        <path d="M12.2 12.6 L15.6 6.4 H19.2 L15.8 12.6 Z" />
        <path d="M20.2 12.6 L23.6 6.4 H27.2 L23.8 12.6 Z" />
      </g>

      {/* Numeral one, slab serif so it holds its shape when small. */}
      <g fill={ink}>
        <path d="M10.8 17.4 L14.3 15 H17.7 V23.1 H14.3 V19.6 L12.4 20.9 Z" />
        <rect x="10.5" y="23.1" width="11" height="2.6" rx="0.6" />
      </g>
    </svg>
  );
}

/** Mark plus wordmark, as it appears in the nav and the footer. */
export function Wordmark({
  size = 28,
  tone = "lime",
  showRole = false,
}: {
  size?: number;
  tone?: "lime" | "ink";
  showRole?: boolean;
}) {
  const text = tone === "lime" ? "text-[var(--lime)]" : "text-[var(--ink)]";

  return (
    <span className="flex items-center gap-2.5">
      <Logo
        size={size}
        body={tone === "lime" ? "var(--lime)" : "var(--ink)"}
        ink={tone === "lime" ? "var(--ink)" : "var(--paper)"}
      />
      <span className="flex flex-col leading-none">
        <span className={`display text-[20px] tracking-[-0.02em] ${text}`}>First AD</span>
        {showRole ? (
          <span className="mt-0.5 font-mono text-[8.5px] uppercase tracking-[0.2em] text-[var(--on-ink-2)]">
            1st Assistant Director
          </span>
        ) : null}
      </span>
    </span>
  );
}
