"""Idempotent local development key provisioning. Production should inject a managed secret."""
import base64
import os
from modules.provider_connections.infrastructure.vault import default_key_path

if __name__ == "__main__":
    path = default_key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Provider encryption key already exists; preserved.")
    else:
        with os.fdopen(handle, "w") as stream:
            stream.write(base64.urlsafe_b64encode(os.urandom(32)).decode())
        print("Provider encryption key initialized outside the repository.")
