"""CSV exports.

A production package that cannot leave the browser is not a deliverable. The
four documents people actually pass around are the stripboard, the clearance
report, the budget top sheet, and the call sheets, and in a production office
they move as spreadsheets, so that is what this emits.

Column names follow what scheduling software and clearance firms already use,
so a row can be pasted into an existing sheet without re-labelling.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Callable

STRIP_LABELS = {
    "white": "INT DAY",
    "yellow": "EXT DAY",
    "blue": "INT NIGHT",
    "green": "EXT NIGHT",
}


def _writer() -> tuple[io.StringIO, "csv._writer"]:
    buffer = io.StringIO()
    # Excel on Windows needs CRLF to keep rows intact.
    return buffer, csv.writer(buffer, lineterminator="\r\n")


def stripboard_csv(package: dict[str, Any]) -> str:
    board = package.get("stripboard") or {}
    buffer, out = _writer()

    out.writerow(
        [
            "Day",
            "Location",
            "Company move",
            "Scene",
            "Slugline",
            "Strip",
            "Eighths",
            "Cast",
            "Synopsis",
        ]
    )

    for day in board.get("days") or []:
        for scene in day.get("scenes") or []:
            out.writerow(
                [
                    day.get("day_number"),
                    day.get("location"),
                    "yes" if day.get("company_move") else "",
                    scene.get("scene_number"),
                    scene.get("slugline"),
                    STRIP_LABELS.get(str(scene.get("strip_color")), scene.get("strip_color")),
                    scene.get("eighths"),
                    " ".join(scene.get("cast_ids") or []),
                    scene.get("synopsis"),
                ]
            )

    return buffer.getvalue()


def day_out_of_days_csv(package: dict[str, Any]) -> str:
    board = package.get("stripboard") or {}
    days = [d.get("day_number") for d in board.get("days") or []]
    buffer, out = _writer()

    out.writerow(["Cast", "Character", *[f"Day {d}" for d in days], "Work days", "Hold days"])

    for member in board.get("cast") or []:
        work = set(member.get("work_days") or [])
        cells: list[str] = []
        holds = 0
        first = min(work) if work else None
        last = max(work) if work else None

        for day in days:
            if day in work:
                cells.append("W")
            elif first is not None and last is not None and first < day < last:
                cells.append("H")
                holds += 1
            else:
                cells.append("")

        out.writerow([member.get("id"), member.get("character"), *cells, len(work), holds])

    return buffer.getvalue()


def clearance_csv(package: dict[str, Any]) -> str:
    report = package.get("clearance") or {}
    entities = {e.get("id"): e for e in report.get("entities") or []}
    buffer, out = _writer()

    out.writerow(
        [
            "Risk",
            "Reference",
            "Category",
            "Scenes",
            "Pages",
            "Portrayal",
            "Negative portrayal",
            "Rationale",
            "Real world matches",
            "Suggested alternatives",
            "Researched",
            "Sources",
        ]
    )

    rank = {"red": 0, "amber": 1, "green": 2}
    findings = sorted(
        report.get("findings") or [], key=lambda f: rank.get(str(f.get("risk")), 9)
    )

    for finding in findings:
        entity = entities.get(finding.get("entity_id")) or {}
        out.writerow(
            [
                str(finding.get("risk", "")).upper(),
                entity.get("text", finding.get("entity_id")),
                str(entity.get("category") or "").replace("_", " "),
                " ".join(entity.get("scene_numbers") or []),
                " ".join(str(p) for p in entity.get("page_refs") or []),
                entity.get("portrayal"),
                "yes" if entity.get("is_negative_portrayal") else "",
                finding.get("rationale"),
                "; ".join(finding.get("real_world_matches") or []),
                "; ".join(finding.get("suggested_alternatives") or []),
                "no" if finding.get("searched") is False else "yes",
                " ".join(c.get("url", "") for c in finding.get("citations") or []),
            ]
        )

    return buffer.getvalue()


def budget_csv(package: dict[str, Any]) -> str:
    budget = package.get("budget") or {}
    buffer, out = _writer()

    out.writerow(["Group", "Account", "Category", "Detail", "Amount USD", "Cost driver"])

    groups = (
        ("Above the line", budget.get("above_the_line") or []),
        ("Below the line", budget.get("below_the_line") or []),
        ("Post and other", budget.get("post_and_other") or []),
    )

    subtotal = 0.0
    for label, lines in groups:
        for line in lines:
            amount = float(line.get("amount_usd") or 0)
            subtotal += amount
            out.writerow(
                [
                    label,
                    line.get("account"),
                    line.get("category"),
                    line.get("detail"),
                    round(amount, 2),
                    line.get("driver"),
                ]
            )

    contingency_pct = float(budget.get("contingency_pct") or 0)
    contingency = subtotal * contingency_pct / 100

    out.writerow([])
    out.writerow(["", "", "", "Subtotal", round(subtotal, 2), ""])
    out.writerow(["", "", "", f"Contingency {contingency_pct}%", round(contingency, 2), ""])
    out.writerow(["", "", "", "Total", round(subtotal + contingency, 2), ""])

    return buffer.getvalue()


def call_sheets_csv(package: dict[str, Any]) -> str:
    buffer, out = _writer()

    out.writerow(
        ["Day", "Location", "General call", "Entry type", "Who", "Time", "Note"]
    )

    for sheet in package.get("call_sheets") or []:
        base = [sheet.get("day_number"), sheet.get("location"), sheet.get("general_call")]

        for call in sheet.get("cast_calls") or []:
            out.writerow([*base, "Cast", call.get("who"), call.get("time"), call.get("note") or ""])

        for call in sheet.get("department_calls") or []:
            out.writerow(
                [*base, "Department", call.get("who"), call.get("time"), call.get("note") or ""]
            )

        for note in sheet.get("safety_notes") or []:
            out.writerow([*base, "Safety", "", "", note])

        if sheet.get("weather_note"):
            out.writerow([*base, "Weather", "", "", sheet.get("weather_note")])

    return buffer.getvalue()


def breakdown_csv(package: dict[str, Any]) -> str:
    breakdown = package.get("breakdown") or {}
    scenes = {s.get("number"): s for s in (package.get("script") or {}).get("scenes") or []}
    buffer, out = _writer()

    out.writerow(
        ["Scene", "Slugline", "Setup hours", "Category", "Element", "Note", "Needs department"]
    )

    for scene in breakdown.get("scenes") or []:
        number = scene.get("scene_number")
        slugline = (scenes.get(number) or {}).get("slugline", "")
        for element in scene.get("elements") or []:
            out.writerow(
                [
                    number,
                    slugline,
                    scene.get("estimated_setup_hours"),
                    str(element.get("category") or "").replace("_", " "),
                    element.get("name"),
                    element.get("note") or "",
                    "yes" if element.get("flags_department") else "",
                ]
            )

    return buffer.getvalue()


EXPORTS: dict[str, Callable[[dict[str, Any]], str]] = {
    "stripboard": stripboard_csv,
    "day-out-of-days": day_out_of_days_csv,
    "clearance": clearance_csv,
    "budget": budget_csv,
    "call-sheets": call_sheets_csv,
    "breakdown": breakdown_csv,
}
