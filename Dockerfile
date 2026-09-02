# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

ARG APP_UID=10001

RUN groupadd --gid "${APP_UID}" app \
    && useradd --uid "${APP_UID}" --gid app --create-home app

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY requirements-dev.txt ./
COPY --chown=app:app . .
RUN chmod +x docker/entrypoint.sh \
    && DJANGO_SECRET_KEY=container-build-only \
       DJANGO_DEBUG=false \
       python manage.py collectstatic --noinput

FROM base AS test

RUN python -m pip install -r requirements-dev.txt

USER app
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["pytest", "--cov", "--cov-report=term-missing", "--cov-fail-under=85"]

FROM base AS runtime

USER app
EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind=0.0.0.0:8000", "--workers=3", "--timeout=60", "--access-logfile=-", "--error-logfile=-", "--no-control-socket"]
