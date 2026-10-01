FROM python:3.14-slim-bookworm
ARG APP_VERSION=0.2.0-11
ARG BUILD_ID=unknown
ARG INSTALL_STEMS=true
LABEL org.opencontainers.image.title="MTA Audio Editor" \
      org.opencontainers.image.description="DAW-style editor for M-Audio/M-Live Merish MTA multitrack files" \
      org.opencontainers.image.source="https://github.com/desalvo/mta-audio-editor" \
      org.opencontainers.image.licenses="EUPL-1.2" \
      org.opencontainers.image.authors="Alessandro De Salvo <braket71@gmail.com>" \
      org.opencontainers.image.version="$APP_VERSION"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    MTA_DATA_DIR=/data/projects MTA_HOST=0.0.0.0 MTA_PORT=8080 \
    MTA_APP_VERSION=$APP_VERSION MTA_BUILD_ID=$BUILD_ID \
    XDG_CACHE_HOME=/data/projects/.cache TORCH_HOME=/data/projects/.cache/torch
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates tini && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 mtaeditor && useradd --system --uid 10001 --gid 10001 --home /nonexistent --shell /usr/sbin/nologin mtaeditor
WORKDIR /app
COPY requirements.txt requirements-stems.txt VERSION BUILD ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_STEMS" = "true" ]; then pip install --no-cache-dir -r requirements-stems.txt; fi \
    && pip install --no-cache-dir --upgrade setuptools==84.0.0 wheel==0.48.0 \
    && python -c "import fastapi, uvicorn, numpy" \
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
