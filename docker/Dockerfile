# syntax=docker/dockerfile:1.7
#
# Headless StarCraft II (Linux build) + Python environment for the project.
# Building this image downloads the game from Blizzard, which means accepting the
# AI and Machine Learning License (see docker/install_sc2.sh).
#
# Sources are NOT copied into the image: the repository is bind-mounted at /workspace
# (see compose.yaml), so code changes do not require a rebuild. Rebuild only when
# pyproject.toml / uv.lock change.

ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim

ARG SC2_VERSION=4.10
# Checksum recorded from the first download of SC2.4.10.zip (Blizzard publishes none).
# The build fails if the archive ever differs. Pass an empty value to skip the check
# when building another SC2_VERSION.
ARG SC2_SHA256="1052f249f30a242bf5e17cc3315324919f9689307ca6dbcdb30bb41ea3004884"
ARG MAP_PACKS="Melee Ladder2019Season3"

RUN apt-get update \
    && apt-get install --assume-yes --no-install-recommends ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*

# --- StarCraft II (large layer, changes only when SC2_VERSION / MAP_PACKS change) ---
COPY docker/install_sc2.sh /usr/local/bin/install_sc2.sh
RUN --mount=type=cache,target=/var/cache/sc2 \
    bash /usr/local/bin/install_sc2.sh

# --- Python dependencies ---
# The virtual environment lives outside /workspace so the bind mount (which may contain
# a Windows .venv) cannot shadow it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:${PATH}" \
    SC2PATH=/root/StarCraftII \
    PYTHONPATH=/workspace/src \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

CMD ["python", "-m", "scbot.doctor"]
