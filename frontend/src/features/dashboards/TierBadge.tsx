export function TierBadge({ tier }: { tier: 0 | 1 | 2 | 3 }) {
  return (
    <span className={`widget-tier${tier ? " widget-tier--paid" : ""}`}>
      {tier === 0 ? "Free" : tier === 1 ? "Analyst" : "Pro"}
    </span>
  );
}
