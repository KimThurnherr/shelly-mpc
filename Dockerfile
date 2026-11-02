# Base-Image per Digest gepinnt (python:3.12-slim, Stand 2026-10-24), damit ein Build
# reproduzierbar ist. Aktualisieren: neuen Digest mit
#   docker buildx imagetools inspect python:3.12-slim
# ermitteln und hier eintragen.
FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY shelly_mcp ./shelly_mcp

# Kein root im Container
RUN useradd --system --uid 10001 --create-home --home-dir /home/app --shell /usr/sbin/nologin app

ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    HOME=/home/app

# Git-Commit und Version des Builds (von GitHub Actions gesetzt) - get_version
# gibt beides zurueck, damit nach einem Redeploy pruefbar ist, welcher Stand wirklich laeuft.
ARG GIT_SHA=unbekannt
ARG APP_VERSION=
ENV GIT_SHA=$GIT_SHA \
    APP_VERSION=$APP_VERSION

EXPOSE 8000

# /healthz ist ohne Auth erreichbar und prueft nur, ob der Prozess antwortet
# (nicht Cloud oder Gateway). Kein curl/wget im Image, darum per Python/urllib.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('MCP_PORT', '8000') + '/healthz', timeout=4)"]

USER app

CMD ["python", "-m", "shelly_mcp"]
