FROM python:3.14-slim-trixie
ARG APP_VERSION=0.2.0
ARG APP_REVISION=153
ARG BUILD_ID=unknown
ARG INSTALL_STEMS=true
LABEL org.opencontainers.image.title="MTA Audio Editor" \
      org.opencontainers.image.description="DAW-style editor for M-Audio/M-Live Merish MTA multitrack files" \
      org.opencontainers.image.source="https://github.com/desalvo/mta-audio-editor" \
      org.opencontainers.image.licenses="EUPL-1.2" \
      org.opencontainers.image.authors="Alessandro De Salvo <braket71@gmail.com>" \
      org.opencontainers.image.version="$APP_VERSION" \
      io.github.desalvo.mta-audio-editor.revision="$APP_REVISION"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    MTA_DATA_DIR=/data/projects MTA_HOST=0.0.0.0 MTA_PORT=8080 \
    MTA_APP_VERSION=$APP_VERSION MTA_APP_REVISION=$APP_REVISION MTA_BUILD_ID=$BUILD_ID \
    XDG_CACHE_HOME=/data/projects/.cache TORCH_HOME=/data/projects/.cache/torch
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates tini fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 mtaeditor \
    && useradd --system --uid 10001 --gid 10001 --home /nonexistent --shell /usr/sbin/nologin mtaeditor
WORKDIR /app
COPY requirements.txt requirements-stems.txt requirements-lyrics.txt requirements-chords.txt VERSION REVISION BUILD_INFO ./
# sphn has no CPython 3.14/aarch64 Linux wheel. Its Opus source build also requires
# CMake 3.x (CMake 4 removed compatibility with the project's old policy baseline).
# Use Debian Trixie's system CMake explicitly, and remove all native build tools afterwards.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_STEMS" = "true" ]; then CMAKE=/usr/bin/cmake python -m pip install --no-cache-dir -r requirements-stems.txt; fi \
    && python -m pip install --no-cache-dir -r requirements-lyrics.txt \
    && python -m pip install --no-cache-dir -r requirements-chords.txt \
    && python -m pip install --no-cache-dir --upgrade --force-reinstall setuptools==84.0.0 wheel==0.48.0 urllib3==2.8.0 msgpack==1.2.3 \
    && python -m pip check \
    && python -c "from importlib.metadata import distributions; n=[dist.metadata.get('Name','') for dist in distributions() if dist.metadata.get('Name','').lower().startswith('nvidia-')]; print('NVIDIA Python packages:', n); assert not n, n" \
    && python -c "from importlib.metadata import version; expected={'setuptools':'84.0.0','wheel':'0.48.0','urllib3':'2.8.0','msgpack':'1.2.3'}; actual={p:version(p) for p in expected}; print(actual); assert actual == expected, (actual, expected)" \
    && apt-get purge -y --auto-remove build-essential cmake \
    && rm -rf /var/lib/apt/lists/*
RUN python -c "import fastapi, uvicorn, numpy, whisper, madmom_infer" \
    && if [ "$INSTALL_STEMS" = "true" ]; then python -c "import torch, demucs"; fi
COPY app ./app
COPY LICENSE NOTICE ./
RUN mkdir -p /data/projects && chown -R 10001:10001 /data /app
USER 10001:10001
EXPOSE 8080
VOLUME ["/data/projects"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=3).read()"
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","-m","app.main"]
