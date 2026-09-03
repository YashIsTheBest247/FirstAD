"""Run persistence.

A finished production package is the thing the user actually wanted, and losing
it on a page refresh after a two minute run is indefensible. Runs are written to
disk as JSON, listed newest first, and fetchable by id so the UI can hand out a
permalink.

Deliberately a directory of files rather than a database. A run is a single
immutable document, there are no queries beyond "list" and "get by id", and a
filesystem gives the deployment one less moving part.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings

log = logging.getLogger(__name__)

SAFE_ID = re.compile(r"^[a-z0-9]{4,40}$")


@dataclass(frozen=True)
class RunSummary:
    """Enough to render a list row without loading the whole package."""

    run_id: str
    title: str
    saved_at: str
    scene_count: int
    page_count: float
    shoot_days: int
    red_flags: int
    searches: int
    recorded: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "title": self.title,
            "saved_at": self.saved_at,
            "scene_count": self.scene_count,
            "page_count": self.page_count,
            "shoot_days": self.shoot_days,
            "red_flags": self.red_flags,
            "searches": self.searches,
            "recorded": self.recorded,
        }


class RunStore:
    def __init__(self, directory: str | None = None) -> None:
        settings = get_settings()
        base = Path(directory or settings.run_store_dir)
        # Resolve relative to the service root, not the process working
        # directory, so it does not matter where uvicorn was launched from.
        self.dir = base if base.is_absolute() else Path(__file__).resolve().parents[2] / base
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        if not SAFE_ID.match(run_id):
            raise ValueError(f"Refusing to touch an unsafe run id: {run_id!r}")
        return self.dir / f"{run_id}.json"

    def save(self, package: dict[str, Any], *, searches: int, setting: str) -> str:
        """Persist a finished package and return its id."""
        run_id = str(package.get("run_id") or "")
        path = self._path(run_id)

        document = {
            "run_id": run_id,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "setting": setting,
            "searches": searches,
            "recorded": False,
            "package": package,
        }
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        log.info("saved run %s to %s", run_id, path)
        return run_id

    def get(self, run_id: str) -> dict[str, Any] | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.exception("could not read run %s", run_id)
            return None

    def delete(self, run_id: str) -> bool:
        path = self._path(run_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list(self, limit: int = 25) -> list[RunSummary]:
        """Newest first, skipping anything unreadable rather than failing."""
        summaries: list[tuple[float, RunSummary]] = []

        for path in self.dir.glob("*.json"):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            summary = summarise(document)
            if summary is None:
                continue
            summaries.append((path.stat().st_mtime, summary))

        summaries.sort(key=lambda pair: pair[0], reverse=True)
        return [s for _, s in summaries[:limit]]


def summarise(document: dict[str, Any]) -> RunSummary | None:
    """Reduce a stored document to a list row."""
    package = document.get("package") or {}
    header = (package.get("script") or {}).get("header") or {}
    board = package.get("stripboard") or {}
    findings = (package.get("clearance") or {}).get("findings") or []

    run_id = document.get("run_id") or package.get("run_id")
    if not run_id:
        return None

    return RunSummary(
        run_id=str(run_id),
        title=str(header.get("title") or "Untitled"),
        saved_at=str(document.get("saved_at") or ""),
        scene_count=int(header.get("scene_count") or 0),
        page_count=float(header.get("page_count") or 0),
        shoot_days=int(board.get("shoot_day_count") or 0),
        red_flags=sum(1 for f in findings if f.get("risk") == "red"),
        searches=int(document.get("searches") or 0),
        recorded=bool(document.get("recorded")),
    )
