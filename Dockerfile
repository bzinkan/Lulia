# syntax=docker/dockerfile:1.7
#
# Lulia API Dockerfile — multi-stage, non-root, pinned base.
#
# Why multi-stage:
#   The runtime image doesn't need pip, build toolchains, or header files
#   (libpq-dev, gcc, etc.). We install Python deps into a virtualenv inside
#   a builder stage, then COPY just that venv into a slim runtime stage.
#   Net effect: smaller image (~250 MB → ~180 MB) and a smaller attack
#   surface.
#
# Why non-root:
#   If a process compromise ever happens inside the container, running as
#   `appuser` instead of root is one more barrier before a malicious actor
#   can chmod or chroot their way out. ECS/Fargate also prefer non-root
#   containers (IAM task-role policies assume least-privilege).
#
# Base pin:
#   `python:3.12.7-slim-bookworm` is tagged by specific patch + OS release
#   so rebuilds are reproducible week-to-week. The published tag is
#   immutable per SemVer patch. For a stricter posture, swap to `@sha256:…`
#   once the prod base digest is captured via `docker inspect`.

# ---------------------------------------------------------------------------
# Stage 1: builder — install Python deps into an isolated virtualenv
# ---------------------------------------------------------------------------
FROM python:3.12.7-slim-bookworm AS builder

# Headers needed for building any pure-Python-fallback wheels. Most of our
# deps ship wheels, but cryptography / psycopg2-binary still benefit from
# having libpq-dev + build-essential available so pip doesn't have to pick
# a sub-optimal install path.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
      && rm -rf /var/lib/apt/lists/*

# Dedicated venv at /opt/venv so the runtime stage can copy one directory
# and be confident it has everything.
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install deps first, then source — the usual trick to keep the layer
# cache honest: editing a router file shouldn't re-run pip.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt


# ---------------------------------------------------------------------------
# Stage 2: runtime — slim image, non-root user, copy the venv in
# ---------------------------------------------------------------------------
FROM python:3.12.7-slim-bookworm AS runtime

# Runtime apt deps only:
#   - libpq5    : the psycopg2 shared lib at runtime
#   - ffmpeg    : video pipeline (slide+TTS composition)
#   - fonts-*   : worksheet/slide rendering
#   - curl      : used by HEALTHCHECK below. Tiny, worth the 1 MB.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 \
      ffmpeg \
      fonts-liberation \
      curl \
      && rm -rf /var/lib/apt/lists/*

# Non-root user. System-account range, no login shell.
ARG APP_UID=10001
ARG APP_GID=10001
RUN groupadd --system --gid "$APP_GID" appuser \
    && useradd --system --uid "$APP_UID" --gid "$APP_GID" \
       --home-dir /app --shell /usr/sbin/nologin appuser

# Pull the venv from the builder. It's self-contained, so no pip needed
# in the runtime image.
ENV VIRTUAL_ENV=/opt/venv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
# Help Python play nicely with Docker: unbuffered stdout for CloudWatch,
# no .pyc files in the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy source. Chown at copy-time so we don't need a separate RUN chown
# layer (that would double the image size of the app code).
#
# Note: `data/` is deliberately NOT copied in. Locally it's bind-mounted
# via compose (state_standards is empty, content is 17 GB of OER data),
# and in prod the content lives in S3. Anything the API truly needs at
# startup is either in the DB or behind an S3 fetch, not in the image.
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser alembic.ini ./alembic.ini
COPY --chown=appuser:appuser alembic/ ./alembic/

USER appuser

EXPOSE 8000

# ECS/Fargate uses its own target-group probes, but HEALTHCHECK also helps
# `docker ps` and any developer-facing tools (e.g. Portainer) show the
# right state during local runs. Hits the liveness probe; `/ready` is a
# deeper check we keep for the ALB.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl --fail --silent --show-error http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.lms_agents.main:app", "--host", "0.0.0.0", "--port", "8000"]
