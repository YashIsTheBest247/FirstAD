"""Parallel Search API integration.

Two stages of the pipeline are only possible with live, citable web research:

  Locations agent   - what a real permit costs in a real jurisdiction
  Clearance crew    - whether a name in the script collides with a real person

Neither can be answered from model weights. A model asked "is there a real
Chicago alderman named Grant Holloway" will confabulate with total confidence,
and a clearance report built on that is worse than no report at all. So every
risk verdict in Greenlight is anchored to a URL a production lawyer can open.

Search fan-out is bounded by a semaphore and memoised per run, because a
feature script produces hundreds of clearable entities and each one is a
billable call.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field

from parallel import AsyncParallel

from app.core.config import get_settings
from app.schemas.production import Citation

log = logging.getLogger(__name__)

# Search modes, mapped to how much the answer is worth.
MODE_DEEP = "advanced"   # clearance verdicts and permit costs
MODE_QUICK = "basic"     # cheap disambiguation passes


@dataclass
class SearchOutcome:
    """What a single search returned, in the shape the agents consume."""

    objective: str
    queries: list[str]
    citations: list[Citation] = field(default_factory=list)
    evidence: str = ""
    error: str | None = None

    @property
    def found_anything(self) -> bool:
        return bool(self.citations)


class ParallelResearch:
    """Bounded, memoised access to the Parallel Search API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = settings.has_parallel
        self._semaphore = asyncio.Semaphore(settings.parallel_max_concurrency)
        self._cache: dict[str, SearchOutcome] = {}
        self._client: AsyncParallel | None = None
        self.call_count = 0

        if self._enabled:
            self._client = AsyncParallel(api_key=settings.parallel_api_key)
        else:
            log.warning("PARALLEL_API_KEY is not set. Research stages will run unsourced.")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def _key(objective: str, queries: list[str], mode: str) -> str:
        blob = "|".join([objective, mode, *sorted(queries)])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]

    async def search(
        self,
        objective: str,
        queries: list[str],
        *,
        mode: str = MODE_DEEP,
        max_chars: int = 6000,
        max_citations: int = 6,
    ) -> SearchOutcome:
        """Run one grounded search and flatten it into citations plus evidence text."""
        if not self._enabled or self._client is None:
            return SearchOutcome(
                objective=objective,
                queries=queries,
                error="Parallel Search is not configured. Set PARALLEL_API_KEY.",
            )

        cache_key = self._key(objective, queries, mode)
        if cache_key in self._cache:
            return self._cache[cache_key]

        settings = get_settings()

        async with self._semaphore:
            try:
                result = await self._client.search(
                    objective=objective,
                    search_queries=queries[:5],
                    mode=mode,
                    max_chars_total=max_chars,
                    # Telling Parallel which model consumes the excerpts lets it
                    # tune compression and result shaping for Gemini.
                    client_model=settings.model_reasoning,
                )
                self.call_count += 1
            except Exception as exc:  # noqa: BLE001 - a failed search must not kill the run
                log.exception("Parallel search failed for objective %r", objective)
                outcome = SearchOutcome(
                    objective=objective, queries=queries, error=f"{type(exc).__name__}: {exc}"
                )
                self._cache[cache_key] = outcome
                return outcome

        citations: list[Citation] = []
        evidence_parts: list[str] = []

        for hit in (result.results or [])[:max_citations]:
            excerpt = " ".join(hit.excerpts or [])[:900].strip()
            citations.append(
                Citation(
                    url=hit.url,
                    title=(hit.title or hit.url)[:200],
                    excerpt=excerpt,
                )
            )
            if excerpt:
                evidence_parts.append(f"[{hit.title or hit.url}] ({hit.url})\n{excerpt}")

        outcome = SearchOutcome(
            objective=objective,
            queries=queries,
            citations=citations,
            evidence="\n\n".join(evidence_parts),
        )
        self._cache[cache_key] = outcome
        return outcome

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


# --------------------------------------------------------------------------
# Purpose-built research briefs
#
# The query wording matters more than anything else in this file. These are
# written the way a clearance researcher actually searches: name plus role plus
# place, because a bare name match is not a legal risk but a name matching a
# real person in the same occupation and city is.
# --------------------------------------------------------------------------


