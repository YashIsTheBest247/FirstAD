"""Deterministic stripboard optimisation.

Grouping scenes into shooting days is a packing problem with hard constraints,
so it is solved in code and handed to the Scheduler agent as a candidate. The
agent then applies the judgement an optimiser cannot encode: which actor not to
strand, which day is too heavy because of what is in it rather than how long it
is, which permit will not come through in time.

The objective, in the order a 1st AD weighs them:
  1. Minimise company moves. Moving the unit costs hours of shooting.
  2. Keep night work contiguous, so turnaround is not broken every other day.
  3. Fill days close to a realistic load without going over.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.schemas.production import (
    Breakdown,
    ParsedScript,
    Scene,
    ScheduledScene,
    ShootDay,
    StripColor,
    TimeOfDay,
)

# A standard drama shoots roughly five pages a day. Forty eighths is five pages.
TARGET_EIGHTHS_PER_DAY = 40
MAX_EIGHTHS_PER_DAY = 52

# Elements that make a day heavier than its page count suggests.
HEAVY_CATEGORIES = {"stunts", "special_effects", "animals", "vehicles", "visual_effects"}
HEAVY_EIGHTHS_PENALTY = 8


def _is_night(scene: Scene) -> bool:
    return scene.time_of_day in (TimeOfDay.NIGHT, TimeOfDay.DUSK)


def _base_location(location: str) -> str:
    """Collapse sub-locations onto the parent set.

    'ARCADIA THEATER - PROJECTION BOOTH' and 'ARCADIA THEATER - LOBBY' are one
    place as far as the trucks are concerned, so they should not cost a move.
    """
    return location.split(" - ")[0].strip() or location


@dataclass
class _Unit:
    """A block of scenes that must be shot together: one set, one lighting state."""

    base_location: str
    night: bool
    scenes: list[Scene]

    @property
    def eighths(self) -> int:
        return sum(s.eighths for s in self.scenes)


def _heaviness(scene_numbers: set[str], breakdown: Breakdown) -> int:
    """Extra notional eighths to charge a day for its difficult elements."""
    penalty = 0
    for sb in breakdown.scenes:
        if sb.scene_number not in scene_numbers:
            continue
        cats = {e.category.value for e in sb.elements}
        if cats & HEAVY_CATEGORIES:
            penalty += HEAVY_EIGHTHS_PENALTY
        if any(e.flags_department for e in sb.elements):
            penalty += 4
    return penalty


def optimise_stripboard(script: ParsedScript, breakdown: Breakdown) -> list[ShootDay]:
    """Produce a candidate shooting schedule."""
    # 1. Bucket scenes into units of one set and one lighting state.
    buckets: dict[tuple[str, bool], list[Scene]] = defaultdict(list)
    for scene in script.scenes:
        buckets[(_base_location(scene.location), _is_night(scene))].append(scene)

    units = [
        _Unit(base_location=loc, night=night, scenes=sorted(scenes, key=lambda s: float(s.page_start)))
        for (loc, night), scenes in buckets.items()
    ]

    # 2. Order units so every unit at the same set is consecutive, which is what
    #    actually removes company moves. Within a set, shoot days before nights.
    by_location: dict[str, list[_Unit]] = defaultdict(list)
    for unit in units:
        by_location[unit.base_location].append(unit)

    # Biggest sets first: the unit spends its longest stretch where there is most
    # to shoot, and the small one-off sets become the moves.
    ordered_locations = sorted(
        by_location, key=lambda loc: sum(u.eighths for u in by_location[loc]), reverse=True
    )

    ordered_units: list[_Unit] = []
    for loc in ordered_locations:
        ordered_units.extend(sorted(by_location[loc], key=lambda u: u.night))

    # 3. Pack units into days, never splitting a unit across a location change.
    days: list[ShootDay] = []
    current: list[Scene] = []
    current_location: str | None = None
    current_night: bool | None = None

    def flush() -> None:
        nonlocal current, current_location, current_night
        if not current or current_location is None:
            return
        day_number = len(days) + 1
        scheduled = [
            ScheduledScene(
                scene_number=s.number,
                slugline=s.slugline,
                strip_color=StripColor.for_scene(s.interior, s.time_of_day),
                eighths=s.eighths,
                location=s.location,
                synopsis=s.synopsis,
            )
            for s in current
        ]
        previous_location = days[-1].location if days else None
        days.append(
            ShootDay(
                day_number=day_number,
                location=current_location,
                scenes=scheduled,
                total_eighths=sum(s.eighths for s in current),
                company_move=previous_location is not None and previous_location != current_location,
            )
        )
        current = []
        current_location = None
        current_night = None

    for unit in ordered_units:
        for scene in unit.scenes:
            loaded = sum(s.eighths for s in current)
            penalty = _heaviness({s.number for s in current}, breakdown)

            location_changed = current_location is not None and current_location != unit.base_location
            lighting_changed = current_night is not None and current_night != unit.night
            would_overflow = loaded + penalty + scene.eighths > MAX_EIGHTHS_PER_DAY
            at_target = loaded + penalty >= TARGET_EIGHTHS_PER_DAY

            if current and (location_changed or lighting_changed or would_overflow or at_target):
                flush()

            current.append(scene)
            current_location = unit.base_location
            current_night = unit.night

    flush()
    return days


def derive_cast(script: ParsedScript) -> list[tuple[str, list[str]]]:
    """Cast numbers, ordered by how much each character works.

    Returns (character, scene_numbers) ordered so the first entry becomes cast 1,
    which is the convention on every stripboard.
    """
    appearances: dict[str, list[str]] = defaultdict(list)
    for scene in script.scenes:
        for character in scene.characters:
            appearances[character.strip().upper()].append(scene.number)

    return sorted(appearances.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def next_working_day(day: date) -> date:
    """The next date that is not a weekend."""
    nxt = day + timedelta(days=1)
    while nxt.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        nxt += timedelta(days=1)
    return nxt


def assign_shoot_dates(days: list[ShootDay], start: date) -> None:
    """Put a real date on every shooting day.

    A schedule without dates cannot book anything. "Day 4" does not tell a
    location manager whether the permit will have cleared, and a call sheet
    without a date is not a call sheet.

    Six-day weeks happen, but the default working week is five days, so
    weekends are skipped. If the start date itself lands on a weekend it is
    moved forward rather than silently shooting on a Saturday.
    """
    if not days:
        return

    current = start
    while current.weekday() >= 5:
        current += timedelta(days=1)

    for index, day in enumerate(days):
        if index > 0:
            current = next_working_day(current)
        day.shoot_date = current


def default_start_date(today: date | None = None) -> date:
    """A sensible default start: the Monday after next.

    Not tomorrow, because nothing shoots tomorrow, and the location research
    routinely reports permit lead times of one to two weeks.
    """
    today = today or date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_until_monday + 7)
