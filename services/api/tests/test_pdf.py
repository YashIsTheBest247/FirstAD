"""Tests for the PDF deliverables.

These two documents are distributed rather than edited, so what matters is that
the page carries the facts someone needs at 5am and that a partial package
never produces a crash instead of a document.
"""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader

from app.core.pdf import PDF_DOCUMENTS, call_sheets_pdf, clearance_pdf


def _text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _pages(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


@pytest.mark.parametrize("document", sorted(PDF_DOCUMENTS))
def test_every_pdf_is_a_valid_document(package: dict, document: str) -> None:
    data = PDF_DOCUMENTS[document](package)

    assert data[:5] == b"%PDF-"
    assert _pages(data) >= 1


@pytest.mark.parametrize("document", sorted(PDF_DOCUMENTS))
def test_every_pdf_survives_an_empty_package(document: str) -> None:
    """A failed or partial run must still produce a readable page."""
    data = PDF_DOCUMENTS[document]({})

    assert data[:5] == b"%PDF-"
    assert _pages(data) == 1


def test_call_sheet_carries_what_the_unit_needs(package: dict) -> None:
    text = _text(call_sheets_pdf(package))

    assert "THE PROJECTIONIST" in text
    assert "CALL SHEET" in text
    assert "DAY 1" in text
    assert "ARCADIA THEATER" in text
    # The crew call is the single most-read number on the sheet.
    assert "CREW CALL" in text
    assert "15:00" in text


def test_call_sheet_prints_the_shooting_date(package: dict) -> None:
    """A call sheet without a date is not a call sheet."""
    package = {**package}
    package["call_sheets"] = [
        {**package["call_sheets"][0], "shoot_date": "2026-09-14"}
    ]
    text = _text(call_sheets_pdf(package))

    assert "Mon 14 Sep 2026" in text


def test_one_page_per_shooting_day(package: dict) -> None:
    sheets = package["call_sheets"]
    two_days = {**package, "call_sheets": [sheets[0], {**sheets[0], "day_number": 2}]}

    assert _pages(call_sheets_pdf(two_days)) == 2


def test_call_sheet_shows_safety_notes(package: dict) -> None:
    text = _text(call_sheets_pdf(package))

    assert "SAFETY" in text.upper()
    assert "Traffic control" in text


def test_clearance_report_leads_with_the_risk_counts(package: dict) -> None:
    text = _text(clearance_pdf(package))

    assert "SCRIPT CLEARANCE REPORT" in text
    assert "RED" in text and "AMBER" in text and "GREEN" in text


def test_clearance_report_orders_red_first(package: dict) -> None:
    text = _text(clearance_pdf(package))
    red_at = text.find("Grant Holloway")
    green_at = text.find("555-0147")

    assert red_at != -1
    assert green_at != -1
    assert red_at < green_at, "red findings must come before green"


def test_clearance_report_prints_sources(package: dict) -> None:
    """A verdict nobody can check is worthless, so the URL travels with it."""
    text = _text(clearance_pdf(package))

    assert "https://example.org/roster" in text


def test_clearance_report_marks_unresearched_entries_honestly(package: dict) -> None:
    text = _text(clearance_pdf(package))

    assert "unreviewed rather than cleared" in text


def test_clearance_report_flags_negative_portrayal(package: dict) -> None:
    text = _text(clearance_pdf(package))

    assert "NEGATIVE PORTRAYAL" in text
