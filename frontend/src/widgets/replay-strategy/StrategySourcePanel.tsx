import { DriverSelect } from "../../components/DriverSelect";
import { driverOption } from "../../components/driver-select-options";
import type { CSSProperties, ReactNode } from "react";
import type {
  DriverStrategy,
  ReplayStrategy,
} from "../../features/replay-strategy/replay-strategy.contracts";
import { useStrategyReplay } from "../../features/replay-strategy/strategy-replay-context";
import {
  useSessionTimeLabel,
  useSessionWorkspace,
} from "../../features/sessions/SessionWorkspaceContext";
import { getEntryAccent } from "../../features/sessions/session-utils";
import { WidgetCard } from "../shared/WidgetCard";
import { WidgetError, WidgetLoading } from "../shared/WidgetState";
import "./strategy-panels.css";

export function StrategySourcePanel({
  title,
  driverFilter,
  children,
}: {
  title: string;
  driverFilter?: boolean;
  children: (data: ReplayStrategy, driver?: DriverStrategy) => ReactNode;
}) {
  const { query, focus, setFocus } = useStrategyReplay();
  const { entries } = useSessionWorkspace();
  const timeLabel = useSessionTimeLabel();
  const data = query.data;
  const driver = data?.drivers.find((row) => row.entry_id === focus);
  const entry = entries.find((item) => item.id === focus);
  const accent = entry ? getEntryAccent(entry) : undefined;
  return (
    <WidgetCard
      title={title}
      actions={
        driverFilter ? (
          <DriverSelect
            className="strategy-driver-select"
            aria-label={`${title} driver`}
            value={focus}
            onChange={setFocus}
            options={entries.map((entry) => driverOption(entry))}
          />
        ) : undefined
      }
    >
      <div
        className="strategy-panel"
        style={{ "--strategy-driver": accent } as CSSProperties}
      >
        {data ? (
          <p className="strategy-panel-clock">
            <span>Replay · {timeLabel(data.as_of_ms)}</span>
            <span>
              {query.isFetching
                ? "Updating"
                : data.total_laps
                  ? `${data.leader_completed_laps}/${data.total_laps} laps completed`
                  : ""}
            </span>
          </p>
        ) : null}
        {query.isError ? (
          <>
            <WidgetError message="The strategy snapshot could not be loaded." />
            <button
              className="button-secondary"
              onClick={() => void query.refetch()}
            >
              Retry calculation
            </button>
          </>
        ) : null}
        {data ? (
          children(data, driver)
        ) : !query.isError ? (
          <WidgetLoading />
        ) : null}
      </div>
    </WidgetCard>
  );
}
