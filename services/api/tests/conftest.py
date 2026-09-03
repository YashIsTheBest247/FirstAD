"""Shared builders for tests.

Constructing a ParsedScript by hand is noisy, so scenes are declared as terse
tuples and expanded here. Keeping the builders in one place means a schema
change breaks compilation in one file rather than twenty tests.
"""

from __future__ import annotations

import pytest

from app.schemas.production import (
    Breakdown,
    BreakdownElement,
    BudgetLine,
    BudgetTopSheet,
    CallSheet,
    CallTime,
    CastMember,
    Citation,
    ClearanceCategory,
    ClearanceEntity,
    ClearanceFinding,
    ClearanceReport,
    ComplianceReport,
    ElementCategory,
    Interior,
    LocationIntel,
    LocationsIntel,
    ParsedScript,
    RiskLevel,
    Scene,
    SceneBreakdown,
    ScheduledScene,
    ScriptHeader,
    ShootDay,
    Stripboard,
    StripColor,
    TimeOfDay,
)


def make_scene(
    number: str,
    location: str,
    interior: str = "INT",
    tod: str = "DAY",
    eighths: int = 4,
    characters: list[str] | None = None,
) -> Scene:
    inter = Interior(interior)
    time = TimeOfDay(tod)
    return Scene(
        number=number,
        slugline=f"{interior}. {location} - {tod}",
        interior=inter,
        location=location,
        time_of_day=time,
        page_start=float(number),
        eighths=eighths,
        synopsis=f"Something happens in {location.lower()}.",
        characters=characters or [],
        raw_text=f"{interior}. {location} - {tod}\n\nAction.",
    )


def make_script(scenes: list[Scene], title: str = "TEST SCRIPT") -> ParsedScript:
    return ParsedScript(
        header=ScriptHeader(
            title=title,
            author="Tests",
            page_count=round(sum(s.eighths for s in scenes) / 8, 1),
            scene_count=len(scenes),
            format_detected="fountain",
        ),
        scenes=scenes,
    )


def make_breakdown(scenes: list[Scene], heavy: set[str] | None = None) -> Breakdown:
    """A breakdown where the named scenes carry a stunt, making them heavy."""
    heavy = heavy or set()
    return Breakdown(
        scenes=[
            SceneBreakdown(
                scene_number=s.number,
                elements=(
                    [
                        BreakdownElement(
                            category=ElementCategory.STUNTS,
                            name="Fall",
                            flags_department=True,
                        )
                    ]
                    if s.number in heavy
                    else [BreakdownElement(category=ElementCategory.PROPS, name="Coffee cup")]
                ),
                estimated_setup_hours=1.5,
            )
            for s in scenes
        ]
    )


