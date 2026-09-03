"use client";

import { useRef, useState } from "react";
import { Eyebrow, Headline } from "./ui";

export function SubmitCard({
  onRun,
  onLoadSample,
  running,
  disabled,
  disabledReason,
}: {
  onRun: (input: {
    text: string;
    filename: string;
    setting: string;
    start_date?: string;
  }) => void;
  onLoadSample: () => Promise<{ text: string; filename: string; setting: string }>;
  running: boolean;
  disabled: boolean;
  disabledReason?: string;
}) {
  const [text, setText] = useState("");
  const [filename, setFilename] = useState("untitled.fountain");
  const [setting, setSetting] = useState("Chicago, Illinois");
  // Empty means "let the API pick", which is the Monday after next.
  const [startDate, setStartDate] = useState("");
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const scenes = (text.match(/^\s*(INT|EXT|I\/E)[.\-\s]/gim) ?? []).length;
  const pages = text ? Math.max(1, Math.round(text.length / 1800)) : 0;
  const ready = text.trim().length > 40 && !running && !disabled;

  async function ingest(file: File) {
    if (file.name.toLowerCase().endsWith(".pdf")) {
      setNotice("PDF ingestion runs server side. Paste the text, or upload .fountain or .txt.");
      return;
    }
    setText(await file.text());
    setFilename(file.name);
    setNotice(null);
  }

  async function loadSample() {
    const sample = await onLoadSample();
    setText(sample.text);
    setFilename(sample.filename);
    setSetting(sample.setting);
    setNotice(null);
  }

  return (
    <section id="submit" className="mx-auto max-w-[1240px] px-5">
      <div className="card-lg overflow-hidden">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--line)] px-6 py-5 sm:px-8">
          <div>
            <Eyebrow>Step one</Eyebrow>
            <h2 className="mt-2 text-[30px] sm:text-[34px]">
              <Headline>Hand over the *draft*</Headline>
            </h2>
          </div>
          <button type="button" onClick={loadSample} disabled={running} className="pill pill-ghost">
            Load sample script
          </button>
        </div>

        <div className="grid gap-0 lg:grid-cols-[1.55fr_1fr]">
          {/* Script input */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              const file = e.dataTransfer.files?.[0];
              if (file) void ingest(file);
            }}
            className={`relative border-b border-[var(--line)] transition lg:border-b-0 lg:border-r ${
              dragging ? "bg-[var(--lime-wash)]" : "bg-[var(--white)]"
            }`}
          >
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
              placeholder={
                "Paste the screenplay here, or drop a .fountain or .txt file.\n\nINT. PROJECTION BOOTH - NIGHT\n\nA cramped room, hot as an engine block."
              }
              className="h-[19rem] w-full resize-y bg-transparent p-6 font-mono text-[12.5px] leading-relaxed text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none sm:p-8"
            />

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line)] bg-[var(--paper)] px-6 py-3 sm:px-8">
              <div className="flex items-center gap-4 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-3)]">
                <span className="text-[var(--text-2)]">{filename}</span>
                {scenes > 0 ? <span>{scenes} sluglines</span> : null}
                {pages > 0 ? <span>~{pages} pages</span> : null}
              </div>
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-2)] underline underline-offset-4 transition hover:text-[var(--text)]"
              >
                Choose a file
              </button>
              <input
                ref={fileInput}
                type="file"
                accept=".fountain,.txt,.fdx,.spmd,text/plain"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void ingest(file);
                }}
              />
            </div>
          </div>

          {/* Settings and launch */}
          <div className="flex flex-col justify-between gap-6 bg-[var(--paper)] p-6 sm:p-8">
            <div>
              <label>
                <Eyebrow>Production base</Eyebrow>
                <input
                  value={setting}
                  onChange={(e) => setSetting(e.target.value)}
                  placeholder="Chicago, Illinois"
                  className="mt-2 w-full rounded-[var(--r-sm)] border border-[var(--line)] bg-[var(--white)] px-3.5 py-2.5 text-[14px] text-[var(--text)] placeholder:text-[var(--text-3)] focus:border-[var(--ink)] focus:outline-none"
                />
              </label>
              <p className="mt-3 text-[12.5px] leading-relaxed text-[var(--text-2)]">
                Where you intend to shoot. This drives the permit research and the clearance
                searches, because a name only becomes a legal problem in a place. An
                alderman in Chicago is not an alderman in Atlanta.
              </p>

              <label className="mt-5 block">
                <Eyebrow>First day of photography</Eyebrow>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="mt-2 w-full rounded-[var(--r-sm)] border border-[var(--line)] bg-[var(--white)] px-3.5 py-2.5 text-[14px] text-[var(--text)] focus:border-[var(--ink)] focus:outline-none"
                />
              </label>
              <p className="mt-3 text-[12.5px] leading-relaxed text-[var(--text-2)]">
                Every shooting day gets a real date, weekends skipped. Leave it blank and
                the schedule starts the Monday after next, which is about the lead time a
                film permit needs.
              </p>
            </div>

            <div>
              <button
                type="button"
                disabled={!ready}
                onClick={() =>
                  onRun({ text, filename, setting, start_date: startDate || undefined })
                }
                className="pill pill-lime relative w-full justify-center overflow-hidden py-3.5 text-[13px]"
              >
                {running ? "Crew working" : "Break it down"}
                {running ? <span className="sweeping absolute inset-0" /> : null}
              </button>

              {notice ? (
                <p className="mt-3 text-[12.5px] leading-relaxed text-[#9a5f08]">{notice}</p>
              ) : null}
              {disabled && disabledReason ? (
                <p className="mt-3 text-[12.5px] leading-relaxed text-[var(--risk-red)]">
                  {disabledReason}
                </p>
              ) : null}
              {!notice && !disabled ? (
                <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-3)]">
                  Seven stages · roughly two minutes
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
