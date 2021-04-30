FROM python:3.7 AS build

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
COPY . /app/

# Build wheel.
RUN bash -c "poetry install && poetry build -f wheel && poetry export --without-hashes -o requirements.txt --dev"

WORKDIR /wheels
RUN bash -c "cp /app/dist/* /wheels/ && cp /app/requirements.txt /wheels/ && rm -rf /app"



FROM pymesh/pymesh:py3.7 AS app-apt

# Blender deps + openscad
RUN apt-get update && \
	apt-get install -y --no-install-recommends \
		curl \
		libfreetype6 \
		libglu1-mesa \
		libxi6 \
		libxrender1 \
		openscad \
		xz-utils && \
	apt-get -y autoremove && \
	rm -rf /var/lib/apt/lists/*


FROM app-apt AS app-blender

# Install blender.
ENV BLENDER_MAJOR 2.92
ENV BLENDER_VERSION 2.92.0
ENV BLENDER_URL https://download.blender.org/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-linux64.tar.xz
RUN curl -L ${BLENDER_URL} | tar -xJ -C /usr/local/ && \
	mv /usr/local/blender-${BLENDER_VERSION}-linux64 /usr/local/blender


FROM app-blender AS app

# Install dependencies from wheels
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir -f /wheels/ -r /wheels/requirements.txt \
  && rm -rf /wheels

WORKDIR /app/
COPY . /app/

RUN pip install --no-cache-dir -e /app/
ENTRYPOINT /bin/bash