@pytest.fixture
def package() -> dict:
    """A complete production package, as the API would serialise one."""
    scenes = [
        make_scene("1", "BOOTH", "INT", "NIGHT", 3, ["MARISOL"]),
        make_scene("2", "MARQUEE", "EXT", "NIGHT", 1),
        make_scene("3", "CITY HALL", "INT", "DAY", 4, ["MARISOL", "HOLLOWAY"]),
    ]
    script = make_script(scenes, title="The Projectionist")

    board = Stripboard(
        days=[
            ShootDay(
                day_number=1,
                location="ARCADIA THEATER",
                total_eighths=4,
                company_move=False,
                notes=["Cast 1 works days 1 and 2."],
                scenes=[
                    ScheduledScene(
                        scene_number="1",
                        slugline="INT. BOOTH - NIGHT",
                        strip_color=StripColor.BLUE,
                        eighths=3,
                        location="BOOTH",
                        cast_ids=["1"],
                        synopsis="Marisol threads film.",
                    ),
                    ScheduledScene(
                        scene_number="2",
                        slugline="EXT. MARQUEE - NIGHT",
                        strip_color=StripColor.GREEN,
                        eighths=1,
                        location="MARQUEE",
                        cast_ids=[],
                        synopsis="A sedan idles.",
                    ),
                ],
            ),
            ShootDay(
                day_number=2,
                location="CITY HALL",
                total_eighths=4,
                company_move=True,
                scenes=[
                    ScheduledScene(
                        scene_number="3",
                        slugline="INT. CITY HALL - DAY",
                        strip_color=StripColor.WHITE,
                        eighths=4,
                        location="CITY HALL",
                        cast_ids=["1", "2"],
                        synopsis="She confronts the alderman.",
                    )
                ],
            ),
        ],
        cast=[
            CastMember(id="1", character="MARISOL", scene_numbers=["1", "3"], work_days=[1, 2]),
            CastMember(id="2", character="HOLLOWAY", scene_numbers=["3"], work_days=[2]),
        ],
        company_moves=1,
        shoot_day_count=2,
        rationale="Theatre first to hold the night block together.",
    )

    clearance = ClearanceReport(
        entities=[
            ClearanceEntity(
                id="person-holloway",
                text="Grant Holloway",
                category=ClearanceCategory.PERSON_NAME,
                scene_numbers=["3"],
                page_refs=[3.0],
                context="The alderman takes an envelope.",
                portrayal="alderman who takes a bribe",
                is_negative_portrayal=True,
            ),
            ClearanceEntity(
                id="phone-5550147",
                text="(312) 555-0147",
                category=ClearanceCategory.PHONE_NUMBER,
                scene_numbers=["1"],
                page_refs=[1.0],
                context="She reads the number aloud.",
                portrayal="neutral",
            ),
        ],
        findings=[
            ClearanceFinding(
                entity_id="person-holloway",
                risk=RiskLevel.RED,
                rationale="Name pattern collides with a sitting official and the portrayal is criminal.",
                real_world_matches=["A sitting alderman with a similar surname"],
                citations=[
                    Citation(
                        url="https://example.org/roster",
                        title="Council roster",
                        excerpt="Ward roster listing.",
                    )
                ],
                suggested_alternatives=["Grant Braddock"],
            ),
            ClearanceFinding(
                entity_id="phone-5550147",
                risk=RiskLevel.GREEN,
                rationale="Inside the 555-0100 to 555-0199 block reserved for fiction.",
                searched=False,
            ),
        ],
    )

    locations = LocationsIntel(
        locations=[
            LocationIntel(
                location="ARCADIA THEATER",
                jurisdiction="City of Chicago",
                permit_required=True,
                permit_cost_note="Fee schedule not confirmed in research.",
                lead_time_days=14,
                weather_window="May to October",
                hazards=["Night exterior", "Live traffic"],
                vendor_notes=["Needs a generator."],
                citations=[
                    Citation(
                        url="https://example.org/permits",
                        title="Film permits",
                        excerpt="Application guidance.",
                    )
                ],
            )
        ]
    )

    budget = BudgetTopSheet(
        above_the_line=[
            BudgetLine(
                account="1100",
                category="Story and rights",
                detail="Screenplay",
                amount_usd=25000,
                driver="Original screenplay, one writer.",
            )
        ],
        below_the_line=[
            BudgetLine(
                account="2100",
                category="Production staff",
                detail="Crew, 2 days",
                amount_usd=40000,
                driver="Two shooting days with a night block.",
            )
        ],
        post_and_other=[
            BudgetLine(
                account="4500",
                category="Legal",
                detail="Clearance and E&O",
                amount_usd=9000,
                driver="One red clearance item needs a rename or a licence.",
            )
        ],
        contingency_pct=10.0,
        assumptions=["US independent short, non-union crew."],
    )

    call_sheets = [
        CallSheet(
            day_number=1,
            general_call="15:00",
            location="ARCADIA THEATER",
            scenes=board.days[0].scenes,
            cast_calls=[CallTime(who="MARISOL", time="15:30", note="Hair and makeup")],
            department_calls=[CallTime(who="Rigging", time="13:00", note="Pre-light the booth")],
            safety_notes=["Night exterior. Traffic control required on the sidewalk."],
            weather_note="Rain cover needed.",
        )
    ]

    return {
        "run_id": "testrun0001",
        "script": script.model_dump(mode="json"),
        "breakdown": make_breakdown(scenes).model_dump(mode="json"),
        "clearance": clearance.model_dump(mode="json"),
        "locations": locations.model_dump(mode="json"),
        "stripboard": board.model_dump(mode="json"),
        "compliance": ComplianceReport(flags=[]).model_dump(mode="json"),
        "budget": budget.model_dump(mode="json"),
        "call_sheets": [c.model_dump(mode="json") for c in call_sheets],
        "trace": [],
    }
