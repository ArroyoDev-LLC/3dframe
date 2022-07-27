# syntax=docker/dockerfile:1
ARG PYTHON_BASE_TAG="3.9.13-bullseye"
ARG DEBIAN_BASE_TAG="bullseye-20220711-slim"
#################
## Python Base
################
FROM python:${PYTHON_BASE_TAG} AS python-base

ARG APP_NAME=threedframe
ARG APP_PATH=/app/$APP_NAME

ARG PYTHON_VERSION=3.9.13
ARG POETRY_VERSION=1.2.0b3

# Python Env
ENV PYTHONFAULTHANDLER=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

ARG DATA_DIR=/data \
    RENDERS_DIR=${DATA_DIR}/renders
ARG MODELS_DIR=${DATA_DIR}/models

ENV DATA_DIR=${DATA_DIR} \
    RENDERS_DIR=${RENDERS_DIR} \
    MODELS_DIR=${MODELS_DIR}

# Poetry Env
ENV POETRY_VERSION=${POETRY_VERSION} \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    POETRY_HOME=${DATA_DIR}/poetry

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python -
ENV PATH="${DATA_DIR}/poetry/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        xorg-dev \
        libglu1-mesa-dev \
        libosmesa6-dev \
        # openscad runtime.
        libboost-all-dev \
        libdouble-conversion3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app
COPY pyproject.toml poetry.lock ./


#################
## Debian Base
################
FROM debian:${DEBIAN_BASE_TAG} AS debian-base

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        xz-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


#################
## OpenScad
################
FROM debian-base as openscad

ARG OPENSCAD_REPO="https://github.com/openscad/openscad.git"
ARG OPENSCAD_REV="openscad-2021.01"

RUN git clone --branch=${OPENSCAD_REV} ${OPENSCAD_REPO} /openscad \
    && git -C /openscad submodule update --init
WORKDIR /openscad

RUN apt-get update \
    && ./scripts/uni-get-dependencies.sh \
    && ./scripts/check-dependencies.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir build
WORKDIR /openscad/build

RUN cmake .. -DEXPERIMENTAL=1 \
    && make -j


#################
## Blender
################
FROM debian-base as blender

ARG BLENDER_MAJOR=2.92 \
    BLENDER_VERSION=2.92.0 \
    BLENDER_ARCH=linux64

ENV BLENDER_URL=https://download.blender.org/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-${BLENDER_ARCH}.tar.xz \
    BLENDER_ARCHIVE_DIR=/blender-archive/${BLENDER_VERSION}-${BLENDER_ARCH}

# Install blender.
RUN --mount=type=cache,id=blender-archive,target=/blender-archive \
    mkdir -p ${BLENDER_ARCHIVE_DIR} \
    && curl -L -o ${BLENDER_ARCHIVE_DIR}/blender.tar.xz ${BLENDER_URL} \
    && tar -xf ${BLENDER_ARCHIVE_DIR}/blender.tar.xz -C /usr/local/ \
    && ln -s /usr/local/blender-${BLENDER_VERSION}-${BLENDER_ARCH} /blender


#################
## App Base
################
FROM python-base as base
COPY --from=openscad /openscad/scripts/uni-get-dependencies.sh /get-oscad-deps.sh
RUN apt-get update \
    && /get-oscad-deps.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm /get-oscad-deps.sh


#################
## Workspace
################
FROM base as workspace

ARG USER_UID=1000
ARG USER_GID=1000
ARG USER_NAME=threedframe

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Setup threedframe user.
RUN groupadd --gid $USER_GID --system ${USER_NAME} \
    && useradd --uid ${USER_UID} --system --gid ${USER_GID} --home-dir ${DATA_DIR} ${USER_NAME} \
    && mkdir -p ${RENDERS_DIR} ${MODELS_DIR} \
    && chown -R ${USER_UID}:${USER_GID} ${DATA_DIR} /app

USER threedframe

RUN ${POETRY_HOME}/bin/poetry install --no-root

# Copy OpenSCAD & Blender binaries
COPY --from=openscad /openscad/build/openscad /usr/local/bin/openscad
COPY --from=blender /blender /usr/local/blender

COPY . .

RUN ${POETRY_HOME}/bin/poetry install --only-root

COPY ./scripts/docker-entrypoint.sh /docker-entrypoint.sh
VOLUME [ $APP_PATH $RENDERS_DIR $MODELS_DIR ]
ENTRYPOINT [ "/docker-entrypoint.sh", "poetry", "run", "threedframe/cli.py" ]
CMD ["--help"]


#################
## Test Runner
################
FROM workspace as test-runner
RUN ${POETRY_HOME}/bin/poetry install --with=test
ENTRYPOINT [ "/docker-entrypoint.sh", "poetry", "run" ]
CMD ["pytest"]
