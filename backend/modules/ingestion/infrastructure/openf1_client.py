"""Bounded OpenF1 HTTP access; independent of race-data conversion and storage."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import threading
import time
from typing import Callable
from urllib.parse import urlencode

import requests

from modules.ingestion.infrastructure.cache_paths import resolve_provider_cache_dir
from modules.ingestion.infrastructure.openf1_cache import (
    OpenF1ResponseCache,
    OpenF1Rows,
    valid_rows,
)


class OpenF1AccessError(ValueError):
    """Actionable source failure, compatible with existing import error handling."""


class OpenF1RequestLimiter:
    """Space requests across clients in one process, including retry attempts."""

    def __init__(self, interval_seconds: float = 2.05) -> None:
        self.interval_seconds = interval_seconds
        self._last_request = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            time.sleep(max(0, self.interval_seconds - (time.monotonic() - self._last_request)))
            self._last_request = time.monotonic()


_process_limiter = OpenF1RequestLimiter()


class OpenF1Client:
    resources = frozenset({
        "meetings", "sessions", "drivers", "laps", "stints", "weather",
        "race_control", "position", "session_result", "pit", "car_data",
        "location", "intervals", "starting_grid", "overtakes", "team_radio",
    })
    retry_statuses = frozenset({429, 502, 503, 504})
    max_response_bytes = 30_000_000

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        http_get: Callable | None = None,
        limiter: OpenF1RequestLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
        max_retry_wait_seconds: float = 30,
    ) -> None:
        if max_attempts < 1 or max_retry_wait_seconds < 0:
            raise ValueError("Invalid OpenF1 retry configuration")
        self.cache = cache_dir if cache_dir is not None else resolve_provider_cache_dir("openf1")
        self.response_cache = OpenF1ResponseCache(self.cache)
        self._http_get = http_get or requests.get
        self._limiter = limiter or _process_limiter
        self._sleep = sleep
        self.max_attempts = max_attempts
        self.max_retry_wait_seconds = max_retry_wait_seconds

    def get(self, resource: str, *, refresh=False, cache_ttl_seconds=7 * 86400, **query) -> OpenF1Rows:
        if resource not in self.resources:
            raise ValueError("Unsupported OpenF1 resource")
        url = "https://api.openf1.org/v1/" + resource + "?" + urlencode(sorted(query.items()))
        if not refresh:
            cached = self.response_cache.read(url, ttl_seconds=cache_ttl_seconds)
            if cached is not None:
                return cached
        rows = self._download(url)
        self.response_cache.write(url, rows)
        return rows

    def _download(self, url: str) -> OpenF1Rows:
        for attempt in range(self.max_attempts):
            self._limiter.wait()
            try:
                with self._http_get(url, timeout=(5, 25), stream=True) as response:
                    if response.status_code == 404:
                        return []
                    if response.status_code in (401, 403):
                        raise OpenF1AccessError(
                            "OpenF1 historical access is unavailable for this session; "
                            "current live sessions require authorized live access"
                        )
                    if response.status_code in self.retry_statuses:
                        if attempt + 1 == self.max_attempts:
                            raise OpenF1AccessError("OpenF1 is busy or temporarily unavailable; retry later")
                        delay = self._retry_delay(response.headers.get("Retry-After"), attempt)
                    else:
                        response.raise_for_status()
                        return self._read_rows(response)
                # Release the response before waiting or starting another request.
            except (requests.Timeout, requests.ConnectionError):
                if attempt + 1 == self.max_attempts:
                    raise OpenF1AccessError("OpenF1 connection failed; retry when the service is available") from None
                delay = self._retry_delay(None, attempt)
            except requests.RequestException:
                raise OpenF1AccessError("OpenF1 could not provide this dataset; retry when the service is available") from None
            self._sleep(delay)
        raise AssertionError("Retry loop must return or raise")

    def _retry_delay(self, retry_after: str | None, attempt: int) -> float:
        delay = float(2 ** attempt)
        if retry_after:
            try:
                delay = max(0, float(retry_after))
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    delay = max(0, (retry_at - datetime.now(timezone.utc)).total_seconds())
                except (ValueError, TypeError, OverflowError):
                    pass
        if delay > self.max_retry_wait_seconds:
            # Do not violate a long provider-requested wait by shortening it.
            raise OpenF1AccessError("OpenF1 requires a longer retry delay; try this import again later")
        return delay

    def _read_rows(self, response: requests.Response) -> OpenF1Rows:
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > self.max_response_bytes:
                raise OpenF1AccessError("OpenF1 response exceeds the bounded download size")
            chunks.append(chunk)
        try:
            rows = json.loads(b"".join(chunks))
        except (ValueError, UnicodeError):
            raise OpenF1AccessError("OpenF1 returned invalid JSON; retry this dataset later") from None
        if not valid_rows(rows):
            raise OpenF1AccessError("Invalid OpenF1 row response")
        return rows
