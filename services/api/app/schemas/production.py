"""Typed contracts for every stage of the Greenlight pipeline.

Each stage consumes the previous stage's model and emits its own. Nothing is
passed between agents as free text, which is what keeps a seven-stage LLM
pipeline deterministic and inspectable.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Stage 1 - Script Supervisor
# --------------------------------------------------------------------------


class Interior(str, Enum):
    INT = "INT"
    EXT = "EXT"
    INT_EXT = "INT/EXT"


class TimeOfDay(str, Enum):
    DAY = "DAY"
    NIGHT = "NIGHT"
    DAWN = "DAWN"
    DUSK = "DUSK"
    CONTINUOUS = "CONTINUOUS"


class StripColor(str, Enum):
    """The standard production stripboard colour convention.

    Every 1st AD reads these four colours the same way, so the scheduler emits
    them rather than inventing its own scheme.
    """

    WHITE = "white"    # INT DAY
    YELLOW = "yellow"  # EXT DAY
    BLUE = "blue"      # INT NIGHT
    GREEN = "green"    # EXT NIGHT

    @classmethod
    def for_scene(cls, interior: "Interior", tod: "TimeOfDay") -> "StripColor":
        night = tod in (TimeOfDay.NIGHT, TimeOfDay.DUSK)
        outside = interior in (Interior.EXT, Interior.INT_EXT)
        if outside:
            return cls.GREEN if night else cls.YELLOW
        return cls.BLUE if night else cls.WHITE


class Scene(BaseModel):
    """One slugline and everything under it, up to the next slugline."""

    number: str = Field(description="Scene number as written or assigned, such as 14 or 14A")
    slugline: str = Field(description="The full heading line, such as INT. PRECINCT BULLPEN - NIGHT")
    interior: Interior
    location: str = Field(description="Set name only, with no INT/EXT prefix and no time suffix")
    time_of_day: TimeOfDay
    page_start: float = Field(description="Page number where the scene begins")
    eighths: int = Field(ge=1, description="Scene length in page eighths. Eight eighths is one page.")
    synopsis: str = Field(description="One sentence of what happens, for the stripboard strip")
    characters: list[str] = Field(default_factory=list, description="Speaking characters present")
    background: list[str] = Field(default_factory=list, description="Silent or background performers described")
    raw_text: str = Field(default="", description="Verbatim scene text, retained for downstream anchoring")

    @property
    def strip_color(self) -> StripColor:
        return StripColor.for_scene(self.interior, self.time_of_day)


class ScriptHeader(BaseModel):
    title: str
    author: str | None = None
    page_count: float
    scene_count: int
    format_detected: Literal["fountain", "pdf", "fdx", "plaintext"]


class ParsedScript(BaseModel):
    """Stage 1 output."""

    header: ScriptHeader
    scenes: list[Scene]


# --------------------------------------------------------------------------
# Stage 2a - Breakdown
# --------------------------------------------------------------------------


class ElementCategory(str, Enum):
    """Standard breakdown-sheet categories, matching the paper form."""

    CAST = "cast"
    BACKGROUND = "background"
    STUNTS = "stunts"
    VEHICLES = "vehicles"
    PROPS = "props"
    WARDROBE = "wardrobe"
    MAKEUP_HAIR = "makeup_hair"
    SPECIAL_EFFECTS = "special_effects"
    VISUAL_EFFECTS = "visual_effects"
    ANIMALS = "animals"
    SET_DRESSING = "set_dressing"
    SOUND = "sound"
    SPECIAL_EQUIPMENT = "special_equipment"


class BreakdownElement(BaseModel):
    category: ElementCategory
    name: str
    note: str | None = Field(default=None, description="Why it is needed, in a few words")
    flags_department: bool = Field(
        default=False,
        description="True when this element forces a department call, a permit, or a safety officer",
    )


class SceneBreakdown(BaseModel):
    scene_number: str
    elements: list[BreakdownElement]
    estimated_setup_hours: float = Field(
        ge=0, description="Crew hours to light and rig this scene, excluding shooting"
    )


class Breakdown(BaseModel):
    """Stage 2a output."""

    scenes: list[SceneBreakdown]


# --------------------------------------------------------------------------
# Stage 2b and 3b - Clearance
# --------------------------------------------------------------------------


class ClearanceCategory(str, Enum):
    PERSON_NAME = "person_name"
    BUSINESS = "business"
    PHONE_NUMBER = "phone_number"
    ADDRESS = "address"
    LICENSE_PLATE = "license_plate"
    BRAND_PRODUCT = "brand_product"
    ARTWORK_MUSIC = "artwork_music"
    REAL_EVENT = "real_event"
    ORGANISATION = "organisation"


class ClearanceEntity(BaseModel):
    """Something in the script that a clearance report has to check."""

    id: str
    text: str = Field(description="The literal string as written in the script")
    category: ClearanceCategory
    scene_numbers: list[str]
    page_refs: list[float]
    context: str = Field(description="Surrounding line, so a researcher can judge portrayal")
    portrayal: str = Field(
        description="How the script depicts it, such as corrupt city official or neutral background signage"
    )
    is_negative_portrayal: bool = Field(
        default=False,
        description="True when depicted unlawfully, immorally, or unflatteringly. Drives the risk ceiling.",
    )


class RiskLevel(str, Enum):
    RED = "red"
    AMBER = "amber"
    GREEN = "green"


class Citation(BaseModel):
    url: str
    title: str
    excerpt: str


class ClearanceFinding(BaseModel):
    """Stage 3b output, one per entity."""

    entity_id: str
    risk: RiskLevel
    rationale: str = Field(description="Plain-language reason a production lawyer would accept")
    real_world_matches: list[str] = Field(
        default_factory=list, description="Actual people or entities found that collide with this reference"
    )
    citations: list[Citation] = Field(default_factory=list)
    suggested_alternatives: list[str] = Field(
        default_factory=list, description="Replacements verified to return no significant match"
    )
    searched: bool = Field(default=True, description="False when resolved without a live search")


class ClearanceReport(BaseModel):
    entities: list[ClearanceEntity]
    findings: list[ClearanceFinding]

    @property
    def red_count(self) -> int:
        return sum(1 for f in self.findings if f.risk is RiskLevel.RED)


# --------------------------------------------------------------------------
# Stage 3a - Locations
# --------------------------------------------------------------------------


class LocationIntel(BaseModel):
    """Real-world production intelligence for one set, grounded in live search."""

    location: str = Field(description="Set name as it appears in the sluglines")
    jurisdiction: str | None = Field(default=None, description="City or county that issues the permit")
    permit_required: bool = True
    permit_cost_note: str | None = None
    lead_time_days: int | None = None
    weather_window: str | None = Field(default=None, description="Months that suit this set, for EXT scenes")
    hazards: list[str] = Field(default_factory=list)
    vendor_notes: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class LocationsIntel(BaseModel):
    locations: list[LocationIntel]


# --------------------------------------------------------------------------
# Stage 4 - Scheduler
# --------------------------------------------------------------------------


class ScheduledScene(BaseModel):
    scene_number: str
    slugline: str
    strip_color: StripColor
    eighths: int
    location: str
    cast_ids: list[str] = Field(default_factory=list)
    synopsis: str


class ShootDay(BaseModel):
    day_number: int
    shoot_date: date | None = None
    unit: str = "Main Unit"
    location: str
    scenes: list[ScheduledScene]
    total_eighths: int
    company_move: bool = Field(
        default=False, description="True when this day starts at a different location than the previous day"
    )
    notes: list[str] = Field(default_factory=list)


class CastMember(BaseModel):
    id: str = Field(description="Cast number used on the stripboard")
    character: str
    scene_numbers: list[str]
    work_days: list[int] = Field(default_factory=list)


class Stripboard(BaseModel):
    """Stage 4 output."""

    days: list[ShootDay]
    cast: list[CastMember]
    company_moves: int
    shoot_day_count: int
    rationale: str = Field(description="Why the scheduler grouped days the way it did")


# --------------------------------------------------------------------------
# Stage 5 - Compliance
# --------------------------------------------------------------------------


class ComplianceSeverity(str, Enum):
    BLOCKER = "blocker"
    WARNING = "warning"
    ADVISORY = "advisory"


class ComplianceFlag(BaseModel):
    severity: ComplianceSeverity
    rule: str = Field(description="Short rule name, such as 10-hour turnaround")
    day_number: int | None = None
    scene_numbers: list[str] = Field(default_factory=list)
    detail: str
    remedy: str = Field(description="The concrete schedule change that clears this flag")


class ComplianceReport(BaseModel):
    flags: list[ComplianceFlag]


# --------------------------------------------------------------------------
# Stage 6 - Line Producer
# --------------------------------------------------------------------------


class BudgetLine(BaseModel):
    account: str = Field(description="Account code, such as 2100")
    category: str
    detail: str
    amount_usd: float
    driver: str = Field(description="What in the script drives this cost")


class BudgetTopSheet(BaseModel):
    """Stage 6 output."""

    above_the_line: list[BudgetLine]
    below_the_line: list[BudgetLine]
    post_and_other: list[BudgetLine]
    contingency_pct: float = 10.0
    assumptions: list[str] = Field(default_factory=list)

    @property
    def subtotal(self) -> float:
        rows = self.above_the_line + self.below_the_line + self.post_and_other
        return round(sum(r.amount_usd for r in rows), 2)

    @property
    def total(self) -> float:
        return round(self.subtotal * (1 + self.contingency_pct / 100), 2)


# --------------------------------------------------------------------------
# Stage 7 - Call Sheet
# --------------------------------------------------------------------------


class CallTime(BaseModel):
    who: str
    time: str
    note: str | None = None


class CallSheet(BaseModel):
    day_number: int
    shoot_date: date | None = None
    general_call: str
    location: str
    scenes: list[ScheduledScene]
    cast_calls: list[CallTime]
    department_calls: list[CallTime]
    safety_notes: list[str] = Field(default_factory=list)
    weather_note: str | None = None
    nearest_hospital: str | None = None


# --------------------------------------------------------------------------
# Envelope
# --------------------------------------------------------------------------


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class StageTrace(BaseModel):
    """One row of the agent activity log the UI renders live."""

    stage: str
    agent: str
    crew_role: str = Field(description="The real production job this agent stands in for")
    status: StageStatus
    started_at: float | None = None
    finished_at: float | None = None
    detail: str = ""
    model: str | None = None
    searches: int = 0

    @property
    def duration_s(self) -> float | None:
        if self.started_at and self.finished_at:
            return round(self.finished_at - self.started_at, 2)
        return None


class ProductionPackage(BaseModel):
    """Everything the pipeline produces for one screenplay."""

    run_id: str
    script: ParsedScript
    breakdown: Breakdown
    clearance: ClearanceReport
    locations: LocationsIntel
    stripboard: Stripboard
    compliance: ComplianceReport
    budget: BudgetTopSheet
    call_sheets: list[CallSheet]
    trace: list[StageTrace]
