"""Tests for the deterministic screenplay parser.

These are the parts of the pipeline with exactly one right answer, so they are
the parts worth pinning down. A regression here silently corrupts everything
downstream: a mis-measured scene lands on the wrong shooting day, and a
mis-read time of day puts a night exterior on a day strip.
"""

from __future__ import annotations

from app.core.screenplay import (
    LINES_PER_PAGE,
    _rendered_rows,
    detect_format,
    parse_screenplay,
    strip_front_matter,
)


def test_parses_basic_sluglines() -> None:
    scenes, _, _ = parse_screenplay(
        "INT. KITCHEN - DAY\n\nShe pours coffee.\n\nEXT. DRIVEWAY - NIGHT\n\nThe car is gone.\n"
    )

    assert [s.number for s in scenes] == ["1", "2"]
    assert scenes[0].interior == "INT"
    assert scenes[0].location == "KITCHEN"
    assert scenes[0].time_of_day == "DAY"
    assert scenes[1].interior == "EXT"
    assert scenes[1].location == "DRIVEWAY"
    assert scenes[1].time_of_day == "NIGHT"


def test_sub_location_is_not_mistaken_for_a_time() -> None:
    """A dash before a room name must not be read as a time of day."""
    scenes, _, _ = parse_screenplay(
        "INT. ARCADIA THEATER - PROJECTION BOOTH - NIGHT\n\nHot as an engine block.\n"
    )

    assert scenes[0].location == "ARCADIA THEATER - PROJECTION BOOTH"
    assert scenes[0].time_of_day == "NIGHT"


def test_location_without_a_time_defaults_to_day() -> None:
    scenes, _, _ = parse_screenplay("INT. WAREHOUSE\n\nDust in the light.\n")

    assert scenes[0].location == "WAREHOUSE"
    assert scenes[0].time_of_day == "DAY"


def test_continuous_inherits_the_previous_lighting_state() -> None:
    """CONTINUOUS carries on from the scene before it.

    Left unresolved it defaults to DAY, which would put a night exterior on a
    yellow strip and schedule it into a day block.
    """
    scenes, _, _ = parse_screenplay(
        "EXT. ALLEY - NIGHT\n\nShe runs.\n\n"
        "EXT. KEDZIE AVENUE - CONTINUOUS\n\nInto traffic.\n\n"
        "INT. BAR - DAY\n\nQuiet.\n\n"
        "INT. BACK ROOM - CONTINUOUS\n\nQuieter.\n"
    )

    assert [s.time_of_day for s in scenes] == ["NIGHT", "NIGHT", "DAY", "DAY"]


def test_time_synonyms_are_normalised() -> None:
    scenes, _, _ = parse_screenplay(
        "INT. A - MORNING\n\nx\n\nINT. B - EVENING\n\nx\n\nEXT. C - SUNSET\n\nx\n"
    )

    assert [s.time_of_day for s in scenes] == ["DAY", "NIGHT", "DUSK"]


def test_interior_exterior_variants() -> None:
    scenes, _, _ = parse_screenplay(
        "INT./EXT. CAR - DAY\n\nDriving.\n\nI/E. TRUCK - DAY\n\nAlso driving.\n"
    )

    assert scenes[0].interior == "INT/EXT"
    assert scenes[1].interior == "INT/EXT"


def test_forced_fountain_heading() -> None:
    """A leading period forces a scene heading in Fountain."""
    scenes, _, _ = parse_screenplay(".BLACK SCREEN\n\nNothing yet.\n\nINT. ROOM - DAY\n\nx\n")

    assert len(scenes) == 2
    assert scenes[0].slugline == "BLACK SCREEN"


def test_front_matter_is_extracted_and_removed() -> None:
    body, meta = strip_front_matter(
        "Title: THE PROJECTIONIST\nAuthor: Someone\n\n====\n\nINT. BOOTH - NIGHT\n\nx\n"
    )

    assert meta["title"] == "THE PROJECTIONIST"
    assert meta["author"] == "Someone"
    assert "Title:" not in body
    assert body.lstrip().startswith("INT. BOOTH")


def test_speakers_are_detected_and_extensions_stripped() -> None:
    scenes, _, _ = parse_screenplay(
        "INT. BOOTH - NIGHT\n\nShe threads film.\n\nMARISOL\nThere you go.\n\n"
        "MARISOL (CONT'D)\nBehave.\n\nTEDDY (O.S.)\nMr. Sandoval called.\n"
    )

    assert scenes[0].speakers == ["MARISOL", "TEDDY"]


def test_transitions_are_not_treated_as_characters() -> None:
    scenes, _, _ = parse_screenplay(
        "INT. ROOM - DAY\n\nHe waits.\n\nCUT TO:\n\nSomething else.\n"
    )

    assert "CUT TO" not in scenes[0].speakers
    assert "CUT TO:" not in scenes[0].speakers


