"""Seed verified fixture accounts for local end-to-end tests of other features."""
import json
import os
from pathlib import Path
import subprocess

BACKEND = Path(__file__).resolve().parents[1] / "backend"

_SEED = """
import json, sys
from datetime import datetime, timezone
from sqlalchemy.engine import make_url
from app.config import settings
from modules.identity_auth.application.security import create_access_token, hash_password
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.storage.infrastructure.db import SessionLocal

payload = json.load(sys.stdin)
email = payload['email']
if make_url(settings.database_url).host not in {'localhost', '127.0.0.1', '::1'} or not email.endswith('@example.com'):
    raise SystemExit('Verified fixtures require a local database and a reserved example.com address.')
with SessionLocal() as db:
    user = UserRecord(email=email, password_hash=hash_password(payload['password']),
                      email_verified_at=datetime.now(timezone.utc))
    db.add(user)
    db.commit()
    print(json.dumps({'access_token': create_access_token(user.id, user.email), 'user_id': user.id}))
"""


def seed_verified_account(credentials):
    python = BACKEND / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    result = subprocess.run([str(python), "-c", _SEED], cwd=BACKEND, input=json.dumps(credentials),
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)
