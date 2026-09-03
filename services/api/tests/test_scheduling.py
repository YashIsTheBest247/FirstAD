"""Tests for the deterministic stripboard optimiser.

The optimiser's whole job is to be cheaper than the alternative: every company
move costs shooting hours, and every broken night block costs turnaround. These
tests assert the properties a 1st AD would check on the board, not the exact
arrangement, because the arrangement is allowed to improve.
"""

from __future__ import annotations

from app.core.scheduling import (
    MAX_EIGHTHS_PER_DAY,
    derive_cast,
    optimise_stripboard,
)
from app.schemas.production import Interior, StripColor, TimeOfDay

from .conftest import make_breakdown, make_scene, make_script


def _board(scenes, heavy=None):
    script = make_script(scenes)
    return optimise_stripboard(script, make_breakdown(scenes, heavy))


# -- strip colours ----------------------------------------------------------


def test_strip_colour_convention() -> None:
    """The four colours every 1st AD reads the same way."""
    assert StripColor.for_scene(Interior.INT, TimeOfDay.DAY) is StripColor.WHITE
    assert StripColor.for_scene(Interior.EXT, TimeOfDay.DAY) is StripColor.YELLOW
    assert StripColor.for_scene(Interior.INT, TimeOfDay.NIGHT) is StripColor.BLUE
    assert StripColor.for_scene(Interior.EXT, TimeOfDay.NIGHT) is StripColor.GREEN


def test_dusk_is_lit_as_night() -> None:
    assert StripColor.for_scene(Interior.EXT, TimeOfDay.DUSK) is StripColor.GREEN
    assert StripColor.for_scene(Interior.INT, TimeOfDay.DUSK) is StripColor.BLUE


def test_int_ext_is_scheduled_as_an_exterior() -> None:
    """A car interior shot on a street is an exterior as far as the unit is concerned."""
    assert StripColor.for_scene(Interior.INT_EXT, TimeOfDay.DAY) is StripColor.YELLOW
    assert StripColor.for_scene(Interior.INT_EXT, TimeOfDay.NIGHT) is StripColor.GREEN


# -- grouping ---------------------------------------------------------------


def test_scenes_at_one_set_are_not_split_across_a_move() -> None:
    """Sub-locations of the same building must not cost a company move."""
    scenes = [
        make_scene("1", "ARCADIA THEATER - BOOTH", "INT", "NIGHT", 4),
        make_scene("2", "DUFFYS TAP", "INT", "NIGHT", 4),
        make_scene("3", "ARCADIA THEATER - LOBBY", "INT", "NIGHT", 4),
    ]
    days = _board(scenes)

    theatre_days = {d.day_number for d in days for s in d.scenes if s.scene_number in ("1", "3")}
    assert len(theatre_days) == 1, "both theatre scenes should share a day"


def test_company_moves_are_minimised() -> None:
    """Six scenes across two sets should cost at most one move."""
    scenes = [
        make_scene("1", "SET A", "INT", "DAY", 4),
        make_scene("2", "SET B", "INT", "DAY", 4),
        make_scene("3", "SET A", "INT", "DAY", 4),
        make_scene("4", "SET B", "INT", "DAY", 4),
        make_scene("5", "SET A", "INT", "DAY", 4),
        make_scene("6", "SET B", "INT", "DAY", 4),
    ]
    days = _board(scenes)

    assert sum(1 for d in days if d.company_move) <= 1


def test_first_day_is_never_a_company_move() -> None:
    scenes = [make_scene("1", "SET A"), make_scene("2", "SET B")]
    days = _board(scenes)

    assert days[0].company_move is False


def test_day_and_night_at_one_set_are_separated() -> None:
    """Relighting a set from day to night mid-day is not a thing you do."""
    scenes = [
        make_scene("1", "SET A", "INT", "DAY", 4),
        make_scene("2", "SET A", "INT", "NIGHT", 4),
    ]
    days = _board(scenes)

    for day in days:
        colours = {s.strip_color for s in day.scenes}
        assert not ({StripColor.WHITE, StripColor.YELLOW} & colours) or not (
            {StripColor.BLUE, StripColor.GREEN} & colours
        ), "a single day mixed day and night work"


def test_no_day_exceeds_the_hard_cap() -> None:
    scenes = [make_scene(str(i), "SET A", "INT", "DAY", 8) for i in range(1, 21)]
    days = _board(scenes)

    for day in days:
        assert day.total_eighths <= MAX_EIGHTHS_PER_DAY


def test_heavy_scenes_produce_lighter_days() -> None:
    """A stunt costs the day more than its page count suggests."""
    plain = [make_scene(str(i), "SET A", "INT", "DAY", 6) for i in range(1, 13)]
    stunts = {s.number for s in plain}

    light_board = _board(plain)
    heavy_board = _board(plain, heavy=stunts)

    assert len(heavy_board) > len(light_board)


# -- integrity --------------------------------------------------------------


def test_every_scene_is_scheduled_exactly_once() -> None:
    scenes = [
        make_scene("1", "SET A", "INT", "DAY", 6),
        make_scene("2", "SET B", "EXT", "NIGHT", 6),
        make_scene("3", "SET A", "INT", "NIGHT", 6),
        make_scene("4", "SET C", "EXT", "DAY", 6),
        make_scene("5", "SET B", "EXT", "NIGHT", 6),
    ]
    days = _board(scenes)

    scheduled = [s.scene_number for d in days for s in d.scenes]
    assert sorted(scheduled) == sorted(s.number for s in scenes)
    assert len(scheduled) == len(set(scheduled)), "a scene was scheduled twice"


def test_day_totals_match_their_scenes() -> None:
    scenes = [make_scene(str(i), "SET A", "INT", "DAY", 5) for i in range(1, 15)]
    days = _board(scenes)

    for day in days:
        assert day.total_eighths == sum(s.eighths for s in day.scenes)


def test_days_are_numbered_from_one_without_gaps() -> None:
    scenes = [make_scene(str(i), f"SET {i}", "INT", "DAY", 6) for i in range(1, 8)]
    days = _board(scenes)

    assert [d.day_number for d in days] == list(range(1, len(days) + 1))


def test_empty_script_produces_no_days() -> None:
    assert _board([]) == []


def test_single_scene_produces_one_day() -> None:
    days = _board([make_scene("1", "SET A")])

    assert len(days) == 1
    assert days[0].scenes[0].scene_number == "1"


# -- cast -------------------------------------------------------------------


def test_cast_is_ordered_by_workload() -> None:
    """Cast 1 is the busiest performer, which is the stripboard convention."""
    scenes = [
        make_scene("1", "SET A", characters=["MARISOL", "RAY"]),
        make_scene("2", "SET A", characters=["MARISOL"]),
        make_scene("3", "SET A", characters=["MARISOL", "TEDDY"]),
        make_scene("4", "SET A", characters=["RAY"]),
    ]
    order = derive_cast(make_script(scenes))

    assert order[0][0] == "MARISOL"
    assert len(order[0][1]) == 3
    assert [name for name, _ in order] == ["MARISOL", "RAY", "TEDDY"]


def test_cast_names_are_normalised_and_deduplicated() -> None:
    scenes = [
        make_scene("1", "SET A", characters=["marisol", "MARISOL"]),
        make_scene("2", "SET A", characters=[" Marisol "]),
    ]
    order = derive_cast(make_script(scenes))

    assert len(order) == 1
    assert order[0][0] == "MARISOL"


def test_cast_is_empty_when_no_characters_are_tagged() -> None:
    assert derive_cast(make_script([make_scene("1", "SET A")])) == []
