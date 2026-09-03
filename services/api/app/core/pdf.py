"""PDF deliverables.

CSV is right for the breakdown and the budget, because those live in a
spreadsheet and get re-sorted. Two documents are different: a call sheet goes
out to sixty people the night before a shooting day, and a clearance report
goes to an insurer. Those are distributed, read once, and never edited, which
makes them PDFs everywhere in the industry.

Laid out with ReportLab's low-level canvas rather than the document templates,
because both of these are forms with fixed regions, not flowing prose. A call
sheet in particular is read at 5am in the dark, so the hierarchy has to be
blunt: the date and the crew call are the largest things on the page.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

INK = colors.HexColor("#101211")
MUTED = colors.HexColor("#5a635e")
RULE = colors.HexColor("#c9cabf")
LIME = colors.HexColor("#a9d629")

RISK_COLOURS = {
    "red": colors.HexColor("#c02828"),
    "amber": colors.HexColor("#c07a10"),
    "green": colors.HexColor("#2c8a4e"),
}

STRIP_LABELS = {
    "white": "INT DAY",
    "yellow": "EXT DAY",
    "blue": "INT NIGHT",
    "green": "EXT NIGHT",
}


class _Page:
    """A canvas with a cursor, so callers do not track y coordinates by hand."""

    def __init__(self, title: str, subject: str) -> None:
        self.buffer = io.BytesIO()
        self.c = pdfcanvas.Canvas(self.buffer, pagesize=A4)
        self.c.setTitle(title)
        self.c.setSubject(subject)
        self.c.setAuthor("First AD")
        self.y = PAGE_H - MARGIN

    # -- primitives ------------------------------------------------------

    def space(self, amount: float) -> None:
        self.y -= amount

    def need(self, amount: float) -> None:
        """Start a new page when the next block will not fit."""
        if self.y - amount < MARGIN:
            self.c.showPage()
            self.y = PAGE_H - MARGIN

    def rule(self, colour: colors.Color = RULE, width: float = 0.6) -> None:
        self.need(6)
        self.c.setStrokeColor(colour)
        self.c.setLineWidth(width)
        self.c.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= 6

    def text(
        self,
        value: str,
        *,
        size: float = 9,
        bold: bool = False,
        colour: colors.Color = INK,
        x: float | None = None,
        leading: float | None = None,
    ) -> None:
        self.need(size + 4)
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.setFillColor(colour)
        self.c.drawString(x if x is not None else MARGIN, self.y, value)
        self.y -= leading if leading is not None else size + 3

    def right(self, value: str, *, size: float = 9, bold: bool = False, colour: colors.Color = INK) -> None:
        """Draw on the current line, right-aligned, without advancing."""
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.setFillColor(colour)
        self.c.drawRightString(PAGE_W - MARGIN, self.y + (size + 3), value)

    def wrapped(
        self,
        value: str,
        *,
        size: float = 9,
        colour: colors.Color = INK,
        indent: float = 0,
        width: float | None = None,
    ) -> None:
        """Naive greedy wrap. Adequate for the short prose these forms carry."""
        if not value:
            return
        limit = (width or (CONTENT_W - indent))
        self.c.setFont("Helvetica", size)
        words, line = value.split(), ""

        for word in words:
            probe = f"{line} {word}".strip()
            if self.c.stringWidth(probe, "Helvetica", size) <= limit:
                line = probe
                continue
            self.text(line, size=size, colour=colour, x=MARGIN + indent)
            self.c.setFont("Helvetica", size)
            line = word
        if line:
            self.text(line, size=size, colour=colour, x=MARGIN + indent)

    def label(self, value: str) -> None:
        self.text(value.upper(), size=7, bold=True, colour=MUTED, leading=11)

    def finish(self) -> bytes:
        self.c.showPage()
        self.c.save()
        return self.buffer.getvalue()


def _fmt_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, date):
        return value.strftime("%a %d %b %Y")
    try:
        return date.fromisoformat(str(value)).strftime("%a %d %b %Y")
    except ValueError:
        return str(value)


# --------------------------------------------------------------------------
# Call sheets
# --------------------------------------------------------------------------


def call_sheets_pdf(package: dict[str, Any]) -> bytes:
    """One page per shooting day, in the order they shoot."""
    header = (package.get("script") or {}).get("header") or {}
    title = str(header.get("title") or "Untitled")
    sheets = package.get("call_sheets") or []

    page = _Page(f"{title} - call sheets", "Call sheets")

    if not sheets:
        page.text("No call sheets were produced for this run.", size=10, colour=MUTED)
        return page.finish()

    for index, sheet in enumerate(sheets):
        if index > 0:
            page.c.showPage()
            page.y = PAGE_H - MARGIN

        # Masthead. The date and the crew call are the two things someone
        # checks at 5am, so they are the largest type on the page.
        page.text(title.upper(), size=16, bold=True)
        page.text("CALL SHEET", size=9, bold=True, colour=MUTED)
        page.space(4)
        page.rule(INK, 1.2)
        page.space(4)

        day_line = f"DAY {sheet.get('day_number')}"
        page.text(day_line, size=22, bold=True)
        page.right(_fmt_date(sheet.get("shoot_date")), size=12, bold=True)
        page.space(2)

        page.text(str(sheet.get("location") or ""), size=11, colour=MUTED)
        page.right(f"CREW CALL  {sheet.get('general_call') or ''}", size=13, bold=True)
        page.space(8)
        page.rule()

        # Scenes.
        page.label("Scenes")
        for scene in sheet.get("scenes") or []:
            page.need(14)
            y = page.y
            page.c.setFont("Helvetica-Bold", 9)
            page.c.setFillColor(INK)
            page.c.drawString(MARGIN, y, str(scene.get("scene_number") or ""))
            page.c.setFont("Helvetica", 9)
            page.c.drawString(MARGIN + 16 * mm, y, str(scene.get("slugline") or "")[:62])
            page.c.setFont("Helvetica", 8)
            page.c.setFillColor(MUTED)
            page.c.drawString(
                MARGIN + 118 * mm, y, STRIP_LABELS.get(str(scene.get("strip_color")), "")
            )
            page.c.drawRightString(PAGE_W - MARGIN, y, f"{scene.get('eighths')}/8")
            page.y -= 13
        page.space(4)
        page.rule()

        # Calls.
        for heading, key in (("Cast calls", "cast_calls"), ("Department calls", "department_calls")):
            rows = sheet.get(key) or []
            if not rows:
                continue
            page.label(heading)
            for row in rows:
                page.need(13)
                y = page.y
                page.c.setFont("Helvetica-Bold", 9)
                page.c.setFillColor(INK)
                page.c.drawString(MARGIN, y, str(row.get("time") or ""))
                page.c.setFont("Helvetica", 9)
                page.c.drawString(MARGIN + 22 * mm, y, str(row.get("who") or ""))
                if row.get("note"):
                    page.c.setFont("Helvetica-Oblique", 8)
                    page.c.setFillColor(MUTED)
                    page.c.drawString(MARGIN + 78 * mm, y, str(row["note"])[:58])
                page.y -= 13
            page.space(3)

        # Safety. Boxed, because it is the part that must not be skimmed.
        notes = sheet.get("safety_notes") or []
        if notes:
            page.space(2)
            top = page.y + 6
            page.label("Safety")
            for note in notes:
                page.wrapped(f"- {note}", size=9, indent=2 * mm)
            bottom = page.y - 2
            page.c.setStrokeColor(RISK_COLOURS["red"])
            page.c.setLineWidth(0.9)
            page.c.rect(MARGIN - 3 * mm, bottom, CONTENT_W + 6 * mm, top - bottom, stroke=1, fill=0)
            page.space(6)

        if sheet.get("weather_note"):
            page.label("Weather")
            page.wrapped(str(sheet["weather_note"]), size=9, colour=MUTED)

        page.space(4)
        page.rule()
        page.text(
            "Nearest hospital: ________________________________________",
            size=8,
            colour=MUTED,
        )

    return page.finish()


# --------------------------------------------------------------------------
# Clearance report
# --------------------------------------------------------------------------


def clearance_pdf(package: dict[str, Any]) -> bytes:
    """The document that goes to the insurer, with its sources attached."""
    header = (package.get("script") or {}).get("header") or {}
    title = str(header.get("title") or "Untitled")
    report = package.get("clearance") or {}
    entities = {e.get("id"): e for e in report.get("entities") or []}
    findings = report.get("findings") or []

    order = {"red": 0, "amber": 1, "green": 2}
    findings = sorted(findings, key=lambda f: order.get(str(f.get("risk")), 9))
    counts = {level: sum(1 for f in findings if f.get("risk") == level) for level in order}

    page = _Page(f"{title} - clearance report", "Script clearance report")

    page.text(title.upper(), size=16, bold=True)
    page.text("SCRIPT CLEARANCE REPORT", size=9, bold=True, colour=MUTED)
    page.space(4)
    page.rule(INK, 1.2)
    page.space(4)

    for level in ("red", "amber", "green"):
        page.c.setFont("Helvetica-Bold", 11)
        page.c.setFillColor(RISK_COLOURS[level])
        page.c.drawString(
            MARGIN + ("red amber green".split().index(level) * 38 * mm),
            page.y,
            f"{counts[level]}  {level.upper()}",
        )
    page.y -= 16
    page.rule()

    page.wrapped(
        "Every reference below was checked against the live web at the time of the run. "
        "Risk is the product of two things: whether the reference collides with something "
        "real and identifiable, and whether the script depicts it damagingly. Sources are "
        "listed so each verdict can be checked.",
        size=8.5,
        colour=MUTED,
    )
    page.space(6)

    if not findings:
        page.text("No clearable references were found.", size=10, colour=MUTED)
        return page.finish()

    for finding in findings:
        entity = entities.get(finding.get("entity_id")) or {}
        risk = str(finding.get("risk") or "green")
        colour = RISK_COLOURS.get(risk, MUTED)

        page.need(52)
        page.space(4)

        # Risk bar plus the reference itself.
        y = page.y
        page.c.setFillColor(colour)
        page.c.rect(MARGIN, y - 2, 2.4 * mm, 11, stroke=0, fill=1)

        page.c.setFont("Helvetica-Bold", 11)
        page.c.setFillColor(INK)
        page.c.drawString(MARGIN + 5 * mm, y, str(entity.get("text") or finding.get("entity_id")))

        page.c.setFont("Helvetica-Bold", 8)
        page.c.setFillColor(colour)
        page.c.drawRightString(PAGE_W - MARGIN, y, risk.upper())
        page.y -= 14

        meta = str(entity.get("category") or "").replace("_", " ")
        scenes = ", ".join(entity.get("scene_numbers") or [])
        if scenes:
            meta += f"   scenes {scenes}"
        if entity.get("is_negative_portrayal"):
            meta += "   NEGATIVE PORTRAYAL"
        page.text(meta, size=7.5, colour=MUTED, x=MARGIN + 5 * mm)

        page.wrapped(
            str(finding.get("rationale") or ""), size=9, indent=5 * mm
        )

        matches = finding.get("real_world_matches") or []
        if matches:
            page.text("Collides with:", size=7.5, bold=True, colour=MUTED, x=MARGIN + 5 * mm)
            for match in matches:
                page.wrapped(f"- {match}", size=8.5, indent=8 * mm)

        alternatives = finding.get("suggested_alternatives") or []
        if alternatives:
            page.text(
                "Pre-verified replacements: " + ", ".join(alternatives),
                size=8.5,
                colour=colors.HexColor("#4a6206"),
                x=MARGIN + 5 * mm,
            )

        citations = finding.get("citations") or []
        if citations:
            page.text("Sources:", size=7.5, bold=True, colour=MUTED, x=MARGIN + 5 * mm)
            for citation in citations:
                page.wrapped(f"- {citation.get('url', '')}", size=7.5, colour=MUTED, indent=8 * mm)
        elif finding.get("searched") is False:
            page.text(
                "Not researched in this run; reported unreviewed rather than cleared.",
                size=7.5,
                colour=MUTED,
                x=MARGIN + 5 * mm,
            )

        page.space(2)
        page.rule()

    return page.finish()


PDF_DOCUMENTS = {
    "call-sheets": call_sheets_pdf,
    "clearance": clearance_pdf,
}
