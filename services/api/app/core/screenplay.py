"""Deterministic screenplay pre-parsing.

Slugline detection and page-eighth measurement are mechanical problems with
exact answers, so they are solved in code rather than asked of a model. The
Script Supervisor agent then only has to do the part that genuinely needs
judgement: synopsis, character extraction, and disambiguating set names.

Doing it this way also caps token spend on long features and stops the model
from inventing scenes that are not in the script.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# A US-letter screenplay page holds roughly 55 typed lines, and the industry
# measures scene length in eighths of a page.
LINES_PER_PAGE = 55.0
LINES_PER_EIGHTH = LINES_PER_PAGE / 8.0

# Typeset column widths, in characters, for the two main element margins.
ACTION_WIDTH = 60
DIALOGUE_WIDTH = 35

SLUGLINE_RE = re.compile(
    r"^\s*(?P<int>INT\.?/EXT\.?|I/E\.?|EXT\.?/INT\.?|INT\.?|EXT\.?)\s*[\.\-\s]\s*(?P<rest>.+)$",
    re.IGNORECASE,
)

# Fountain lets a writer force a scene heading with a leading period.
FORCED_SLUG_RE = re.compile(r"^\.(?P<rest>[^\.].*)$")

TIME_TOKENS = (
    "CONTINUOUS",
    "MOMENTS LATER",
    "LATER",
    "MORNING",
    "AFTERNOON",
    "EVENING",
    "NIGHT",
    "DAY",
    "DAWN",
    "DUSK",
    "SUNRISE",
    "SUNSET",
    "MAGIC HOUR",
)

TIME_NORMALISE = {
    "MORNING": "DAY",
    "AFTERNOON": "DAY",
    "EVENING": "NIGHT",
    "SUNRISE": "DAWN",
    "SUNSET": "DUSK",
    "MAGIC HOUR": "DUSK",
    "MOMENTS LATER": "CONTINUOUS",
    "LATER": "CONTINUOUS",
}

BOILERPLATE_RE = re.compile(
    r"^\s*(FADE (IN|OUT)|CUT TO|SMASH CUT|DISSOLVE TO|MATCH CUT|THE END)[:\.]?\s*$",
    re.IGNORECASE,
)


@dataclass
class RawScene:
    """A mechanically extracted scene, before any model sees it."""

    number: str
    slugline: str
    interior: str
    location: str
    time_of_day: str
    page_start: float
    eighths: int
    text: str
    speakers: list[str] = field(default_factory=list)


def _normalise_interior(token: str) -> str:
    t = token.upper().replace(".", "").replace(" ", "")
    if t in ("INT/EXT", "EXT/INT", "I/E"):
        return "INT/EXT"
    return "EXT" if t.startswith("EXT") else "INT"


def _split_location_and_time(rest: str) -> tuple[str, str]:
    """Pull the trailing time-of-day off a scene heading.

    Sluglines separate the set from the time with a dash, but sub-locations use
    dashes too, so the last dash-delimited chunk is only treated as a time when
    it actually reads as one.
    """
    cleaned = rest.strip().rstrip(".")
    parts = [p.strip() for p in re.split(r"\s+[-–—]+\s+", cleaned) if p.strip()]

    if len(parts) > 1:
        tail = parts[-1].upper()
        for token in sorted(TIME_TOKENS, key=len, reverse=True):
            if tail == token or tail.startswith(token + " ") or tail.endswith(" " + token):
                location = " - ".join(parts[:-1])
                return location.upper(), TIME_NORMALISE.get(token, token)

    return cleaned.upper(), "DAY"


def _speakers_in(block: str) -> list[str]:
    """Character cues are uppercase lines that are followed by dialogue."""
    found: list[str] = []
    lines = block.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 40:
            continue
        # Strip parenthetical extensions such as (CONT'D) or (V.O.)
        candidate = re.sub(r"\s*\([^)]*\)\s*$", "", stripped).strip()
        if not candidate or not candidate.isupper():
            continue
        if not re.fullmatch(r"[A-Z0-9 .'\-#]+", candidate):
            continue
        if BOILERPLATE_RE.match(candidate) or SLUGLINE_RE.match(candidate):
            continue
        # Must be followed by a non-blank line for this to be a cue.
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if not nxt:
            continue
        if candidate not in found:
            found.append(candidate)
    return found


def _rendered_rows(block: str) -> int:
    """Rows this scene would occupy once typeset in screenplay format.

    Source lines are not page lines. An action paragraph written as one long
    line wraps to three rows inside the action margin, and a page is measured
    in rows, so measuring the source directly under-counts every scene. Blank
    lines are real vertical space and count as one row each.
    """
    rows = 0
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            rows += 1
            continue
        # Dialogue sits in a much narrower margin than action.
        width = DIALOGUE_WIDTH if line.startswith("  ") or len(stripped) < 45 else ACTION_WIDTH
        rows += max(1, math.ceil(len(stripped) / width))
    return rows


def _measure_eighths(block: str) -> int:
    """Scene length in page eighths, floored at one."""
    return max(1, round(_rendered_rows(block) / LINES_PER_EIGHTH))


def strip_front_matter(text: str) -> tuple[str, dict[str, str]]:
    """Remove a Fountain title page and return it as metadata."""
    meta: dict[str, str] = {}
    if "====" in text:
        head, _, body = text.partition("====")
        for line in head.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip().lower()] = v.strip()
        return body.lstrip("\n"), meta
    return text, meta


def parse_screenplay(text: str) -> tuple[list[RawScene], dict[str, str], float]:
    """Split a screenplay into scenes and measure it.

    Returns the scenes, any title-page metadata, and the total page count.
    """
    body, meta = strip_front_matter(text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = body.split("\n")

    starts: list[tuple[int, str, str, str]] = []  # index, slugline, interior, rest
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        forced = FORCED_SLUG_RE.match(stripped)
        probe = forced.group("rest").strip() if forced else stripped

        m = SLUGLINE_RE.match(probe)
        if m:
            starts.append((i, probe, _normalise_interior(m.group("int")), m.group("rest")))
        elif forced:
            # A forced heading with no INT/EXT still opens a scene.
            starts.append((i, probe, "INT", probe))

    scenes: list[RawScene] = []
    consumed_lines = 0

    for idx, (line_no, slug, interior, rest) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        block = "\n".join(lines[line_no:end]).strip()

        location, tod = _split_location_and_time(rest)
        page_start = round(consumed_lines / LINES_PER_PAGE, 1) + 1.0

        scenes.append(
            RawScene(
                number=str(idx + 1),
                slugline=slug.upper(),
                interior=interior,
                location=location,
                time_of_day=tod,
                page_start=page_start,
                eighths=_measure_eighths(block),
                text=block,
                speakers=_speakers_in(block),
            )
        )
        consumed_lines += _rendered_rows(block)

    _resolve_continuous(scenes)

    page_count = round(max(consumed_lines / LINES_PER_PAGE, 0.1), 1)
    return scenes, meta, page_count


def _resolve_continuous(scenes: list[RawScene]) -> None:
    """Give CONTINUOUS scenes the lighting state they actually inherit.

    A scene headed CONTINUOUS carries on from the scene before it, so it is
    lit and scheduled as whatever that scene was. Left unresolved it defaults
    to day, which puts a night exterior on the wrong strip colour and, worse,
    onto the wrong shooting day.
    """
    inherited = "DAY"
    for scene in scenes:
        if scene.time_of_day == "CONTINUOUS":
            scene.time_of_day = inherited
        else:
            inherited = scene.time_of_day


def detect_format(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".fountain") or lowered.endswith(".spmd"):
        return "fountain"
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".fdx"):
        return "fdx"
    return "plaintext"
