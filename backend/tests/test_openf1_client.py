import gzip
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from multiprocessing import get_context
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import requests

from modules.ingestion.infrastructure.openf1_cache import OpenF1ResponseCache
from modules.ingestion.infrastructure.openf1_client import OpenF1AccessError, OpenF1Client


class Response:
    def __init__(self, status=200, *, rows=None, payload=None, headers=None, stream_error=None):
        self.status_code = status
        self.headers = headers or {}
        self.payload = payload if payload is not None else json.dumps(rows or []).encode()
        self.stream_error = stream_error
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("HTTP error", response=self)

    def iter_content(self, chunk_size):
        yield self.payload
        if self.stream_error:
            raise self.stream_error


def write_cache_in_process(directory, worker):
    cache = OpenF1ResponseCache(Path(directory))
    for index in range(12):
        cache.write("shared-url", [{"worker": worker, "sample": index, "padding": "x" * 1000}])


class OpenF1ClientTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.http = Mock()
        self.limiter = Mock()
        self.sleep = Mock()
        self.client = OpenF1Client(cache_dir=self.directory, http_get=self.http, limiter=self.limiter, sleep=self.sleep)

    def test_cache_reuse_sorted_filters_and_explicit_refresh(self):
        rows = [{"session_key": 42, "driver_number": 1}]
        responses = [Response(rows=rows), Response(rows=[{"updated": True}])]
        self.http.side_effect = responses
        self.assertEqual(self.client.get("laps", session_key=42, driver_number=1), rows)
        self.assertEqual(self.client.get("laps", driver_number=1, session_key=42), rows)
        self.assertEqual(self.http.call_count, 1)
        self.assertEqual(self.client.get("laps", session_key=42, driver_number=1, refresh=True), [{"updated": True}])
        self.assertEqual(self.http.call_count, 2)
        self.assertTrue(all(response.closed for response in responses))

    def test_expired_cache_is_replaced(self):
        self.http.side_effect = [Response(rows=[{"old": True}]), Response(rows=[{"new": True}])]
        self.client.get("laps")
        path = next(self.directory.glob("*.json.gz"))
        os.utime(path, (1, 1))
        self.assertEqual(self.client.get("laps"), [{"new": True}])
        self.assertEqual(self.http.call_count, 2)

    def test_corrupt_empty_and_wrong_shape_cache_are_not_trusted(self):
        url = "https://api.openf1.org/v1/laps?"
        path = self.client.response_cache.path_for(url)
        for payload in (b"not gzip", gzip.compress(b"{broken"), gzip.compress(b'{}'), gzip.compress(b'[]')):
            with self.subTest(payload=payload):
                path.write_bytes(payload)
                self.http.return_value = Response(rows=[{"valid": True}])
                self.assertEqual(self.client.get("laps"), [{"valid": True}])
        self.assertEqual(self.http.call_count, 4)

    def test_malformed_json_is_actionable_and_not_cached(self):
        self.http.return_value = Response(payload=b"<html>private upstream error</html>")
        with self.assertRaisesRegex(OpenF1AccessError, "invalid JSON") as failure:
            self.client.get("laps")
        self.assertNotIn("private", str(failure.exception))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_non_record_response_is_rejected(self):
        for payload in (b'{"error":"unavailable"}', b'[1,2]', b'null'):
            with self.subTest(payload=payload):
                self.http.return_value = Response(payload=payload)
                with self.assertRaisesRegex(OpenF1AccessError, "Invalid OpenF1 row"):
                    self.client.get("laps")
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_authentication_failures_do_not_retry(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.http.reset_mock()
                self.http.return_value = Response(status)
                with self.assertRaisesRegex(OpenF1AccessError, "historical access"):
                    self.client.get("laps")
                self.assertEqual(self.http.call_count, 1)
        self.sleep.assert_not_called()

    def test_rate_limit_and_unavailable_service_retry_with_closed_responses(self):
        first = Response(429, headers={"Retry-After": "2"})
        second = Response(503)
        self.http.side_effect = [first, second, Response(rows=[{"valid": True}])]
        self.assertEqual(self.client.get("laps"), [{"valid": True}])
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [2, 2])
        self.assertEqual(self.limiter.wait.call_count, 3)
        self.assertTrue(first.closed and second.closed)

    def test_long_retry_after_is_not_shortened(self):
        self.http.return_value = Response(429, headers={"Retry-After": "60"})
        with self.assertRaisesRegex(OpenF1AccessError, "longer retry delay"):
            self.client.get("laps")
        self.assertEqual(self.http.call_count, 1)
        self.sleep.assert_not_called()

    def test_retry_after_http_date_is_supported(self):
        retry_at = datetime.now(timezone.utc) + timedelta(seconds=10)
        self.http.side_effect = [Response(503, headers={"Retry-After": format_datetime(retry_at, usegmt=True)}), Response(rows=[{"valid": True}])]
        self.client.get("laps")
        delay = self.sleep.call_args.args[0]
        self.assertGreater(delay, 0)
        self.assertLessEqual(delay, 10)

    def test_connection_retry_budget_is_finite(self):
        self.http.side_effect = requests.Timeout("upstream timeout")
        with self.assertRaisesRegex(OpenF1AccessError, "connection failed"):
            self.client.get("laps")
        self.assertEqual(self.http.call_count, 3)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [1, 2])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_permanent_http_error_is_not_retried(self):
        self.http.return_value = Response(400)
        with self.assertRaisesRegex(OpenF1AccessError, "could not provide"):
            self.client.get("laps")
        self.assertEqual(self.http.call_count, 1)
        self.sleep.assert_not_called()

    def test_missing_and_empty_responses_are_not_cached(self):
        self.http.side_effect = [Response(404), Response(), Response(rows=[{"valid": True}])]
        self.assertEqual(self.client.get("laps"), [])
        self.assertEqual(self.client.get("laps"), [])
        self.assertEqual(self.client.get("laps"), [{"valid": True}])
        self.assertEqual(self.http.call_count, 3)

    def test_response_size_limit_is_enforced_before_caching(self):
        self.client.max_response_bytes = 3
        self.http.return_value = Response(payload=b"1234")
        with self.assertRaisesRegex(OpenF1AccessError, "bounded download"):
            self.client.get("laps")
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_partial_stream_is_discarded_before_retry(self):
        first = Response(payload=b'[{"partial":', stream_error=requests.Timeout())
        self.http.side_effect = [first, Response(rows=[{"complete": True}])]
        self.assertEqual(self.client.get("laps"), [{"complete": True}])
        self.assertTrue(first.closed)
        self.assertEqual(self.client.get("laps"), [{"complete": True}])
        self.assertEqual(self.http.call_count, 2)

    def test_cache_write_failure_does_not_fail_valid_download(self):
        blocked = self.directory / "file-instead-of-cache-directory"
        blocked.write_text("occupied")
        client = OpenF1Client(cache_dir=blocked, http_get=self.http, limiter=self.limiter, sleep=self.sleep)
        self.http.return_value = Response(rows=[{"valid": True}])
        with self.assertLogs("pitwall.ingestion.cache", level="WARNING"):
            self.assertEqual(client.get("laps"), [{"valid": True}])

    def test_failed_replace_cleans_up_temporary_file(self):
        self.http.return_value = Response(rows=[{"valid": True}])
        with patch.object(Path, "replace", side_effect=OSError("disk unavailable")):
            with self.assertLogs("pitwall.ingestion.cache", level="WARNING"):
                self.assertEqual(self.client.get("laps"), [{"valid": True}])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_parallel_processes_leave_one_complete_cache_and_no_temporary_files(self):
        with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as pool:
            futures = [pool.submit(write_cache_in_process, str(self.directory), worker) for worker in (1, 2)]
            for future in futures:
                future.result(timeout=30)
        rows = self.client.response_cache.read("shared-url", ttl_seconds=60)
        self.assertIn(rows[0]["worker"], (1, 2))
        self.assertEqual(rows[0]["sample"], 11)
        self.assertEqual(len(list(self.directory.iterdir())), 1)

    def test_unknown_resource_is_rejected_before_network_access(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.client.get("../unknown")
        self.http.assert_not_called()
