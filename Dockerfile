FROM debian:trixie-slim AS audio-core-build
RUN apt-get update && apt-get install -y --no-install-recommends cmake g++ make && rm -rf /var/lib/apt/lists/*
COPY native/audio_core /src/audio_core
RUN cmake -S /src/audio_core -B /build -DCMAKE_BUILD_TYPE=Release && cmake --build /build --parallel 2

FROM python:3.14-slim-trixie AS vst3-host-build
RUN apt-get update && apt-get install -y --no-install-recommends git cmake g++ make pkg-config libfreetype6-dev libasound2-dev libx11-dev libxext-dev libxrender-dev libxcomposite-dev libxrandr-dev libxinerama-dev libxcursor-dev libgl1-mesa-dev libpixman-1-dev libxfont-dev libxkbfile-dev x11proto-dev xtrans-dev && rm -rf /var/lib/apt/lists/*
COPY scripts/build_vst3_runtime.py scripts/patch_vst3_runtime.py /src/scripts/
COPY native/host_transport /src/native/host_transport
RUN python /src/scripts/build_vst3_runtime.py --wheel-dir /wheels

FROM python:3.14-slim-trixie
ARG APP_VERSION=0.3.0
ARG APP_REVISION=210
ARG RELEASE_CHANNEL=stable
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
    MTA_APP_VERSION=$APP_VERSION MTA_APP_REVISION=$APP_REVISION MTA_RELEASE_CHANNEL=$RELEASE_CHANNEL MTA_BUILD_ID=$BUILD_ID \
    MTA_AI_JOB_STATE_DIR=/data/projects/.ai-jobs MTA_DIAGNOSTIC_DIR=/data/projects/.diagnostics \
    XDG_CACHE_HOME=/data/projects/.cache TORCH_HOME=/data/projects/.cache/torch \
    VAMP_PATH=/opt/mta/vamp MTA_VAMP_PATH=/opt/mta/vamp MTA_CHORDINO_HOST=/usr/bin/vamp-simple-host
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates tini fonts-dejavu-core xvfb libxtst6 vamp-examples libasound2t64 libfreetype6 libx11-6 libxext6 libxrandr2 libxinerama1 libxcursor1 libgl1 libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 mtaeditor \
    && useradd --system --uid 10001 --gid 10001 --home /nonexistent --shell /usr/sbin/nologin mtaeditor
COPY --from=vst3-host-build /wheels/*.whl /opt/mta/vst3-wheels/
WORKDIR /app
COPY requirements.txt requirements-vst3.txt requirements-stems.txt requirements-lyrics.txt requirements-chords.txt VERSION REVISION RELEASE_CHANNEL BUILD_INFO ./
# sphn has no CPython 3.14/aarch64 Linux wheel. Its Opus source build also requires
# CMake 3.x (CMake 4 removed compatibility with the project's old policy baseline).
# Use Debian Trixie's system CMake explicitly, and remove all native build tools afterwards.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake curl libboost-all-dev vamp-plugin-sdk \
    && python -m pip install --no-cache-dir --find-links=/opt/mta/vst3-wheels -r requirements.txt \
    && if [ "$INSTALL_STEMS" = "true" ]; then CMAKE=/usr/bin/cmake python -m pip install --no-cache-dir -r requirements-stems.txt; fi \
    && python -m pip install --no-cache-dir -r requirements-lyrics.txt \
    && python -m pip install --no-cache-dir -r requirements-chords.txt \
    && python -m pip install --no-cache-dir --upgrade --force-reinstall setuptools==84.0.0 wheel==0.48.0 urllib3==2.8.0 msgpack==1.2.3 \
    && python -m pip check \
    && curl -fsSL https://github.com/c4dm/nnls-chroma/archive/refs/heads/master.tar.gz -o /tmp/nnls.tar.gz \
    && mkdir -p /tmp/nnls /opt/mta/vamp \
    && tar -xzf /tmp/nnls.tar.gz -C /tmp/nnls --strip-components=1 \
    && make -C /tmp/nnls -f Makefile.linux VAMP_SDK_DIR=/usr/include/vamp-sdk \
    && cp /tmp/nnls/nnls-chroma.so /tmp/nnls/nnls-chroma.cat /tmp/nnls/nnls-chroma.n3 /opt/mta/vamp/ \
    && VAMP_PATH=/opt/mta/vamp vamp-simple-host --list-ids | grep -q 'nnls-chroma:chordino' \
    && rm -rf /tmp/nnls /tmp/nnls.tar.gz \
    && python -c "from importlib.metadata import distributions; n=[dist.metadata.get('Name','') for dist in distributions() if dist.metadata.get('Name','').lower().startswith('nvidia-')]; print('NVIDIA Python packages:', n); assert not n, n" \
    && python -c "from importlib.metadata import version; expected={'setuptools':'84.0.0','wheel':'0.48.0','urllib3':'2.8.0','msgpack':'1.2.3'}; actual={p:version(p) for p in expected}; print(actual); assert actual == expected, (actual, expected)" \
    && apt-get purge -y --auto-remove build-essential cmake curl libboost-all-dev vamp-plugin-sdk \
    && rm -rf /var/lib/apt/lists/*
RUN python -c "import fastapi, uvicorn, numpy, whisper, madmom_infer, pedalboard, av, mido; assert hasattr(pedalboard.VST3Plugin,'_mta_set_transport')" \
    && if [ "$INSTALL_STEMS" = "true" ]; then python -c "import torch, demucs"; fi
COPY app ./app
COPY --from=audio-core-build /build/libmta_audio_core.so /app/bin/libmta_audio_core.so
RUN chmod 755 /app/app/ace_step_http_worker.py
COPY LICENSE NOTICE ./
RUN mkdir -p /data/projects /opt/mta/vst3 && chown -R 10001:10001 /data /app
USER 10001:10001
EXPOSE 8080
VOLUME ["/data/projects"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=3).read()"
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","-m","app.main"]
