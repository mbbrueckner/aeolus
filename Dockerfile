# Front end first, so a Python-only change does not rebuild it.
FROM node:24-alpine AS frontend
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

# Dependencies before source, so edits do not invalidate the install layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra server --no-install-project

COPY app/ ./app/
COPY --from=frontend /build/dist ./frontend/dist
RUN uv sync --frozen --no-dev --extra server

# Nothing is written at runtime: uploads are parsed in memory and no database
# is involved, so the container can run read-only.
RUN useradd --create-home --uid 10001 aeolus
USER aeolus

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "app.web.api:app", "--host", "0.0.0.0", "--port", "8000"]
