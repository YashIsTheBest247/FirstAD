# First AD API, built for Cloud Run.
#
# Build from the REPOSITORY ROOT, not from this directory:
#
#   docker build -f services/api/Dockerfile -t firstad-api .
#
# The API resolves the sample screenplay and any bundled recorded run relative
# to the repository layout (app/../../../samples), so the image reproduces that
# shape rather than special-casing the container.
#
# Two stages, so the runtime image carries no build toolchain, and a non-root
# user because Cloud Run would otherwise happily run this as root.

FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY services/api/requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r /tmp/requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080

COPY --from=build /opt/venv /opt/venv

WORKDIR /srv

# Mirrors the repo layout: /srv/samples sits three levels above the app package.
COPY samples ./samples
COPY services/api/app ./services/api/app

RUN useradd --create-home --uid 10001 firstad \
    && mkdir -p /srv/services/api/.runs \
    && chown -R firstad:firstad /srv
USER firstad

WORKDIR /srv/services/api

EXPOSE 8080

# Single worker on purpose. A run holds in-process state for its duration, and
# Cloud Run scales by adding instances rather than threads.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1
