#!/usr/bin/env bash
set -euo pipefail

SKIP_DOCKER="${SKIP_DOCKER:-0}"
SKIP_RUN="${SKIP_RUN:-0}"
SKIP_WORKER="${SKIP_WORKER:-0}"
DB_READY_ATTEMPTS="${DB_READY_ATTEMPTS:-30}"
DB_READY_SLEEP_SECONDS="${DB_READY_SLEEP_SECONDS:-2}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

echo "==> Project root: $PROJECT_ROOT"

if ! command -v py >/dev/null 2>&1; then
  echo "Python launcher 'py' not found. Install Python 3.12 first." >&2
  exit 1
fi

echo "==> Checking Python 3.12"
py -3.12 -c "import sys; print(sys.version)"

if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment"
  py -3.12 -m venv --copies .venv
else
  echo "==> Reusing existing virtual environment"
fi

PYTHON_EXE=".venv/Scripts/python.exe"

check_database_ready() {
  "$PYTHON_EXE" -c 'from sqlalchemy import create_engine, text; from app.config import settings; engine = create_engine(settings.database_url, future=True, pool_pre_ping=True); connection = engine.connect(); connection.execute(text("SELECT 1")); connection.close(); engine.dispose()' >/dev/null 2>&1
}

wait_for_database() {
  echo "==> Waiting for database readiness"

  for ((attempt=1; attempt<=DB_READY_ATTEMPTS; attempt++)); do
    if check_database_ready; then
      echo "==> Database is ready"
      return 0
    fi

    if [ "$attempt" -lt "$DB_READY_ATTEMPTS" ]; then
      echo "   Database not ready yet ($attempt/$DB_READY_ATTEMPTS). Retrying in ${DB_READY_SLEEP_SECONDS}s..."
      sleep "$DB_READY_SLEEP_SECONDS"
    fi
  done

  echo "Database did not become ready in time. Check PostgreSQL startup logs and connection settings." >&2
  return 1
}

echo "==> Upgrading pip"
"$PYTHON_EXE" -m pip install --upgrade pip

echo "==> Installing requirements"
"$PYTHON_EXE" -m pip install -r requirements.txt

if [ "$SKIP_DOCKER" != "1" ]; then
  if command -v docker >/dev/null 2>&1 && [ -f "docker-compose.yml" ]; then
    echo "==> Starting PostgreSQL with docker compose"
    docker compose up -d
  else
    echo "==> Docker or docker-compose.yml missing, skipping Docker startup"
  fi
else
  echo "==> Skipping Docker startup"
fi

if [ -f "alembic.ini" ]; then
  wait_for_database
  echo "==> Running database migrations"
  "$PYTHON_EXE" -m alembic upgrade head
else
  echo "==> alembic.ini not found, skipping migrations"
fi

if [ "$SKIP_RUN" != "1" ]; then
  echo "==> Starting backend"
  WORKER_PID=""
  cleanup_worker() {
    if [ -n "$WORKER_PID" ]; then
      kill "$WORKER_PID" >/dev/null 2>&1 || true
    fi
  }
  trap cleanup_worker EXIT INT TERM

  if [ "$SKIP_WORKER" != "1" ]; then
    echo "==> Starting import worker"
    "$PYTHON_EXE" -m app.worker &
    WORKER_PID="$!"
  else
    echo "==> Import worker not started because SKIP_WORKER=1 was set."
  fi

  "$PYTHON_EXE" -m uvicorn app.main:app --reload
else
  echo "==> Setup complete. Backend not started because SKIP_RUN=1 was set."
fi
