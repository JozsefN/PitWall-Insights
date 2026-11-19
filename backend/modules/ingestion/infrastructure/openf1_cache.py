"""Disposable, atomically replaced OpenF1 response files."""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
from pathlib import Path
import tempfile
import time
from typing import Any

logger = logging.getLogger("pitwall.ingestion.cache")

OpenF1Rows = list[dict[str, Any]]


def valid_rows(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(row, dict) for row in value)


class OpenF1ResponseCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, url: str) -> Path:
        return self.directory / (hashlib.sha256(url.encode()).hexdigest() + ".json.gz")

    def read(self, url: str, *, ttl_seconds: float) -> OpenF1Rows | None:
        path = self.path_for(url)
        try:
            if time.time() - path.stat().st_mtime >= ttl_seconds:
                return None
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                rows = json.load(stream)
            # Empty responses may reflect temporary source availability.
            return rows if rows and valid_rows(rows) else None
        except (OSError, ValueError, EOFError):
            return None

    def write(self, url: str, rows: OpenF1Rows) -> None:
        if not rows:
            return
        temporary: Path | None = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            # Unique names work for different threads AND worker processes.
            # A reader sees either the previous complete file or the new one.
            with tempfile.NamedTemporaryFile(
                dir=self.directory, prefix=self.path_for(url).stem + "-",
                suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                with gzip.GzipFile(fileobj=stream, mode="wb") as compressed:
                    compressed.write(json.dumps(rows).encode("utf-8"))
            temporary.replace(self.path_for(url))
        except OSError:
            # This cache is optional; a valid download can still be imported.
            logger.warning("OpenF1 response cache could not be written", exc_info=True)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove an OpenF1 temporary cache file")