async def research_clearance_entity(
    research: ParallelResearch,
    *,
    text: str,
    category: str,
    portrayal: str,
    setting_hint: str,
) -> SearchOutcome:
    """Ask whether a scripted reference collides with something real."""
    queries: list[str] = []

    if category == "person_name":
        queries = [
            f"{text} {setting_hint}",
            f'"{text}" {portrayal}',
            f'"{text}" news',
        ]
        objective = (
            f'Determine whether "{text}" is the name of a real, identifiable living person, '
            f"particularly one connected to {setting_hint} or to the role of {portrayal}. "
            "Report their occupation, location, and whether they are publicly known. "
            "If no notable real person carries this name, say so explicitly."
        )
    elif category == "business":
        queries = [f'"{text}" {setting_hint}', f'"{text}" company', f'"{text}" trademark']
        objective = (
            f'Determine whether "{text}" is the name of a real, operating business or a '
            f"registered trademark, especially near {setting_hint}. Report what it does and "
            "where it operates."
        )
    elif category == "address":
        queries = [f'"{text}"', f"{text} business listing", f"{text} property"]
        objective = (
            f'Identify what currently exists at the address "{text}". Report any named '
            "business, residence, or landmark at that address, since depicting a real "
            "occupied address creates a privacy exposure."
        )
    elif category == "organisation":
        queries = [f'"{text}" organisation', f'"{text}" {setting_hint}', f'"{text}" official']
        objective = (
            f'Determine whether "{text}" is a real organisation, agency, or body, and if so '
            "what it does and whether it is litigious about depiction."
        )
    elif category == "brand_product":
        queries = [f'"{text}" brand', f'"{text}" trademark class', f'"{text}" product']
        objective = (
            f'Determine whether "{text}" is an active trademark, who owns it, and whether the '
            "mark is still in commercial use."
        )
    elif category == "artwork_music":
        queries = [f'"{text}" copyright', f'"{text}" rights holder', f'"{text}" public domain']
        objective = (
            f'Determine the copyright status of "{text}", who controls the rights, and whether '
            "it has entered the public domain."
        )
    elif category == "real_event":
        queries = [f"{text}", f"{text} {setting_hint}", f"{text} controversy"]
        objective = (
            f'Establish whether the event described as "{text}" actually happened, when, and '
            "which identifiable real people were involved."
        )
    else:
        queries = [f'"{text}" {setting_hint}', f'"{text}"']
        objective = f'Determine whether "{text}" refers to something real and identifiable.'

    return await research.search(objective=objective, queries=queries, mode=MODE_DEEP)


async def research_location(
    research: ParallelResearch,
    *,
    location: str,
    setting_hint: str,
    is_exterior: bool,
) -> SearchOutcome:
    """Pull permit, cost, and hazard intelligence for one set."""
    kind = "exterior location" if is_exterior else "interior location"
    queries = [
        f"{setting_hint} film permit cost application",
        f"{setting_hint} filming permit lead time requirements",
        f"filming {location} {setting_hint} permit",
    ]
    objective = (
        f"A film production needs to shoot at a {kind} of the type '{location}' in or near "
        f"{setting_hint}. Report the permitting authority, the current permit fee, the required "
        "lead time in days, any insurance or police/fire officer requirements, and known "
        "restrictions such as street closures or night-shoot curfews."
    )
    return await research.search(objective=objective, queries=queries, mode=MODE_DEEP)


async def verify_alternative_is_clear(
    research: ParallelResearch, *, candidate: str, setting_hint: str
) -> bool:
    """Check that a proposed replacement name does not itself collide with anything.

    Suggesting an alternative without checking it just moves the liability, so a
    candidate is only offered when a live search comes back thin.
    """
    outcome = await research.search(
        objective=(
            f'Determine whether "{candidate}" is the name of a real notable person or business, '
            f"particularly in {setting_hint}."
        ),
        queries=[f'"{candidate}" {setting_hint}', f'"{candidate}"'],
        mode=MODE_QUICK,
        max_chars=2000,
        max_citations=3,
    )
    if outcome.error:
        return False
    # Treat a candidate as clear only when search finds essentially nothing on it.
    return len(outcome.citations) <= 1
