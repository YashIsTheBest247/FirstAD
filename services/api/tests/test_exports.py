"""Tests for the CSV exports.

An export is a contract with a spreadsheet, so what matters is that the header
row is stable, the rows line up with it, and nothing silently drops. Content is
checked only where it is a transformation rather than a copy.
"""

from __future__ import annotations

import csv
import io

import pytest

from app.core.exports import EXPORTS


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


@pytest.mark.parametrize("document", sorted(EXPORTS))
def test_every_export_produces_a_header_and_aligned_rows(package: dict, document: str) -> None:
    rows = _rows(EXPORTS[document](package))

    assert rows, f"{document} produced nothing"
    width = len(rows[0])
    assert width > 1

    for row in rows[1:]:
        # Blank spacer rows are allowed; anything else must match the header.
        if any(cell.strip() for cell in row):
            assert len(row) == width, f"{document} row is ragged: {row}"


@pytest.mark.parametrize("document", sorted(EXPORTS))
def test_every_export_survives_an_empty_package(document: str) -> None:
    """A partial or failed run must not crash the export."""
    rows = _rows(EXPORTS[document]({}))

    assert len(rows) >= 1


def test_stripboard_export_translates_strip_colours_to_labels() -> None:
    """A colour name is meaningless in a spreadsheet; the lighting state is not."""
    package = {
        "stripboard": {
            "days": [
                {
                    "day_number": 1,
                    "location": "SET A",
                    "company_move": False,
                    "scenes": [
                        {
                            "scene_number": "1",
                            "slugline": "INT. A - NIGHT",
                            "strip_color": "blue",
                            "eighths": 3,
                            "cast_ids": ["1", "2"],
                            "synopsis": "x",
                        }
                    ],
                }
            ]
        }
    }
    rows = _rows(EXPORTS["stripboard"](package))

    assert rows[1][5] == "INT NIGHT"
    assert rows[1][7] == "1 2"


def test_stripboard_export_marks_company_moves(package: dict) -> None:
    rows = _rows(EXPORTS["stripboard"](package))
    move_column = rows[0].index("Company move")

    assert any(row[move_column] == "yes" for row in rows[1:])


def test_stripboard_export_has_one_row_per_scene(package: dict) -> None:
    rows = _rows(EXPORTS["stripboard"](package))
    scene_count = sum(len(d["scenes"]) for d in package["stripboard"]["days"])

    assert len(rows) - 1 == scene_count


def test_day_out_of_days_marks_work_and_hold(package: dict) -> None:
    """W is a work day, H is a hold day, and a hold day is paid."""
    rows = _rows(EXPORTS["day-out-of-days"](package))

    assert rows[0][:2] == ["Cast", "Character"]
    marisol = next(r for r in rows[1:] if r[1] == "MARISOL")
    assert "W" in marisol


def test_day_out_of_days_counts_holds_between_first_and_last_call() -> None:
    """A gap between a performer's first and last day is a hold, not a day off."""
    package = {
        "stripboard": {
            "days": [{"day_number": d, "scenes": []} for d in (1, 2, 3)],
            "cast": [{"id": "1", "character": "X", "work_days": [1, 3]}],
        }
    }
    rows = _rows(EXPORTS["day-out-of-days"](package))

    row = rows[1]
    assert row[2:5] == ["W", "H", "W"]
    assert row[-1] == "1", "the middle day should be counted as a hold"


def test_clearance_export_orders_red_before_green(package: dict) -> None:
    rows = _rows(EXPORTS["clearance"](package))

    risks = [row[0] for row in rows[1:]]
    assert risks == sorted(risks, key=lambda r: {"RED": 0, "AMBER": 1, "GREEN": 2}[r])
    assert risks[0] == "RED"


def test_clearance_export_carries_sources_and_researched_flag(package: dict) -> None:
    rows = _rows(EXPORTS["clearance"](package))
    header = rows[0]
    researched = header.index("Researched")
    sources = header.index("Sources")

    red = next(r for r in rows[1:] if r[0] == "RED")
    green = next(r for r in rows[1:] if r[0] == "GREEN")

    assert red[researched] == "yes"
    assert "https://" in red[sources]
    # The 555 number is cleared by rule, so it is honestly marked unresearched.
    assert green[researched] == "no"


def test_clearance_export_resolves_the_entity_text(package: dict) -> None:
    """Rows must show the reference, not the internal entity id."""
    rows = _rows(EXPORTS["clearance"](package))

    assert any("Grant Holloway" in row[1] for row in rows[1:])
    assert not any(row[1].startswith("person-") for row in rows[1:])


def test_budget_export_totals_match_the_lines(package: dict) -> None:
    rows = _rows(EXPORTS["budget"](package))

    # The group column is only filled on real budget lines, so it separates
    # them from the subtotal block and the blank spacer row.
    data_rows = [row for row in rows[1:] if len(row) > 4 and row[0]]
    summary_rows = [row for row in rows[1:] if len(row) > 4 and not row[0] and row[3]]

    line_total = sum(float(row[4]) for row in data_rows)
    labelled = {row[3]: float(row[4]) for row in summary_rows}

    assert labelled["Subtotal"] == pytest.approx(line_total)
    assert labelled["Total"] == pytest.approx(line_total * 1.10)


def test_budget_export_includes_the_cost_driver(package: dict) -> None:
    """A line nobody can defend is padding, so the driver travels with it."""
    rows = _rows(EXPORTS["budget"](package))
    driver = rows[0].index("Cost driver")

    assert any(row[driver].strip() for row in rows[1:] if row[0])


def test_call_sheets_export_separates_entry_types(package: dict) -> None:
    rows = _rows(EXPORTS["call-sheets"](package))
    kinds = {row[3] for row in rows[1:]}

    assert {"Cast", "Department", "Safety", "Weather"} <= kinds


def test_breakdown_export_joins_sluglines_from_the_script(package: dict) -> None:
    """The breakdown only holds scene numbers, so the slugline is looked up."""
    rows = _rows(EXPORTS["breakdown"](package))

    assert rows[0][1] == "Slugline"
    assert any("INT." in row[1] or "EXT." in row[1] for row in rows[1:])


def test_breakdown_export_flags_elements_needing_a_department(package: dict) -> None:
    rows = _rows(EXPORTS["breakdown"](package))
    flag = rows[0].index("Needs department")

    assert flag == len(rows[0]) - 1
    assert all(row[flag] in ("", "yes") for row in rows[1:])
