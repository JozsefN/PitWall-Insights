export function TierBadge({ tier }: { tier: 0 | 1 | 2 | 3 }) {
  return (
    <span className={`widget-tier${tier ? " widget-tier--paid" : ""}`}>
      {tier === 0 ? "Free" : `Tier ${tier}`}
    </span>
  );
}
