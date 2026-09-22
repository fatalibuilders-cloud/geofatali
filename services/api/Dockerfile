# GeoFatali API.
#
# Multi-stage so the runtime image does not carry a compiler. The engine is
# copied in as a sibling package rather than published, because it is versioned
# with the API and a mismatch between them would be worse than a build step.

FROM python:3.11-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY services/api/requirements.txt ./requirements.txt
RUN pip install --prefix=/install -r requirements.txt


FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/engine

# Runs as a non-root user: a web process has no reason to be root, and a
# container that is root by default is one mistake away from being a problem.
RUN useradd --create-home --uid 10001 geofatali

COPY --from=build /install /usr/local

WORKDIR /app
COPY services/engineering-engine/geofatali_engine /engine/geofatali_engine
COPY services/api/app /app/app
COPY database/migrations /database/migrations
COPY services/api/docker-entrypoint.sh /usr/local/bin/entrypoint

RUN chmod +x /usr/local/bin/entrypoint && chown -R geofatali /app
USER geofatali

EXPOSE 8000

# Bound to 0.0.0.0 because a container that listens only on its own loopback
# is unreachable from anywhere, which is the single commonest way a phone
# fails to see a development server.
ENV GEOFATALI_BIND_HOST=0.0.0.0 \
    GEOFATALI_PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["entrypoint"]
