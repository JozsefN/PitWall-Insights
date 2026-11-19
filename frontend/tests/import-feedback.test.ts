import { test } from "node:test";
import assert from "node:assert/strict";
import { getImportFeedback } from "../src/features/sessions/import-feedback.ts";

test("source failures retain the actionable backend explanation", () => {
  assert.deepEqual(getImportFeedback({ response: { data: { detail: { message: "Try this session again after it has ended" } } } }),
    { message: "Try this session again after it has ended" });
});
test("source and network errors are readable", () => {
  assert.deepEqual(getImportFeedback({ response: { data: { detail: "Session has no public data yet" } } }),
    { message: "Session has no public data yet" });
  assert.match(getImportFeedback(new Error("Network Error")).message, /backend/);
  assert.match(getImportFeedback({ response: { data: { detail: [] } } }).message, /backend/);
});
