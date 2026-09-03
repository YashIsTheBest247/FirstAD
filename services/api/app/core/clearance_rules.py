"""Deterministic clearance rules.

Two jobs a model should not be doing, because both have exact answers:

  1. Recognising a fiction-reserved phone number. The 555-0100 to 555-0199
     block exists precisely so scripts can use it, and a number in that range
     is cleared by rule rather than by judgement. Screenplays spell numbers out
     in dialogue ("five five five, zero one four seven"), which a model reads
     past, so the digits are recovered here first.

  2. Deciding that two extracted references are the same thing. "MARISOL VEGA"
     and "Marisol" are one person, and "1847 North Kedzie Avenue" contains
     "North Kedzie Avenue". Left separate they inflate the report and, worse,
     spend the live-search budget twice on one entity, which pushes real
     references past the cap and gets them reported as unreviewed.
"""

from __future__ import annotations

import re

WORD_DIGITS: dict[str, str] = {
    "zero": "0", "oh": "0", "o": "0", "nought": "0",
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12",
}

# The North American Numbering Plan reserves 555-0100 through 555-0199 for
# fictional use. Nothing else in the 555 exchange is guaranteed unassigned.
FICTION_PHONE_RE = re.compile(r"555\s*-?\s*01\d{2}")

# Titles and honorifics that are not part of a person's identity.
NAME_NOISE = re.compile(
    r"^(mr|mrs|ms|miss|dr|det|detective|officer|sgt|sergeant|capt|captain|"
    r"alderman|councilman|councilwoman|mayor|judge|professor|prof|sir|madam)\.?\s+",
    re.IGNORECASE,
)


def spell_out_to_digits(text: str) -> str:
    """Turn spelled-out digits in dialogue into numerals.

    'Three one two, five five five, zero one four seven' becomes '3125550147'.
    Digits already present are kept, so mixed forms work too.
    """
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    out: list[str] = []
    for token in tokens:
        if not token:
            continue
        if token.isdigit():
            out.append(token)
        elif token in WORD_DIGITS:
            out.append(WORD_DIGITS[token])
    return "".join(out)


def is_fiction_phone(text: str) -> bool:
    """True when a reference is a phone number inside the reserved range."""
    digits = spell_out_to_digits(text)
    if FICTION_PHONE_RE.search(digits):
        return True
    # Also catch the written form directly, e.g. "(312) 555-0147".
    return bool(FICTION_PHONE_RE.search(re.sub(r"[^\d-]", "", text)))


def normalise_name(text: str) -> str:
    """Strip titles, punctuation and case so two spellings can be compared."""
    cleaned = NAME_NOISE.sub("", text.strip())
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _tokens(text: str) -> set[str]:
    return {t for t in normalise_name(text).split() if len(t) > 1}


def same_reference(a: str, b: str, category: str) -> bool:
    """Whether two extracted strings denote the same real-world thing.

    Deliberately conservative. A shared surname is enough to merge a person,
    because a script that says MARISOL VEGA once and Marisol thereafter is
    describing one character; but two unrelated businesses that happen to share
    a common word are not merged.
    """
    na, nb = normalise_name(a), normalise_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True

    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False

    if category == "person_name":
        # One name being a subset of the other means the shorter is the short
        # form: "Marisol" within "Marisol Vega", "Ray" within "Ray Okonkwo".
        return ta <= tb or tb <= ta

    if category in ("address", "business", "organisation"):
        # An address containing another is the same place with a number on it.
        # For businesses require full containment plus a multi-word overlap, so
        # "Duffy's Tap" and "Duffy's Diner" stay separate.
        smaller, larger = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
        return smaller <= larger and len(smaller) >= 2

    return False


def pick_canonical(a: str, b: str) -> str:
    """The fuller of two spellings, which is what a report should print."""
    return a if len(a) >= len(b) else b
