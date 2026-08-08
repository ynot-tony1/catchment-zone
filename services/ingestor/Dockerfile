# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder stage: install dependencies into a virtual environment using the
# lockfile-pinned versions in pyproject.toml, without leaving build tools in
# the final image.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip \
    && pip install .

# ---------------------------------------------------------------------------
# Runtime stage: slim image, non-root user, only the built virtual
# environment and application source are copied in.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# libpq is required at runtime by psycopg's binary wheel dependencies for TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system ingestor \
    && useradd --system --gid ingestor --home-dir /app --shell /usr/sbin/nologin ingestor

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
USER ingestor

# The config/ registries (catchment-sources.yml, statistics-sources.yml,
# metric-definitions.yml) live at the monorepo root, outside this image's
# build context (services/ingestor), so they are not baked into the image.
# Provide them at container run time with a bind mount, for example:
#   docker run -v "$(pwd)/config:/app/config:ro" ... catchment-zone-ingestor import-gias
# or set CONFIG_DIR (see config.py) to wherever the registries are mounted
# if not at the default ./config relative to the working directory.

ENTRYPOINT ["ingestor"]
CMD ["--help"]
