"""Greenlight HTTP API.

One endpoint does the real work. It streams server-sent events so the client
sees each crew member start and finish rather than waiting on a single opaque
request, which for a feature-length script would be minutes long.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.crew import CREW_ROLES
from app.core.config import get_settings
from app.pipeline import PipelineRun

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"

app = FastAPI(
    title="Greenlight",
    description="A production office that reads a screenplay and returns a pre-production package.",
    version="0.1.0",
)

settings = get_settings()

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


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream(text: str, filename: str, setting: str) -> AsyncIterator[str]:
    run = PipelineRun(raw_text=text, filename=filename, setting=setting)
    async for event in run.run():
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
        _stream(payload.text, payload.filename, payload.setting),
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