def test_eighths_are_measured_on_wrapped_rows_not_source_lines() -> None:
    """A long action line wraps, and the measurement has to account for it.

    One source line of 400 characters is seven rows inside the action margin,
    so a scene written as a single long paragraph must measure larger than a
    scene written as a single short one.
    """
    long_line = "He waits, and the room waits with him, and the clock on the wall " * 12
    short, _, _ = parse_screenplay("INT. A - DAY\n\nHe waits.\n")
    long, _, _ = parse_screenplay(f"INT. B - DAY\n\n{long_line}\n")

    assert short[0].eighths == 1
    assert long[0].eighths > short[0].eighths


def test_dialogue_wraps_in_a_narrower_margin_than_action() -> None:
    """The same text measures longer as dialogue, because the column is narrower."""
    sentence = "I am telling you this once and you are going to listen to me now."
    as_action, _, _ = parse_screenplay(f"INT. A - DAY\n\n{sentence * 4}\n")
    as_dialogue, _, _ = parse_screenplay(f"INT. A - DAY\n\nRAY\n  {sentence * 4}\n")

    assert as_dialogue[0].eighths >= as_action[0].eighths


def test_every_scene_measures_at_least_one_eighth() -> None:
    """One eighth is the floor on a stripboard, however short the scene."""
    scenes, _, _ = parse_screenplay("INT. A - DAY\n\nx\n")

    assert scenes[0].eighths == 1


def test_many_short_scenes_sum_to_more_eighths_than_pages() -> None:
    """The one-eighth floor inflates the board relative to the page count.

    This is not a rounding bug, it is how a real stripboard behaves: twenty
    one-line scenes occupy about a page of paper but take twenty strips, each
    charged at the minimum eighth. Pinned here so nobody "fixes" it later.
    """
    script = "".join(f"INT. ROOM {i} - DAY\n\nA beat.\n\n" for i in range(20))
    scenes, _, pages = parse_screenplay(script)

    assert sum(s.eighths for s in scenes) == 20
    assert pages < 2.0


def test_page_count_is_rendered_rows_over_lines_per_page() -> None:
    """Page count comes from typeset rows, which is the actual contract.

    It is deliberately not derived from the summed eighths. Those are two
    different quantisations of the same text: eighths are rounded per scene and
    floored at one, so on a script of many similar-length scenes the rounding
    does not cancel out and the two figures legitimately diverge. Asserting
    they match would be asserting a coincidence.
    """
    body = "She crosses the room and puts the reel down on the bench. " * 8
    script = "".join(f"INT. ROOM {i} - DAY\n\n{body}\n\n" for i in range(10))
    scenes, _, pages = parse_screenplay(script)

    rows = sum(_rendered_rows(s.text) for s in scenes)
    assert pages == round(rows / LINES_PER_PAGE, 1)


def test_eighth_rounding_has_no_systematic_direction_across_lengths() -> None:
    """Across a spread of scene lengths, rounding should not be one-sided.

    A consistent downward bias would under-report a feature by several pages,
    and page count drives both the schedule and the budget.
    """
    deltas: list[float] = []
    for repeats in range(1, 14):
        body = "She crosses the room and puts the reel down on the bench. " * repeats
        scenes, _, _ = parse_screenplay(f"INT. ROOM - DAY\n\n{body}\n")
        true_eighths = _rendered_rows(scenes[0].text) / (LINES_PER_PAGE / 8)
        deltas.append(scenes[0].eighths - true_eighths)

    # Mean error well inside half an eighth in either direction.
    assert abs(sum(deltas) / len(deltas)) < 0.5


def test_scenes_are_numbered_sequentially_from_one() -> None:
    script = "".join(f"INT. ROOM {i} - DAY\n\nx\n\n" for i in range(5))
    scenes, _, _ = parse_screenplay(script)

    assert [s.number for s in scenes] == ["1", "2", "3", "4", "5"]


def test_page_starts_increase_monotonically() -> None:
    script = "".join(f"INT. ROOM {i} - DAY\n\nSome action.\n\n" for i in range(8))
    scenes, _, _ = parse_screenplay(script)

    starts = [s.page_start for s in scenes]
    assert starts == sorted(starts)
    assert starts[0] == 1.0


def test_script_with_no_sluglines_yields_nothing() -> None:
    """The caller needs to be able to tell this apart from a parse failure."""
    scenes, _, _ = parse_screenplay("Just some prose with no scene headings at all.\n")

    assert scenes == []


def test_crlf_input_is_handled() -> None:
    scenes, _, _ = parse_screenplay("INT. KITCHEN - DAY\r\n\r\nShe pours coffee.\r\n")

    assert len(scenes) == 1
    assert scenes[0].location == "KITCHEN"


def test_raw_text_is_retained_per_scene() -> None:
    scenes, _, _ = parse_screenplay(
        "INT. A - DAY\n\nFirst thing.\n\nINT. B - NIGHT\n\nSecond thing.\n"
    )

    assert "First thing." in scenes[0].text
    assert "Second thing." not in scenes[0].text
    assert "Second thing." in scenes[1].text


def test_detect_format() -> None:
    assert detect_format("script.fountain") == "fountain"
    assert detect_format("script.SPMD") == "fountain"
    assert detect_format("script.pdf") == "pdf"
    assert detect_format("script.fdx") == "fdx"
    assert detect_format("script.txt") == "plaintext"


def test_lines_per_page_is_the_industry_figure() -> None:
    assert LINES_PER_PAGE == 55.0
