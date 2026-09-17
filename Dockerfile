# Multi-stage build: React frontend, then the Python backend that serves
# both the API and the built frontend as one process (§2: "One FastAPI
# app, one React app" — in production that's one container, one process).
#
# The catalog build runs at image-build time so the deployed image is
# self-contained (no persistent volume needed just to hold the catalog).
# It needs network access to the public ABO S3 bucket during `docker build`.

FROM node:20-slim AS web-build
WORKDIR /repo
COPY sdk/package.json sdk/package-lock.json ./sdk/
RUN cd sdk && npm ci
COPY sdk/ ./sdk/
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci
COPY web/ ./web/
RUN cd web && npm run build

FROM python:3.12-slim AS backend
WORKDIR /repo

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libwebp7 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY catalog/ ./catalog/
COPY server/ ./server/
RUN pip install --no-cache-dir -e .

COPY assets/ ./assets/
COPY --from=web-build /repo/web/dist ./web/dist

# Bakes the ~810-item catalog (metadata + resized thumbnails) into the
# image. Network access required at build time.
RUN python -m catalog.build

ENV APP_ENV=production
EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
