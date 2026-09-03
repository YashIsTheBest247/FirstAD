"""Tests for the deterministic clearance rules.

Both of these were written after a real pipeline run got them wrong. The
fiction-phone rule was in the risk-scorer prompt and the model read past it
because the script spells the number out in dialogue. The merge rule did not
exist, so one character arrived as two entities and spent the live-search
budget twice.
"""

from __future__ import annotations

import pytest

from app.core.clearance_rules import (
    is_fiction_phone,
    normalise_name,
    pick_canonical,
    same_reference,
    spell_out_to_digits,
)


# -- fiction phone numbers --------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "(312) 555-0147",
        "555-0100",
        "555-0199",
        "5550147",
        "312.555.0142",
        # The form that actually broke: dialogue spells it out.
        "Three one two, five five five, zero one four seven",
        "five five five oh one four seven",
    ],
)
def test_reserved_range_is_recognised(text: str) -> None:
    assert is_fiction_phone(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "555-1234",       # 555 exchange but outside the reserved block
        "312-555-9000",
        "555-0200",       # one past the top of the range
        "555-0099",       # one below the bottom
        "JRK-4482",       # a licence plate, not a phone number
        "",
    ],
)
def test_numbers_outside_the_range_are_not_cleared(text: str) -> None:
    assert is_fiction_phone(text) is False


def test_spell_out_conversion() -> None:
    assert spell_out_to_digits("five five five, zero one four seven") == "5550147"
    assert spell_out_to_digits("Three one two") == "312"
    # Mixed forms occur when a writer part-spells a number.
    assert spell_out_to_digits("312 five five five 0147") == "3125550147"
    assert spell_out_to_digits("no digits at all") == ""


# -- reference merging ------------------------------------------------------


def test_titles_are_stripped_when_comparing_names() -> None:
    assert normalise_name("DETECTIVE RAY OKONKWO") == "ray okonkwo"
    assert normalise_name("Mr. Sandoval") == "sandoval"
    assert normalise_name("Alderman Grant Holloway") == "grant holloway"


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("MARISOL VEGA", "Marisol"),
        ("DETECTIVE RAY OKONKWO", "Ray"),
        ("Alderman Grant Holloway", "GRANT HOLLOWAY"),
        ("Mr. Sandoval", "Sandoval"),
    ],
)
def test_short_forms_merge_into_the_full_name(a: str, b: str) -> None:
    assert same_reference(a, b, "person_name") is True
    assert same_reference(b, a, "person_name") is True


def test_unrelated_people_do_not_merge() -> None:
    assert same_reference("Marisol Vega", "Grant Holloway", "person_name") is False
    assert same_reference("Teddy", "Ray", "person_name") is False


def test_an_address_containing_another_is_the_same_place() -> None:
    assert same_reference("1847 North Kedzie Avenue", "NORTH KEDZIE AVENUE", "address") is True


def test_businesses_sharing_one_word_stay_separate() -> None:
    """A shared word is not identity, or every Duffy's in town becomes one bar."""
    assert same_reference("Duffy's Tap", "Duffy's Diner", "business") is False


def test_identical_strings_always_merge() -> None:
    assert same_reference("Zenith", "zenith", "brand_product") is True


def test_empty_strings_never_merge() -> None:
    assert same_reference("", "Marisol", "person_name") is False
    assert same_reference("Marisol", "", "person_name") is False


def test_canonical_form_keeps_the_fuller_spelling() -> None:
    """The report should print the full name, not the short form."""
    assert pick_canonical("Marisol", "MARISOL VEGA") == "MARISOL VEGA"
    assert pick_canonical("MARISOL VEGA", "Marisol") == "MARISOL VEGA"
