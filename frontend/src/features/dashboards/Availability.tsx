import { modesText, sessionKindsText } from "./compatibility";
import type {
  DashboardAudience,
  SessionKind,
} from "../../widgets/registry/widget.types";
import "./availability.css";

export function Availability({
  modes,
  kinds,
}: {
  modes: DashboardAudience[];
  kinds: readonly SessionKind[];
}) {
  return (
    <span className="availability-tags">
      <span>{modesText(modes)}</span>
      <span>{sessionKindsText(kinds)}</span>
    </span>
  );
}
