"""First AD HTTP API.

One endpoint does the real work. It streams server-sent events so the client
sees each crew member start and finish rather than waiting on a single opaque
request, which for a feature-length script would be minutes long.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.agents.crew import CREW_ROLES
from app.core.config import get_settings
from app.core.exports import EXPORTS
from app.core.pdf import PDF_DOCUMENTS
from app.core.store import RunStore
from app.pipeline import PipelineRun

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"
RECORDED_RUN = SAMPLES_DIR / "recorded-run.json"

app = FastAPI(
    title="First AD",
    description="A production office that reads a screenplay and returns a pre-production package.",
    version="0.1.0",
)

settings = get_settings()
store = RunStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyseRequest(BaseModel):
    text: str = Field(min_length=40, description="Raw screenplay text")
    filename: str = "untitled.fountain"
    setting: str = Field(default="Chicago, Illinois", description="Where the production intends to shoot")
    start_date: date | None = Field(
        default=None,
        description="First day of principal photography. Defaults to the Monday after next.",
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream(
    text: str, filename: str, setting: str, start_date: date | None = None
) -> AsyncIterator[str]:
    run = PipelineRun(
        raw_text=text, filename=filename, setting=setting, start_date=start_date
    )

    async for event in run.run():
        # A finished package is persisted before it is streamed, so the client
        # already has a permalink by the time it renders the result. A storage
        # failure must not lose the run the user just waited two minutes for.
        if event.get("type") == "complete":
            try:
                store.save(
                    event["package"],
                    searches=int(event.get("searches_run") or 0),
                    setting=setting,
                )
                event["saved"] = True
            except Exception:  # noqa: BLE001 - the run itself still succeeded
                log.exception("could not persist run")
                event["saved"] = False

        yield _sse(event)

    yield "data: [DONE]\n\n"


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Stops nginx and friends from buffering the stream into uselessness.
    "X-Accel-Buffering": "no",
}


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "gemini_configured": settings.has_gemini,
        "gemini_backend": "vertex-ai" if settings.google_genai_use_vertexai else "api-key",
        "parallel_configured": settings.has_parallel,
        "models": {"reasoning": settings.model_reasoning, "fast": settings.model_fast},
    }


@app.get("/api/crew")
async def crew() -> dict:
    """The roster, so the UI can show the network before a run starts."""
    order = [
        ("script", "script_supervisor", "Parses sluglines, measures pages, writes strip synopses"),
        ("breakdown", "breakdown_agent", "Tags every element a department has to supply"),
        ("clearance_extract", "clearance_extractor", "Finds every reference needing legal clearance"),
        ("locations", "locations_agent", "Researches permits, fees, and hazards per set"),
        ("clearance_risk", "risk_scorer", "Grades each reference against live search evidence"),
        ("schedule", "scheduler_agent", "Builds the stripboard and day-out-of-days"),
        ("compliance", "compliance_agent", "Checks turnaround, minors, meals, and safety"),
        ("budget", "line_producer", "Builds the budget top sheet"),
        ("call_sheets", "call_sheet_agent", "Cuts a call sheet per shooting day"),
    ]
    return {
        "crew": [
            {
                "stage": stage,
                "agent": agent,
                "crew_role": CREW_ROLES[agent],
                "does": does,
                "grounded": agent in ("locations_agent", "risk_scorer"),
            }
            for stage, agent, does in order
        ]
    }


@app.get("/api/sample")
async def sample() -> dict:
    path = SAMPLES_DIR / "the-projectionist.fountain"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample screenplay is missing.")
    return {
        "filename": path.name,
        "setting": "Chicago, Illinois",
        "text": path.read_text(encoding="utf-8"),
    }


@app.post("/api/analyse")
async def analyse(payload: AnalyseRequest) -> StreamingResponse:
    _require_config()
    return StreamingResponse(
        _stream(payload.text, payload.filename, payload.setting, payload.start_date),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/analyse/upload")
async def analyse_upload(
    file: UploadFile = File(...),
    setting: str = Form("Chicago, Illinois"),
) -> StreamingResponse:
    _require_config()

    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Script exceeds {settings.max_upload_mb} MB.")

    filename = file.filename or "untitled.fountain"

    if filename.lower().endswith(".pdf"):
        text = _extract_pdf(raw)
    else:
        text = raw.decode("utf-8", errors="replace")

    if len(text.strip()) < 40:
        raise HTTPException(status_code=422, detail="That file contains no readable screenplay text.")

    return StreamingResponse(
        _stream(text, filename, setting),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/api/runs")
async def list_runs(limit: int = 25) -> dict:
    """Every package this instance has produced, newest first."""
    return {"runs": [s.as_dict() for s in store.list(limit=max(1, min(limit, 100)))]}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    try:
        document = store.get(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="No such run.")
    return document


@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str) -> dict:
    try:
        removed = store.delete(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="No such run.")
    return {"deleted": run_id}


@app.get("/api/demo")
async def demo() -> dict:
    """A previously captured run, bundled with the repository.

    This exists so the product can be evaluated without anyone holding API
    keys. It is a real pipeline output that was recorded to disk, not a
    simulation, and it is flagged `recorded` so the UI can say so plainly
    rather than passing it off as a live result.
    """
    if not RECORDED_RUN.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "No recorded run is bundled. Run a script with keys configured, then "
                "POST /api/runs/{run_id}/promote to capture it as the demo."
            ),
        )
    try:
        document = json.loads(RECORDED_RUN.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Recorded run is corrupt: {exc}") from exc

    document["recorded"] = True
    return document


@app.get("/api/runs/{run_id}/export/{document}.csv")
async def export_run(run_id: str, document: str) -> Response:
    """One document out of a stored run, as a spreadsheet.

    A production office moves these as CSV, so the columns are named the way
    scheduling software and clearance firms already label them and a row can be
    pasted into an existing sheet without re-labelling.
    """
    builder = EXPORTS.get(document)
    if builder is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown document. Available: {', '.join(sorted(EXPORTS))}.",
        )

    stored = _load_run_or_demo(run_id)
    package = stored.get("package") or {}

    title = ((package.get("script") or {}).get("header") or {}).get("title") or "firstad"
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-") or "firstad"

    return Response(
        # A BOM is what makes Excel open UTF-8 CSV without mangling accents.
        content="﻿" + builder(package),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}-{document}.csv"'},
    )


@app.get("/api/runs/{run_id}/export/{document}.pdf")
async def export_run_pdf(run_id: str, document: str) -> Response:
    """A call sheet or a clearance report, as the document people distribute.

    These two are handed out rather than edited: a call sheet goes to the whole
    unit the night before, a clearance report goes to the insurer. Everything
    else exports as CSV because it belongs in a spreadsheet.
    """
    builder = PDF_DOCUMENTS.get(document)
    if builder is None:
        raise HTTPException(
            status_code=404,
            detail=f"No PDF for that document. Available: {', '.join(sorted(PDF_DOCUMENTS))}.",
        )

    stored = _load_run_or_demo(run_id)
    package = stored.get("package") or {}

    title = ((package.get("script") or {}).get("header") or {}).get("title") or "firstad"
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-") or "firstad"

    return Response(
        content=builder(package),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{slug}-{document}.pdf"'},
    )


@app.get("/api/runs/{run_id}/export.json")
async def export_run_json(run_id: str) -> Response:
    """The whole package, for anyone who would rather have the structured data."""
    stored = _load_run_or_demo(run_id)
    title = (((stored.get("package") or {}).get("script") or {}).get("header") or {}).get(
        "title"
    ) or "firstad"
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-") or "firstad"

    return Response(
        content=json.dumps(stored, ensure_ascii=False, indent=1),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{slug}-package.json"'},
    )


def _load_run_or_demo(run_id: str) -> dict:
    """Resolve a run id, accepting the literal id `demo` for the bundled run."""
    if run_id == "demo":
        if not RECORDED_RUN.exists():
            raise HTTPException(status_code=404, detail="No recorded run is bundled.")
        return json.loads(RECORDED_RUN.read_text(encoding="utf-8"))

    try:
        document = store.get(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="No such run.")
    return document


@app.post("/api/runs/{run_id}/promote")
async def promote_run(run_id: str) -> dict:
    """Capture a stored run as the bundled demo.

    Keeping this an explicit action means the shipped demo is always a real
    result somebody chose, rather than a fixture that drifts away from what the
    pipeline actually produces.
    """
    try:
        document = store.get(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="No such run.")

    document["recorded"] = True
    RECORDED_RUN.parent.mkdir(parents=True, exist_ok=True)
    RECORDED_RUN.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"promoted": run_id, "path": str(RECORDED_RUN)}


def _extract_pdf(raw: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not read that PDF: {exc}") from exc


def _require_config() -> None:
    if not settings.has_gemini:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini is not configured. Set GOOGLE_API_KEY, or set "
                "GOOGLE_GENAI_USE_VERTEXAI=TRUE with GOOGLE_CLOUD_PROJECT."
            ),
        )
