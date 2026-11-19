export type ImportFeedback = { message: string };

export function getImportFeedback(error: unknown): ImportFeedback {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
    return { message: detail.message };
  }
  if (typeof detail === "string") return { message: detail };
  return { message: "The session could not be loaded. Check that the backend is running, then retry." };
}
