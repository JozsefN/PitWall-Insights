import { DriverSelect } from "../../components/DriverSelect";
import { driverOption } from "../../components/driver-select-options";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { importSession } from "../../data/api/sessions.api";
import { useSessionTimeLabel, useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import { useTelemetryMaterializationReadiness } from "../../features/sessions/session-data.hooks";
import {
  useRadioTimelineQuery,
  useReviewQuery,
  useSessionReview,
} from "../../features/session-review/review-query";
import type {
  DriverCard,
  LapChoice,
  ReviewData,
} from "../../features/session-review/contracts";
import { WidgetCard } from "../shared/WidgetCard";
import { QualifyingDriverCards } from "../driver-cards/QualifyingDriverCards";
import { ReviewContent } from "./ReviewContent";
import { TeamRadio } from "./TeamRadio";
import type { ReviewPanelId } from "./review-specs";
import { reviewPanelGuide, reviewPanels } from "./review-specs";
import { seconds } from "./format";
import "./review.css";

function LoadReviewMetadata() {
  const { session, sessionId } = useSessionWorkspace();
  const cache = useQueryClient();
  const refresh = useMutation({
    mutationFn: () =>
      importSession({
        season_year: session.season_year,
        round_number: session.round_number!,
        session_name: session.session_name,
        source_session_key: session.source_session_key,
        import_profile: "core",
      }),
    onSuccess: () =>
      cache.invalidateQueries({ queryKey: ["session-review", sessionId] }),
  });
  if (
    !session.round_number ||
    !session.source_session_key.startsWith("openf1:session:")
  )
    return null;
  return (
    <div className="review-controls">
      <button
        className="button-secondary"
        disabled={refresh.isPending}
        onClick={() => refresh.mutate()}
      >
        {refresh.isPending
          ? "Loading OpenF1 metadata…"
          : "Load OpenF1 metadata"}
      </button>
      {refresh.isError ? (
        <p role="alert">
          OpenF1 metadata could not be loaded. Try again shortly.
        </p>
      ) : refresh.isSuccess ? (
        <small>Metadata check complete.</small>
      ) : null}
    </div>
  );
}

function usePrepareLap(choice: LapChoice | undefined, enabled: boolean) {
  const request = {
    entryIds: choice ? [choice.entry_id] : [],
    scope: "lap" as const,
    lapNumber: choice?.lap_number,
    enabled: enabled && Boolean(choice),
  };
  const car = useTelemetryMaterializationReadiness({ ...request, kind: "car" });
  const position = useTelemetryMaterializationReadiness({
    ...request,
    kind: "position",
  });
  return {
    ready: Boolean(choice) && car.ready && position.ready,
    failed: car.isError || position.isError,
  };
}

function SegmentReview({ cards }: { cards: DriverCard[] }) {
  const { lapSelection, entries } = useSessionWorkspace();
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [prepare, setPrepare] = useState(false);
  const choices = cards.flatMap((card) => {
    const laps = new Map<number, string>();
    if (typeof lapSelection === "number")
      laps.set(lapSelection, `Selected · Lap ${lapSelection}`);
    for (const row of card.qualifying)
      if (row.lap_number != null)
        laps.set(row.lap_number, `Q${row.phase} · Lap ${row.lap_number}`);
    if (
      card.best_clean_lap_number != null &&
      !laps.has(card.best_clean_lap_number)
    )
      laps.set(
        card.best_clean_lap_number,
        `Best clean · Lap ${card.best_clean_lap_number}`,
      );
    for (const number of [...card.recent_clean_lap_numbers].reverse()) {
      if (!laps.has(number)) laps.set(number, `Recent clean · Lap ${number}`);
    }
    return [...laps].map(([lap_number, label]) => ({
      value: `${card.entry_id}:${lap_number}`,
      label,
      entry_id: card.entry_id,
      lap_number,
    }));
  });
  const a = choices.find((choice) => choice.value === first) ?? choices[0];
  const choiceOptions = choices.map((choice) => {
    const entry = entries.find((item) => item.id === choice.entry_id);
    return entry
      ? { ...driverOption(entry, choice.value), label: `${entry.driver_name || entry.driver_abbreviation} · ${choice.label}`, detail: choice.label }
      : { value: choice.value, label: choice.label };
  });
  const b =
    choices.find((choice) => choice.value === second && choice !== a) ??
    choices.find((choice) => choice.entry_id !== a?.entry_id);
  const readinessA = usePrepareLap(a, prepare),
    readinessB = usePrepareLap(b, prepare);
  const laps = [a, b]
    .filter((value) => value != null)
    .map(({ entry_id, lap_number }) => ({ entry_id, lap_number }));
  const query = useReviewQuery(
    ["segments"],
    laps,
    Boolean(a),
    undefined,
    prepare && readinessA.ready && (!b || readinessB.ready),
  );
  const supported = query.data?.groups.segments?.supported ?? 0;
  return (
    <>
      <div className="review-controls">
        <label>
          Focus lap{" "}
          <DriverSelect
            aria-label="Focus lap"
            value={a?.value ?? ""}
            onChange={(value) => {
              setFirst(value);
              setPrepare(false);
            }}
            options={choiceOptions}
          />
        </label>
        <label>
          Comparison lap{" "}
          <DriverSelect
            aria-label="Comparison lap"
            value={b?.value ?? ""}
            onChange={(value) => {
              setSecond(value);
              setPrepare(false);
            }}
            options={choiceOptions.filter((choice) => choice.value !== a?.value)}
            disabled={!b}
          />
        </label>
      </div>
      {!a ? (
        <p>Choose drivers with completed clean or qualifying laps.</p>
      ) : null}
      {a && !supported && query.data ? (
        <p>
          Matching lap telemetry needs preparation or lacks usable position
          coverage.
        </p>
      ) : null}
      {a && supported < laps.length && !prepare ? (
        <button className="button-secondary" onClick={() => setPrepare(true)}>
          Prepare chosen laps
        </button>
      ) : null}
      {prepare && (readinessA.failed || readinessB.failed) ? (
        <p role="alert">
          Telemetry preparation failed. Check the session data status.
        </p>
      ) : null}
      {prepare &&
      !readinessA.failed &&
      !readinessB.failed &&
      !(readinessA.ready && (!b || readinessB.ready)) ? (
        <p role="status">Preparing lap telemetry…</p>
      ) : null}
      {prepare &&
      readinessA.ready &&
      (!b || readinessB.ready) &&
      supported < laps.length ? (
        <button
          className="button-secondary"
          onClick={() => void query.refetch()}
        >
          Refresh segment comparison
        </button>
      ) : null}
      {query.isError ? (
        <button
          className="button-secondary"
          onClick={() => void query.refetch()}
        >
          Retry segment comparison
        </button>
      ) : null}
      {query.data?.groups.segments?.laps.map((lap) =>
        lap.segments.length ? (
          <div key={`${lap.entry_id}:${lap.lap_number}`}>
            <h4>
              {
                cards.find((card) => card.entry_id === lap.entry_id)
                  ?.abbreviation
              }{" "}
              · Lap {lap.lap_number} · {seconds(lap.lap_time_s, 3)}
            </h4>
            <div className="review-segment-grid">
              {lap.segments.map((segment) => (
                <details key={segment.segment} data-colour={segment.colour}>
                  <summary>
                    <small>{segment.segment}</small>
                    <strong>{seconds(segment.time_s)}</strong>
                  </summary>
                  <dl>
                    <dt>Gap to comparison best</dt>
                    <dd>{seconds(segment.delta_to_best_s)}</dd>
                    <dt>Change from prior median</dt>
                    <dd>{seconds(segment.delta_to_prior_median_s)}</dd>
                    <dt>Minimum sampled speed</dt>
                    <dd>{segment.min_speed_kph ?? "Unavailable"} km/h</dd>
                    <dt>Mean throttle</dt>
                    <dd>
                      {segment.mean_throttle_pct?.toFixed(0) ?? "Unavailable"}%
                    </dd>
                    <dt>Brake-on samples</dt>
                    <dd>
                      {segment.brake_sample_pct?.toFixed(0) ?? "Unavailable"}%
                    </dd>
                  </dl>
                </details>
              ))}
            </div>
          </div>
        ) : null,
      )}
      <small>{query.data?.groups.segments?.method}</small>
    </>
  );
}
function ProjectionControls({
  data,
  defaultUpdating,
  name,
}: {
  data?: ReviewData;
  defaultUpdating: boolean;
  name: (id: string) => string;
}) {
  const [horizon, setHorizon] = useState(5);
  const [fuel, setFuel] = useState(false);
  const custom = horizon !== 5 || fuel;
  const query = useReviewQuery(["pace"], [], custom, {
    horizon_laps: horizon,
    ...(fuel ? { fuel_burn_kg_per_lap: 1.5, fuel_time_s_per_kg: 0.03 } : {}),
  });
  const displayed = (custom ? query.data : undefined) ?? data;
  return (
    <>
      <ReviewSnapshotStatus
        data={displayed}
        updating={custom ? query.isFetching : defaultUpdating}
        showingDefault={custom && !query.data && Boolean(data)}
      />
      <div className="review-controls">
        <label>
          Projection horizon
          <select
            aria-label="Projection horizon"
            value={horizon}
            onChange={(event) => setHorizon(Number(event.target.value))}
          >
            {[1, 3, 5, 10, 20].map((value) => (
              <option key={value} value={value}>
                {value} laps
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>
            <input
              type="checkbox"
              aria-label="Fuel scenario"
              checked={fuel}
              onChange={(event) => setFuel(event.target.checked)}
            />{" "}
            Fuel scenario
          </span>
          <small>1.5 kg/lap × 0.03 s/kg</small>
        </label>
      </div>
      {displayed ? (
        <ReviewContent
          panelId="race-pace-forecast"
          groups={displayed.groups}
          name={name}
        />
      ) : null}
      {custom && query.isError ? (
        <button
          className="button-secondary"
          onClick={() => void query.refetch()}
        >
          Retry projection
        </button>
      ) : null}
    </>
  );
}

function RepairControls({
  data,
  defaultUpdating,
  name,
}: {
  data?: ReviewData;
  defaultUpdating: boolean;
  name: (id: string) => string;
}) {
  const [extra, setExtra] = useState(0);
  const hasReport = Boolean(
    data?.groups.incidents?.reports.some((row) => row.kind === "damage_report"),
  );
  const custom = hasReport && extra > 0;
  const query = useReviewQuery(["pit"], [], custom, {
    repair_extra_s: extra,
  });
  const displayed = (custom ? query.data : undefined) ?? data;
  return (
    <>
      <ReviewSnapshotStatus
        data={displayed}
        updating={custom ? query.isFetching : defaultUpdating}
        showingDefault={custom && !query.data && Boolean(data)}
      />
      {hasReport ? (
        <label>
          Extra repair time scenario{" "}
          <select
            value={extra}
            onChange={(event) => setExtra(Number(event.target.value))}
          >
            <option value={0}>No added repair time</option>
            {[3, 5, 8, 12].map((value) => (
              <option key={value} value={value}>
                +{value} s
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {displayed ? (
        <ReviewContent
          panelId="pit-benchmark"
          groups={displayed.groups}
          name={name}
        />
      ) : null}
      {custom && query.isError ? (
        <button
          className="button-secondary"
          onClick={() => void query.refetch()}
        >
          Retry pit scenario
        </button>
      ) : null}
    </>
  );
}

function ReviewSnapshotStatus({
  data,
  updating,
  showingDefault = false,
}: {
  data?: ReviewData;
  updating: boolean;
  showingDefault?: boolean;
}) {
  const { mode } = useSessionWorkspace();
  const timeLabel = useSessionTimeLabel();
  return (
    <div className="insight-context">
      <span>
        {mode === "simulation" ? "Replay" : "Lookback"}
        {data ? ` · ${timeLabel(data.as_of_ms)}` : ""}
      </span>
      <span
        className="snapshot-refresh-status"
        data-visible={updating || showingDefault}
      >
        {showingDefault
          ? updating
            ? "Updating · Default shown"
            : "Default shown"
          : "Updating"}
      </span>
    </div>
  );
}

export function ReviewWidget({
  panelId,
  options,
}: {
  panelId: ReviewPanelId;
  options?: Record<string, unknown>;
}) {
  const spec = reviewPanels[panelId];
  return (
    <WidgetCard title={typeof options?.title === "string" ? options.title : spec.title}>
      <div className="review-panel" data-review-panel={panelId}>
        <details className="insight-help">
          <summary>When to use this panel</summary>
          <p>{reviewPanelGuide[panelId]}</p>
        </details>
        {panelId === "team-radio" ? <RadioReview /> : (
          <SnapshotReview panelId={panelId} options={options} />
        )}
      </div>
    </WidgetCard>
  );
}

function RadioReview() {
  const query = useRadioTimelineQuery();
  const { sessionId } = useSessionWorkspace();
  if (query.isError) {
    return (
      <div role="alert">
        <p>Team radio could not be loaded.</p>
        <button type="button" className="button-secondary" onClick={() => void query.refetch()}>
          Retry team radio
        </button>
      </div>
    );
  }
  if (!query.data) return <p role="status">Loading team radio…</p>;
  return <TeamRadio key={sessionId} radio={query.data} />;
}

function SnapshotReview({ panelId, options }: {
  panelId: Exclude<ReviewPanelId, "team-radio">;
  options?: Record<string, unknown>;
}) {
  const query = useSessionReview();
  const workspace = useSessionWorkspace();
  const name = (id: string) => {
    const entry = workspace.entries.find((item) => item.id === id);
    return entry?.driver_abbreviation ?? entry?.driver_name ?? "Driver";
  };
  const data = query.data;
  const isProjection = panelId === "race-pace-forecast";
  const isPit = panelId === "pit-benchmark";
  return (
    <>
      {query.isError ? (
        <div role="alert">
          <p>Review data could not be loaded.</p>
          <button
            className="button-secondary"
            onClick={() => void query.refetch()}
          >
            Retry review
          </button>
        </div>
      ) : null}
      {!data && !query.isError ? (
        <p role="status">Loading session review…</p>
      ) : null}
      {isProjection ? (
        <ProjectionControls
          data={data}
          defaultUpdating={query.isFetching}
          name={name}
        />
      ) : isPit ? (
        <RepairControls
          data={data}
          defaultUpdating={query.isFetching}
          name={name}
        />
      ) : data ? (
        <>
          <ReviewSnapshotStatus data={data} updating={query.isFetching} />
          {panelId === "lookback-driver-cards" ? (
            <>
              <QualifyingDriverCards cards={data.groups.drivers ?? []} />
              {data.groups.drivers?.length &&
              data.groups.drivers.every(
                (card) => !card.headshot_url && !card.qualifying.length,
              ) ? (
                <LoadReviewMetadata />
              ) : null}
            </>
          ) : null}
          {panelId === "lap-segment-review" ? (
            <SegmentReview cards={data.groups.drivers ?? []} />
          ) : null}
          <ReviewContent
            panelId={panelId}
            groups={data.groups}
            name={name}
            contextId={
              typeof options?.contextId === "string"
                ? options.contextId || undefined
                : undefined
            }
          />
        </>
      ) : null}
    </>
  );
}
