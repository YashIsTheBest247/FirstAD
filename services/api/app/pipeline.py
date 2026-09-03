"""The First AD pipeline.

Seven stages, fixed order, typed handoff between each. The only concurrency is
where the work is genuinely independent: the breakdown and the clearance
extraction do not depend on each other, and neither do the location research and
the clearance research. Everything else is strictly ordered, because a schedule
cannot be built before the breakdown exists and a budget cannot be built before
the schedule does.

The pipeline is an async generator so the UI can watch the crew work rather than
staring at a spinner for two minutes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import date
from typing import Any, AsyncIterator

from app.agents.crew import (
    CREW_ROLES,
    CallSheetSet,
    ClearanceEntitySet,
    ClearanceFindingSet,
    build_crew,
)
from app.core.adk_runtime import AgentExecutionError, run_agent
from app.core.clearance_rules import is_fiction_phone, pick_canonical, same_reference
from app.core.config import get_settings
from app.core.scheduling import (
    assign_shoot_dates,
    default_start_date,
    derive_cast,
    optimise_stripboard,
)
from app.core.screenplay import detect_format, parse_screenplay
from app.schemas.production import (
    Breakdown,
    ClearanceCategory,
    BudgetTopSheet,
    CastMember,
    ClearanceReport,
    ComplianceReport,
    LocationsIntel,
    ParsedScript,
    ProductionPackage,
    RiskLevel,
    ScriptHeader,
    StageStatus,
    StageTrace,
    Stripboard,
)
from app.tools.parallel_search import (
    ParallelResearch,
    research_clearance_entity,
    research_location,
    verify_alternative_is_clear,
)

log = logging.getLogger(__name__)

# Scenes per batch when fanning a stage out. Small enough that a batch stays
# well inside a comfortable context, large enough that a feature does not turn
# into a hundred calls.
SCENE_BATCH = 10

# How many clearance entities get a live search is read from settings, because
# every search is billable and the sensible cap depends on your plan.


def _compact_scenes(script: ParsedScript, include_text: bool = False) -> str:
    """Render scenes for a prompt without wasting tokens on JSON syntax."""
    rows = []
    for s in script.scenes:
        head = (
            f"#{s.number} | {s.slugline} | {s.eighths}/8 | p{s.page_start} | "
            f"cast: {', '.join(s.characters) or 'none'}"
        )
        if include_text:
            rows.append(f"{head}\n{s.raw_text}")
        else:
            rows.append(f"{head}\n  {s.synopsis}")
    return "\n\n".join(rows)


def _chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class PipelineRun:
    """One screenplay moving through the crew."""

    def __init__(
        self,
        raw_text: str,
        filename: str,
        setting: str,
        start_date: date | None = None,
    ) -> None:
        self.run_id = uuid.uuid4().hex[:12]
        self.raw_text = raw_text
        self.filename = filename
        self.setting = setting.strip() or "an unnamed United States city"
        # Without a real first day the schedule cannot be booked against
        # anything, and permit lead times mean nothing.
        self.start_date = start_date or default_start_date()
        self.crew = build_crew()
        self.research = ParallelResearch()
        self.trace: list[StageTrace] = []
        # Stages that fell back rather than failing the whole run.
        self.degraded: list[str] = []
        self._settings = get_settings()

    # -- tracing ---------------------------------------------------------

    def _begin(self, stage: str, agent: str, detail: str = "", model: str | None = None) -> StageTrace:
        entry = StageTrace(
            stage=stage,
            agent=agent,
            crew_role=CREW_ROLES.get(agent, "Production Office"),
            status=StageStatus.RUNNING,
            started_at=time.time(),
            detail=detail,
            model=model,
        )
        self.trace.append(entry)
        return entry

    def _finish(self, entry: StageTrace, detail: str, searches: int = 0) -> StageTrace:
        entry.status = StageStatus.DONE
        entry.finished_at = time.time()
        entry.detail = detail
        entry.searches = searches
        return entry

    @staticmethod
    def _event(entry: StageTrace) -> dict[str, Any]:
        return {"type": "stage", "stage": entry.model_dump(mode="json") | {"duration_s": entry.duration_s}}

    # -- stages ----------------------------------------------------------

    async def _stage_parse(self) -> ParsedScript:
        raw_scenes, meta, page_count = parse_screenplay(self.raw_text)
        if not raw_scenes:
            raise ValueError(
                "No scene headings were found. A screenplay needs sluglines such as "
                "'INT. KITCHEN - DAY' for the breakdown to work."
            )

        header = ScriptHeader(
            title=meta.get("title", self.filename.rsplit(".", 1)[0]).upper(),
            author=meta.get("author"),
            page_count=page_count,
            scene_count=len(raw_scenes),
            format_detected=detect_format(self.filename),
        )

        # The parser's output is authoritative for everything mechanical. The
        # Script Supervisor only fills in synopsis, cast, and background.
        payload = {
            "header": header.model_dump(mode="json"),
            "scenes": [
                {
                    "number": s.number,
                    "slugline": s.slugline,
                    "interior": s.interior,
                    "location": s.location,
                    "time_of_day": s.time_of_day,
                    "page_start": s.page_start,
                    "eighths": s.eighths,
                    "parser_speakers": s.speakers,
                    "text": s.text,
                }
                for s in raw_scenes
            ],
        }

        prompt = (
            f"Screenplay: {header.title}\n"
            f"Setting for this production: {self.setting}\n\n"
            f"Parsed scenes follow as JSON. Return a ParsedScript.\n\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

        script = await run_agent(
            self.crew["script_supervisor"], prompt, ParsedScript, run_id=self.run_id
        )

        # Re-attach the verbatim text, which the agent was told to drop, and
        # re-assert the parser's mechanical fields in case a value drifted.
        by_number = {s.number: s for s in raw_scenes}
        for scene in script.scenes:
            raw = by_number.get(scene.number)
            if raw is None:
                continue
            scene.raw_text = raw.text
            scene.eighths = raw.eighths
            scene.page_start = raw.page_start
        script.header = header
        return script

    async def _stage_breakdown(self, script: ParsedScript) -> Breakdown:
        batches = _chunks(script.scenes, SCENE_BATCH)

        async def run_batch(batch: list[Any]) -> Breakdown:
            body = "\n\n".join(f"#{s.number} | {s.slugline}\n{s.raw_text}" for s in batch)
            prompt = (
                f"Break down the following {len(batch)} scenes.\n"
                f"Production setting: {self.setting}\n\n{body}"
            )
            return await run_agent(
                self.crew["breakdown_agent"], prompt, Breakdown, run_id=self.run_id
            )

        results = await asyncio.gather(*(run_batch(b) for b in batches), return_exceptions=True)

        merged: Breakdown = Breakdown(scenes=[])
        for result in results:
            if isinstance(result, BaseException):
                log.warning("breakdown batch failed: %s", result)
                continue
            merged.scenes.extend(result.scenes)
        if not merged.scenes:
            raise AgentExecutionError("Every breakdown batch failed.")
        return merged

    async def _stage_extract_clearance(self, script: ParsedScript) -> ClearanceEntitySet:
        batches = _chunks(script.scenes, SCENE_BATCH)

        async def run_batch(batch: list[Any]) -> ClearanceEntitySet:
            body = "\n\n".join(f"#{s.number} | p{s.page_start} | {s.slugline}\n{s.raw_text}" for s in batch)
            prompt = (
                f"Extract every clearable reference from the following scenes.\n"
                f"Production setting: {self.setting}\n\n{body}"
            )
            return await run_agent(
                self.crew["clearance_extractor"], prompt, ClearanceEntitySet, run_id=self.run_id
            )

        results = await asyncio.gather(*(run_batch(b) for b in batches), return_exceptions=True)

        # Merge references that denote the same thing, not merely identical
        # strings. A script names a character in full once and by first name
        # thereafter, and each spelling arrives as its own entity. Left
        # separate they spend the live-search budget twice on one person and
        # push real references past the cap.
        merged: list[Any] = []
        for result in results:
            if isinstance(result, BaseException):
                log.warning("clearance extraction batch failed: %s", result)
                continue

            for entity in result.entities:
                for existing in merged:
                    if existing.category is not entity.category:
                        continue
                    if not same_reference(existing.text, entity.text, entity.category.value):
                        continue

                    existing.text = pick_canonical(existing.text, entity.text)
                    existing.scene_numbers = sorted(
                        set(existing.scene_numbers) | set(entity.scene_numbers)
                    )
                    existing.page_refs = sorted(set(existing.page_refs) | set(entity.page_refs))
                    # A reference is only as safe as its worst depiction.
                    existing.is_negative_portrayal = (
                        existing.is_negative_portrayal or entity.is_negative_portrayal
                    )
                    if entity.is_negative_portrayal and not existing.is_negative_portrayal:
                        existing.portrayal = entity.portrayal
                    break
                else:
                    merged.append(entity)

        return ClearanceEntitySet(entities=merged)

    async def _stage_locations(self, script: ParsedScript) -> tuple[LocationsIntel, int]:
        distinct: dict[str, bool] = {}
        for scene in script.scenes:
            base = scene.location.split(" - ")[0].strip()
            is_ext = scene.interior.value in ("EXT", "INT/EXT")
            distinct[base] = distinct.get(base, False) or is_ext

        outcomes = await asyncio.gather(
            *(
                research_location(
                    self.research, location=loc, setting_hint=self.setting, is_exterior=is_ext
                )
                for loc, is_ext in distinct.items()
            )
        )

        research_blocks = []
        for (loc, _), outcome in zip(distinct.items(), outcomes):
            block = outcome.evidence or "No research returned for this set."
            research_blocks.append(f"=== SET: {loc} ===\n{block}")

        prompt = (
            f"Production setting: {self.setting}\n"
            f"Sets in the script: {', '.join(distinct)}\n\n"
            f"Live permit and location research follows.\n\n" + "\n\n".join(research_blocks)
        )

        intel = await run_agent(
            self.crew["locations_agent"], prompt, LocationsIntel, run_id=self.run_id
        )
        return intel, len([o for o in outcomes if o.found_anything])

    async def _stage_clearance_risk(self, entities: ClearanceEntitySet) -> tuple[ClearanceReport, int]:
        # Research the riskiest entities first, so a cap never drops the ones
        # that matter. Negative portrayal is the strongest predictor of exposure.
        ordered = sorted(
            entities.entities,
            key=lambda e: (not e.is_negative_portrayal, e.category.value, -len(e.scene_numbers)),
        )
        cap = self._settings.max_researched_entities
        researched = ordered[:cap]

        outcomes = await asyncio.gather(
            *(
                research_clearance_entity(
                    self.research,
                    text=e.text,
                    category=e.category.value,
                    portrayal=e.portrayal,
                    setting_hint=self.setting,
                )
                for e in researched
            )
        )

        # For anything depicted negatively, pre-verify replacement names so the
        # report can suggest alternatives that are themselves clear.
        needs_alternatives = [e for e in researched if e.is_negative_portrayal][:6]
        verified_alternatives: dict[str, list[str]] = {}
        if needs_alternatives:
            candidates = {
                e.id: _candidate_names(e.text, e.category.value) for e in needs_alternatives
            }
            checks = [
                (eid, cand)
                for eid, cands in candidates.items()
                for cand in cands
            ]
            check_results = await asyncio.gather(
                *(
                    verify_alternative_is_clear(
                        self.research, candidate=cand, setting_hint=self.setting
                    )
                    for _, cand in checks
                )
            )
            for (eid, cand), is_clear in zip(checks, check_results):
                if is_clear:
                    verified_alternatives.setdefault(eid, []).append(cand)

        blocks = []
        for entity, outcome in zip(researched, outcomes):
            evidence = outcome.evidence or "SEARCH RETURNED NOTHING SUBSTANTIVE."
            if outcome.error:
                evidence = f"SEARCH UNAVAILABLE: {outcome.error}"
            alts = verified_alternatives.get(entity.id, [])
            blocks.append(
                f"=== ENTITY {entity.id} ===\n"
                f"text: {entity.text}\n"
                f"category: {entity.category.value}\n"
                f"portrayal: {entity.portrayal}\n"
                f"negative_portrayal: {entity.is_negative_portrayal}\n"
                f"scenes: {', '.join(entity.scene_numbers)}\n"
                f"pre-verified clear alternatives: {', '.join(alts) if alts else 'none supplied'}\n"
                f"--- research ---\n{evidence}"
            )

        prompt = (
            f"Production setting: {self.setting}\n"
            f"Grade the following {len(researched)} entities. Return one finding per entity, "
            f"using the entity id exactly.\n\n" + "\n\n".join(blocks)
        )

        graded = await run_agent(
            self.crew["risk_scorer"], prompt, ClearanceFindingSet, run_id=self.run_id
        )

        # A number inside the 555-0100 to 555-0199 block is cleared by rule,
        # not by judgement, so the verdict is asserted here rather than left to
        # the model. Screenplays spell numbers out in dialogue, which reads
        # past a prompt instruction, and getting this wrong flags the one
        # reference a writer already did correctly.
        by_id = {e.id: e for e in entities.entities}
        for finding in graded.findings:
            entity = by_id.get(finding.entity_id)
            if entity is None or entity.category is not ClearanceCategory.PHONE_NUMBER:
                continue
            if not is_fiction_phone(entity.text):
                continue
            finding.risk = RiskLevel.GREEN
            finding.rationale = (
                "Inside the 555-0100 to 555-0199 block, which the North American Numbering "
                "Plan reserves for fictional use. Cleared by rule, so no search was needed."
            )
            finding.real_world_matches = []
            finding.suggested_alternatives = []
            finding.searched = False

        # Anything past the research cap is reported honestly as unreviewed
        # rather than silently dropped.
        graded_ids = {f.entity_id for f in graded.findings}
        for entity in ordered[cap:]:
            if entity.id not in graded_ids:
                graded.findings.append(
                    _unreviewed_finding(entity.id)
                )

        return (
            ClearanceReport(entities=entities.entities, findings=graded.findings),
            len([o for o in outcomes if o.found_anything]),
        )

    async def _stage_schedule(
        self, script: ParsedScript, breakdown: Breakdown, locations: LocationsIntel
    ) -> Stripboard:
        candidate = optimise_stripboard(script, breakdown)
        cast_order = derive_cast(script)
        cast = [
            CastMember(id=str(i + 1), character=name, scene_numbers=scenes)
            for i, (name, scenes) in enumerate(cast_order)
        ]

        prompt = (
            f"Production setting: {self.setting}\n"
            f"Script: {script.header.title}, {script.header.page_count} pages, "
            f"{script.header.scene_count} scenes.\n\n"
            f"=== CANDIDATE STRIPBOARD FROM THE OPTIMISER ===\n"
            f"{json.dumps([d.model_dump(mode='json') for d in candidate], ensure_ascii=False)}\n\n"
            f"=== CAST, ORDERED BY WORKLOAD ===\n"
            f"{json.dumps([c.model_dump(mode='json') for c in cast], ensure_ascii=False)}\n\n"
            f"=== BREAKDOWN ===\n"
            f"{json.dumps(breakdown.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"=== LOCATION INTELLIGENCE ===\n"
            f"{json.dumps(locations.model_dump(mode='json'), ensure_ascii=False)}"
        )

        try:
            board = await run_agent(
                self.crew["scheduler_agent"], prompt, Stripboard, run_id=self.run_id
            )
        except AgentExecutionError as exc:
            # The optimiser already produced a valid board; the agent only adds
            # a 1st AD's judgement on top. Losing that judgement is a real
            # downgrade, but it is not a reason to throw away a run that has
            # already cost minutes of work and every other stage.
            log.warning("scheduler agent failed, falling back to the optimiser board: %s", exc)
            self.degraded.append(f"Scheduler: {exc}")
            board = Stripboard(
                days=candidate,
                cast=cast,
                company_moves=sum(1 for d in candidate if d.company_move),
                shoot_day_count=len(candidate),
                rationale=(
                    "Produced by the deterministic optimiser alone. The Scheduler agent was "
                    "unavailable, so this board groups scenes by set and lighting state to "
                    "minimise company moves, but it has not been reviewed for stranded cast, "
                    "day weight, or permit lead times."
                ),
            )

        board.shoot_day_count = len(board.days)
        board.company_moves = sum(1 for d in board.days if d.company_move)

        assign_shoot_dates(board.days, self.start_date)

        # Cast work days are derivable from the board, and the agent frequently
        # leaves them empty, which silently breaks the day-out-of-days grid.
        for day in board.days:
            numbers = {s.scene_number for s in day.scenes}
            for member in board.cast:
                if numbers & set(member.scene_numbers) and day.day_number not in member.work_days:
                    member.work_days.append(day.day_number)
        for member in board.cast:
            member.work_days.sort()

        return board

    async def _stage_compliance(self, board: Stripboard, breakdown: Breakdown) -> ComplianceReport:
        prompt = (
            f"=== SHOOTING SCHEDULE ===\n"
            f"{json.dumps(board.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"=== BREAKDOWN ===\n"
            f"{json.dumps(breakdown.model_dump(mode='json'), ensure_ascii=False)}"
        )
        return await run_agent(
            self.crew["compliance_agent"], prompt, ComplianceReport, run_id=self.run_id
        )

    async def _stage_budget(
        self,
        script: ParsedScript,
        board: Stripboard,
        breakdown: Breakdown,
        locations: LocationsIntel,
        clearance: ClearanceReport,
    ) -> BudgetTopSheet:
        flagged = [f for f in clearance.findings if f.risk.value in ("red", "amber")]
        prompt = (
            f"Script: {script.header.title}, {script.header.page_count} pages.\n"
            f"Schedule: {board.shoot_day_count} shooting days, {board.company_moves} company moves.\n"
            f"Production setting: {self.setting}\n\n"
            f"=== SCHEDULE ===\n{json.dumps(board.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"=== BREAKDOWN ===\n{json.dumps(breakdown.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"=== LOCATIONS ===\n{json.dumps(locations.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"=== CLEARANCE ITEMS NEEDING LEGAL WORK: {len(flagged)} ==="
        )
        return await run_agent(self.crew["line_producer"], prompt, BudgetTopSheet, run_id=self.run_id)

    async def _stage_call_sheets(
        self, board: Stripboard, breakdown: Breakdown, compliance: ComplianceReport, locations: LocationsIntel
    ) -> CallSheetSet:
        prompt = (
            f"=== SCHEDULE ===\n{json.dumps(board.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"=== BREAKDOWN ===\n{json.dumps(breakdown.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"=== COMPLIANCE FLAGS ===\n{json.dumps(compliance.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"=== LOCATIONS ===\n{json.dumps(locations.model_dump(mode='json'), ensure_ascii=False)}"
        )
        return await run_agent(self.crew["call_sheet_agent"], prompt, CallSheetSet, run_id=self.run_id)

    # -- driver ----------------------------------------------------------

    async def run(self) -> AsyncIterator[dict[str, Any]]:
        """Drive the crew, emitting a progress event as each stage turns over."""
        yield {
            "type": "run_started",
            "run_id": self.run_id,
            "setting": self.setting,
            "parallel_enabled": self.research.enabled,
        }

        try:
            # Stage 1
            entry = self._begin("script", "script_supervisor", "Parsing sluglines and measuring pages")
            yield self._event(entry)
            script = await self._stage_parse()
            yield self._event(
                self._finish(
                    entry,
                    f"{script.header.scene_count} scenes, {script.header.page_count} pages",
                )
            )

            # Stage 2, concurrent
            e_break = self._begin("breakdown", "breakdown_agent", "Tagging elements scene by scene")
            e_extract = self._begin("clearance_extract", "clearance_extractor", "Finding clearable references")
            yield self._event(e_break)
            yield self._event(e_extract)

            breakdown, entities = await asyncio.gather(
                self._stage_breakdown(script), self._stage_extract_clearance(script)
            )

            element_count = sum(len(s.elements) for s in breakdown.scenes)
            yield self._event(self._finish(e_break, f"{element_count} elements across {len(breakdown.scenes)} scenes"))
            yield self._event(self._finish(e_extract, f"{len(entities.entities)} references to check"))

            # Stage 3, concurrent, both grounded in Parallel Search
            e_loc = self._begin("locations", "locations_agent", "Researching permits and jurisdictions")
            e_risk = self._begin("clearance_risk", "risk_scorer", "Checking references against the real world")
            yield self._event(e_loc)
            yield self._event(e_risk)

            (locations, loc_hits), (clearance, risk_hits) = await asyncio.gather(
                self._stage_locations(script), self._stage_clearance_risk(entities)
            )

            yield self._event(
                self._finish(e_loc, f"{len(locations.locations)} sets researched", searches=loc_hits)
            )
            yield self._event(
                self._finish(
                    e_risk,
                    f"{clearance.red_count} red, "
                    f"{sum(1 for f in clearance.findings if f.risk.value == 'amber')} amber",
                    searches=risk_hits,
                )
            )

            # Stage 4
            e_sched = self._begin("schedule", "scheduler_agent", "Optimising the stripboard")
            yield self._event(e_sched)
            board = await self._stage_schedule(script, breakdown, locations)
            yield self._event(
                self._finish(
                    e_sched, f"{board.shoot_day_count} shooting days, {board.company_moves} company moves"
                )
            )

            # Stage 5
            e_comp = self._begin("compliance", "compliance_agent", "Checking turnaround, minors, and safety")
            yield self._event(e_comp)
            try:
                compliance = await self._stage_compliance(board, breakdown)
                blockers = sum(1 for f in compliance.flags if f.severity.value == "blocker")
                detail = f"{len(compliance.flags)} flags, {blockers} blocking"
            except AgentExecutionError as exc:
                log.warning("compliance stage failed: %s", exc)
                self.degraded.append(f"Compliance: {exc}")
                compliance = ComplianceReport(flags=[])
                detail = "unavailable, schedule not checked against the rules"
            yield self._event(self._finish(e_comp, detail))

            # Stage 6
            e_bud = self._begin("budget", "line_producer", "Building the top sheet")
            yield self._event(e_bud)
            try:
                budget = await self._stage_budget(script, board, breakdown, locations, clearance)
                detail = f"${budget.total:,.0f} including contingency"
            except AgentExecutionError as exc:
                log.warning("budget stage failed: %s", exc)
                self.degraded.append(f"Line Producer: {exc}")
                budget = BudgetTopSheet(
                    above_the_line=[], below_the_line=[], post_and_other=[],
                    assumptions=["The Line Producer was unavailable, so no budget was produced."],
                )
                detail = "unavailable, no top sheet produced"
            yield self._event(self._finish(e_bud, detail))

            # Stage 7
            e_call = self._begin("call_sheets", "call_sheet_agent", "Cutting call sheets")
            yield self._event(e_call)
            try:
                call_sheets = await self._stage_call_sheets(board, breakdown, compliance, locations)
                detail = f"{len(call_sheets.call_sheets)} call sheets"
            except AgentExecutionError as exc:
                log.warning("call sheet stage failed: %s", exc)
                self.degraded.append(f"2nd AD: {exc}")
                call_sheets = CallSheetSet(call_sheets=[])
                detail = "unavailable, no call sheets cut"

            # The date belongs to the shooting day, not to the agent's opinion
            # of it, so it is copied across rather than generated.
            dates = {d.day_number: d.shoot_date for d in board.days}
            for sheet in call_sheets.call_sheets:
                sheet.shoot_date = dates.get(sheet.day_number)
            yield self._event(self._finish(e_call, detail))

            package = ProductionPackage(
                run_id=self.run_id,
                script=script,
                breakdown=breakdown,
                clearance=clearance,
                locations=locations,
                stripboard=board,
                compliance=compliance,
                budget=budget,
                call_sheets=call_sheets.call_sheets,
                trace=self.trace,
            )

            yield {
                "type": "complete",
                "run_id": self.run_id,
                "searches_run": self.research.call_count,
                "degraded": self.degraded,
                "package": package.model_dump(mode="json"),
            }

        except Exception as exc:  # noqa: BLE001 - surfaced to the client as a failed run
            log.exception("pipeline failed")
            if self.trace:
                last = self.trace[-1]
                if last.status is StageStatus.RUNNING:
                    last.status = StageStatus.FAILED
                    last.finished_at = time.time()
                    last.detail = str(exc)[:300]
                    yield self._event(last)
            yield {"type": "error", "run_id": self.run_id, "message": str(exc)[:500]}
        finally:
            await self.research.close()


def _candidate_names(original: str, category: str) -> list[str]:
    """Propose replacement candidates for a flagged reference.

    Deliberately mechanical. The point is not to be clever, it is to generate
    plausible same-register candidates that then get verified against live
    search before the report is allowed to recommend them.
    """
    parts = original.split()
    if category == "person_name" and len(parts) >= 2:
        first, last = parts[0], parts[-1]
        return [f"{first} Braddock", f"{first} Ellsworth", f"Dalton {last}"][:3]
    if category == "business":
        stem = " ".join(parts[:-1]) if len(parts) > 1 else original
        return [f"{stem} Mutual", f"{stem} Trust", f"Harrow {parts[-1]}"][:3]
    return []


def _unreviewed_finding(entity_id: str):
    from app.schemas.production import ClearanceFinding, RiskLevel

    return ClearanceFinding(
        entity_id=entity_id,
        risk=RiskLevel.AMBER,
        rationale=(
            "Not researched in this run. The live-search budget was reached before this "
            "reference was reached, so it is reported as unreviewed rather than cleared."
        ),
        searched=False,
    )
