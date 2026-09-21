FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite+aiosqlite:////data/mafia_vmeda.db

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install .

RUN useradd --create-home --uid 10001 botuser \
    && mkdir -p /data \
    && chown botuser:botuser /data
USER botuser

CMD ["python", "-m", "app.main"]
