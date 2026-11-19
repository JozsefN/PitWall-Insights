"""Separate persistent application signing secret; never ship a known JWT signing key."""
import os
from pathlib import Path
import secrets
import time


def load_signing_key():
    configured = os.environ.get("PITWALL_AUTH_SECRET")
    if configured:
        if len(configured.encode()) < 32:
            raise ValueError("PITWALL_AUTH_SECRET must contain at least 32 bytes")
        return configured
    directory = Path(os.environ.get("LOCALAPPDATA") or Path.home()/".local"/"share") / "pitwall-insights" / "secrets"
    directory.mkdir(parents=True,exist_ok=True)
    path = directory/"identity-signing.key"
    try:
        descriptor = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor,"w") as stream:
            stream.write(secrets.token_urlsafe(48))
    # Another API process may have created the file and be finishing its write.
    for _ in range(20):
        value = path.read_text().strip()
        if len(value)>=32:
            return value
        time.sleep(.01)
    raise ValueError("Application signing key is invalid")
