export function CapabilityMark({ included, showLabel = false }: { included: boolean; showLabel?: boolean }) {
  const label = included ? showLabel ? "Supported" : "Included" : "Unavailable";
  return <span className={`profile-availability ${included ? "is-supported" : "is-unavailable"}`} aria-label={label}>
    <span aria-hidden="true">{included ? "✓" : "—"}</span>
    <span className={showLabel ? "profile-check-label" : "sr-only"}>{label}</span>
  </span>;
}
