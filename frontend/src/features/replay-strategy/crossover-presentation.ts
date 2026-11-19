import type {
  CrossoverDecision,
  TyreFamily,
} from "./replay-strategy.contracts";

export const crossoverTyreNames: Record<TyreFamily, string> = {
  SLICK: "Slicks",
  INTERMEDIATE: "Intermediates",
  WET: "Full wets",
};

export function crossoverHeadline(decision: CrossoverDecision) {
  const target = decision.target
    ? crossoverTyreNames[decision.target].toLowerCase()
    : "the other set";
  switch (decision.action) {
    case "box":
      return `Box for ${target}`;
    case "forecast_box":
      return `Scenario favors boxing for ${target}`;
    case "wait":
      return `Wait a lap before fitting ${target}`;
    case "hold":
      return "Stay on the current set";
    case "closed":
      return "Pit entry closed";
    case "outlap":
      return "Out-lap in progress";
    default:
      return "Watch the next sectors";
  }
}
