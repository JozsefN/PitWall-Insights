type TimedSessionSnapshot = { session_id: string; as_of_ms: number };

export function retainSnapshot<T extends TimedSessionSnapshot>(
  previous: T | undefined,
  sameScope: boolean,
  sessionId: string,
  cutoff?: number,
): T | undefined {
  if (!sameScope || previous?.session_id !== sessionId) return undefined;
  if (cutoff !== undefined && previous.as_of_ms > cutoff) return undefined;
  return previous;
}
