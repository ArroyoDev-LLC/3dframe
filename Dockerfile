FROM python:3.8 AS build

# Python Envs
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Install Poetry
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | POETRY_HOME=/opt/poetry python && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

WORKDIR /app/
COPY pyproject.toml poetry.lock /app/

# Build wheel.
RUN bash -c "poetry export --without-hashes -o requirements.txt --dev && pip install -U pip && mkdir -p dist && pip wheel -w dist -r requirements.txt"


WORKDIR /wheels
RUN bash -c "cp /app/dist/* /wheels/ && cp /app/requirements.txt /wheels/ && rm -rf /app"


### Base sys-library dependencies.
FROM python:3.8-buster as deps

ARG NUM_CORES=4
ENV NUMCPU $NUM_CORES

# Pymesh + OpenSCAD + Blender deps
RUN curl -L -o /get-oscad-deps.sh https://raw.githubusercontent.com/openscad/openscad/openscad-2021.01/scripts/uni-get-dependencies.sh \
    && curl -L -o /check-oscad-deps.sh https://raw.githubusercontent.com/openscad/openscad/openscad-2021.01/scripts/check-dependencies.sh \
    && chmod +x /get-oscad-deps.sh && chmod +x /check-oscad-deps.sh \
    && apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        git \
        cmake \
        libgmp-dev \
        libmpfr-dev \
        libgmpxx4ldbl \
        libboost-dev \
        libboost-thread-dev \
        zip unzip patchelf \
        # Blender specific
        curl \
        libfreetype6 \
        libglu1-mesa \
        libxi6 \
        libxrender1 \
        xz-utils \
        # OpenSCAD specific
        libunistring-dev \
        libglib2.0 \
        libharfbuzz-dev \
     && /get-oscad-deps.sh \
     && /check-oscad-deps.sh \
     && apt-get clean \
     && rm -rf /var/lib/apt/lists/*


### Compile OpenSCAD
FROM deps as openscad

ARG NUM_CORES=4
ENV NUMCPU $NUM_CORES

RUN git clone --branch openscad-2021.01 https://github.com/openscad/openscad.git /openscad-src \
    && cd /openscad-src \
    && git submodule update --init \
    && ./scripts/check-dependencies.sh \
    && qmake openscad.pro \
    && make --jobs="${NUMCPU}" \
    && cp ./openscad /openscad \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /openscad-src


### Download Blender.
FROM deps as blender

# Install blender.
ENV BLENDER_MAJOR 2.92
ENV BLENDER_VERSION 2.92.0
ENV BLENDER_URL https://download.blender.org/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-linux64.tar.xz
RUN curl -L ${BLENDER_URL} | tar -xJ -C /usr/local/ && \
	mv /usr/local/blender-${BLENDER_VERSION}-linux64 /blender


### Compile Pymesh
FROM deps as pymesh

WORKDIR /root/
ARG BRANCH="main"
ARG NUM_CORES=4

RUN git clone --single-branch -b $BRANCH https://github.com/PyMesh/PyMesh.git

ENV PYMESH_PATH /root/PyMesh
ENV NUM_CORES $NUM_CORES
ENV NUMCPU $NUM_CORES
WORKDIR $PYMESH_PATH

RUN git submodule update --init && \
    pip install -r $PYMESH_PATH/python/requirements.txt && \
    ./setup.py bdist_wheel && \
    rm -rf build_3.7 third_party/build && \
    python $PYMESH_PATH/docker/patches/patch_wheel.py dist/pymesh2*.whl && \
    pip install dist/pymesh2*.whl && \
    python -c "import pymesh; pymesh.test()"


### 3dframe App
FROM pymesh AS app


# Copy OpenSCAD & Blender binaries
COPY --from=openscad /openscad /usr/local/bin/openscad
COPY --from=blender /blender /usr/local/blender

# Copy dependencies.
COPY --from=build /wheels /wheels


ENV UID 1000

# Container user.
# Create User
RUN useradd \
  --non-unique \
  --no-create-home \
  --no-user-group \
  --home-dir /app \
  --uid ${UID:-1000} \
  threedframe \
  # Install dependencies from wheels
  && pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir -f /wheels/ -r /wheels/requirements.txt \
  && rm -rf /wheels

# Install needed fonts.
RUN cd /usr/share/fonts/truetype \
 && curl -o opensans.zip -L https://fonts.google.com/download?family=Open%20Sans \
 && unzip -d opensans opensans.zip \
 && rm opensans.zip \
 && fc-cache -f -v


WORKDIR /app/
COPY . /app/

RUN pip install --no-cache-dir -e /app/ \
  && mkdir -p /app/renders \
  && chown -R threedframe: /app \
  && chmod -R u+rwx /app \
  && mkdir -p /app/.local/share/expSolidPython \
  && chown -R threedframe /app/.local \
  && chmod -R a+rwx /app/.local


ENTRYPOINT /bin/bash
CMD ['3dframe']
