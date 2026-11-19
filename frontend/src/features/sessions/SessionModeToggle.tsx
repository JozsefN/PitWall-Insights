import type { SessionWorkspaceMode } from "../../widgets/registry/widget.types";

const modes = [
  { id: "lookback", label: "Lookback", detail: "Review completed laps" },
  { id: "simulation", label: "Replay", detail: "Watch the session unfold" },
] as const;

export function SessionModeToggle({ value, onChange }: {
  value: SessionWorkspaceMode;
  onChange: (mode: SessionWorkspaceMode) => void;
}) {
  return (
    <div className="sessions-mode-switch" role="group" aria-label="Session mode">
      {modes.map((mode) => (
        <button key={mode.id} type="button" className="sessions-mode-option" aria-label={mode.label} aria-pressed={value === mode.id} onClick={() => onChange(mode.id)}>
          <strong>{mode.label}</strong>
          <small>{mode.detail}</small>
        </button>
      ))}
    </div>
  );
}
