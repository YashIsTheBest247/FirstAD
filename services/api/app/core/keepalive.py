"""Stops the service being put to sleep for idleness.

A free Render instance sleeps after fifteen minutes without an inbound
request, and takes about a minute to come back. That cold start is the first
thing a visitor meets, so it is worth avoiding.

The browser already polls `/api/health` every twelve minutes, but that only
helps while somebody has the page open. This closes the rest of the gap by
having the service call its own public URL on a timer. The request leaves the
container, reaches the load balancer, and counts as inbound traffic, which is
what the idle timer actually watches.

The honest limit: this keeps a running instance running. It cannot wake one
that has already stopped, because there is no process left to run the timer.
Waking from cold needs a request from outside, which is what the scheduled
GitHub workflow in `.github/workflows/keepalive.yml` is for. The two together
cover both cases.

Enabled only when the platform tells us our own public URL, so local
development and test runs never ping anything.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

log = logging.getLogger(__name__)

# Comfortably inside the fifteen minute idle window, with room for a couple of
# missed beats before the platform would consider the service idle.
INTERVAL_SECONDS = 10 * 60

# Render publishes this automatically. Its presence is also how we know we are
# running on a platform that sleeps.
URL_ENV_VARS = ("RENDER_EXTERNAL_URL", "PUBLIC_BASE_URL")


def public_url() -> str | None:
    for name in URL_ENV_VARS:
        value = os.environ.get(name, "").strip().rstrip("/")
        if value:
            return value
    return None


async def _beat(client: httpx.AsyncClient, url: str) -> None:
    try:
        response = await client.get(f"{url}/api/health")
        log.debug("keepalive ping -> %s", response.status_code)
    except Exception as exc:  # noqa: BLE001 - a failed ping must never kill the task
        # Worth a warning rather than silence: if this starts failing, cold
        # starts come back and nobody would otherwise know why.
        log.warning("keepalive ping failed: %s", exc)


async def keepalive_loop() -> None:
    """Ping our own public URL forever, on a fixed interval."""
    url = public_url()
    if not url:
        log.info("keepalive disabled: no public URL in the environment")
        return

    log.info("keepalive enabled: pinging %s every %ss", url, INTERVAL_SECONDS)

    # A short timeout on purpose. This is a liveness beat, not a request whose
    # answer anyone is waiting for, so it should never pile up.
    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            await asyncio.sleep(INTERVAL_SECONDS)
            await _beat(client, url)
