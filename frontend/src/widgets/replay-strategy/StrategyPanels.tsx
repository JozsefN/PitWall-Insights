import type { CSSProperties } from "react";
import type {
  DriverStrategy,
  IncidentForecast,
  Neutralisation,
  ReplayStrategy,
} from "../../features/replay-strategy/replay-strategy.contracts";
import {
  useSessionTimeLabel,
  useSessionWorkspace,
} from "../../features/sessions/SessionWorkspaceContext";
import {
  formatLapTime,
  getEntryDisplayName,
} from "../../features/sessions/session-utils";
import { StrategySourcePanel } from "./StrategySourcePanel";
import { crossoverHeadline } from "../../features/replay-strategy/crossover-presentation";
import {
  getCompoundColor,
  getCompoundLabel,
} from "../telemetry/utils/stint-analysis";
import "./strategy-panels.css";

type Options = { options?: Record<string, unknown> };

const panelTitle = (options: Options["options"], fallback: string) =>
  typeof options?.title === "string" ? options.title : fallback;
const seconds = (value: number) => `${value.toFixed(1)} s`;
const signed = (value: number, digits = 2) =>
  `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
const pitEvidence = {
  circuit_adjusted_sector_archive: "prior races weighted toward this circuit",
  timing_sectors: "same-circuit stops measured at pit-adjacent sectors",
  same_circuit_sector_archive:
    "prior races with measured pit sectors at this circuit",
  pooled_sector_archive: "prior races with measured pit sectors",
  local_laps: "same-circuit laps",
  same_circuit_archive: "same-circuit races",
  pooled_archive: "earlier races across circuits",
};

export function StrategyCallWidget({ options }: Options) {
  return (
    <StrategySourcePanel
      title={panelTitle(options, "Strategy call")}
      driverFilter
    >
      {(data, driver) => driver && <DriverCall data={data} driver={driver} />}
    </StrategySourcePanel>
  );
}

function DriverCall({
  data,
  driver,
}: {
  data: ReplayStrategy;
  driver: DriverStrategy;
}) {
  const { entries } = useSessionWorkspace();
  const call = driver.call;
  const wet = data.crossover?.decisions[driver.entry_id];
  const earlyRival = driver.rivals?.find((item) => item.outlap?.uncertain_flip);
  const rival = entries.find((entry) => entry.id === call?.rival_context_id);
  const first = call?.best.stops[0];
  const alternative = call?.alternative?.stops[0];
  const pitPhasePlan = call?.best.pit_phase
    ? call.best
    : call?.alternative?.pit_phase
      ? call.alternative
      : undefined;
  const lap = driver.completed_laps;
  const end =
    data.total_laps == null
      ? lap + 1
      : lap + data.total_laps - data.leader_completed_laps;
  const headline =
    call?.action === "box"
      ? "Box this lap"
      : first
        ? `Stay out · box on lap ${first.lap}`
        : "Run to the finish";
  const tyres = [
    { lap, compound: driver.compound },
    ...(call?.best.stops ?? []),
  ];
  if (
    wet &&
    (!call ||
      wet.action === "box" ||
      wet.action === "wait" ||
      wet.action === "forecast_box")
  )
    return (
      <section
        className="strategy-call-card"
        data-action={wet.action.includes("box") ? "box" : "extend"}
      >
        <small>Weather crossover · {wet.laps}-lap view</small>
        <h4>{crossoverHeadline(wet)}</h4>
        <p>Tyre crossover shows the sector comparisons and pit options.</p>
      </section>
    );
  if (!call)
    return (
      <div className="strategy-unavailable">
        <h4>Waiting for a supported call</h4>
        <p>{driver.status ?? data.status}</p>
      </div>
    );
  return (
    <>
      <section className="strategy-call-card" data-action={call.action}>
        <small>
          {call.decision_sensitive ? "Close call" : "Fastest modelled plan"}
        </small>
        <h4>{headline}</h4>
        <p>
          {first
            ? `Fit a fresh ${getCompoundLabel(first.compound).toLowerCase()} set`
            : `${getCompoundLabel(driver.compound)} tyres to the flag`}
        </p>
      </section>
      {earlyRival ? (
        <p className="strategy-pit-phase">
          Possible rejoin opportunity from a rival’s latest out-lap split. Check
          the margin in Rival gaps &amp; lap comparison.
        </p>
      ) : null}
      {data.incident.pit_entry_closed ? (
        <p className="strategy-pit-phase">
          Pit entry closed. Later stops assume race control reopens it.
        </p>
      ) : null}
      {call.best.exit_lap_beyond_observed_age ? (
        <p className="strategy-call-note">
          Current tyres are at the observed age limit. This plan includes only
          the lap needed to reach the pits.
        </p>
      ) : null}
      <ol className="strategy-plan-strip" aria-label="Proposed stints">
        {tyres.map((stint, index) => {
          const lastLap = tyres[index + 1]?.lap ?? end;
          return (
            <li
              key={stint.lap}
              style={
                {
                  "--strategy-compound": getCompoundColor(stint.compound),
                  flexGrow: lastLap - stint.lap,
                } as CSSProperties
              }
              title={`${index ? "Fresh set" : "Current set"} · Laps ${stint.lap + 1}–${lastLap}`}
            >
              <b>{getCompoundLabel(stint.compound)}</b>
              <small>
                L{stint.lap + 1}–{lastLap}
              </small>
            </li>
          );
        })}
      </ol>
      <dl className="strategy-call-context">
        {call.pit_window ? (
          <div>
            <dt>Pit window</dt>
            <dd>
              {call.pit_window[0] === call.pit_window[1]
                ? `Lap ${call.pit_window[0]}`
                : `Laps ${call.pit_window.join("–")}`}
            </dd>
          </div>
        ) : null}
        {call.margin_s != null ? (
          <div>
            <dt>Edge over alternative</dt>
            <dd>
              {seconds(call.margin_s)}
              {call.margin_pct != null
                ? ` · ${call.margin_pct.toFixed(2)}%`
                : ""}
            </dd>
          </div>
        ) : null}
        {driver.gap_ahead_s != null ? (
          <div>
            <dt>Gap ahead</dt>
            <dd>{seconds(driver.gap_ahead_s)}</dd>
          </div>
        ) : null}
        {driver.rejoin_if_pit ? (
          <div>
            <dt>If pitting at current gaps</dt>
            <dd>
              P{driver.rejoin_if_pit.position} of{" "}
              {driver.rejoin_if_pit.timed_drivers} timed
            </dd>
          </div>
        ) : null}
      </dl>
      {call.incident_changed_call ? (
        <p className="strategy-call-note">
          Neutralisation changes the ranked plan. Green-flag baseline{" "}
          {call.green_best.stops.length
            ? `boxes on lap ${call.green_best.stops[0].lap}`
            : "stays out to the finish"}
          .
        </p>
      ) : null}
      {rival ? (
        <p className="strategy-call-note">
          Includes measured following loss if {getEntryDisplayName(rival)} stays
          out this lap.
        </p>
      ) : null}
      {pitPhasePlan?.pit_phase ? (
        <p className="strategy-pit-phase">
          {pitPhasePlan === call.alternative
            ? `Alternative pit on lap ${alternative?.lap} · `
            : ""}
          {pitPhasePlan.pit_phase.basis === "historical_phase"
            ? `At pit entry · ${Math.round(pitPhasePlan.pit_phase.sc_pct)}% SC · ${Math.round(pitPhasePlan.pit_phase.vsc_pct)}% VSC`
            : "Assumes the current intervention holds until pit entry"}
          {pitPhasePlan.neutralisation_saving_s > 0
            ? ` · ${seconds(pitPhasePlan.neutralisation_saving_s)} expected pit saving`
            : ""}
        </p>
      ) : null}
      <details>
        <summary>Assumptions and evidence</summary>
        {(call.best.warmup_s ?? 0) > 0.05 ? (
          <p>Fresh-tyre warm-up adds {seconds(call.best.warmup_s ?? 0)} across the planned stops.</p>
        ) : null}
        {call.alternative ? (
          <p>
            {alternative
              ? `Alternative first stop: lap ${alternative.lap}, ${getCompoundLabel(alternative.compound).toLowerCase()} tyres.`
              : "Alternative: keep the current set to the finish."}
          </p>
        ) : null}
        <p>
          {call.candidate_count} feasible first-stop variants · Decision
          sensitivity ±{seconds(call.sensitivity_s)}.
        </p>
        <p>
          {data.pit.median_s == null
            ? "Green pit loss is unavailable."
            : `Green pit loss ${seconds(data.pit.median_s)} from ${data.pit.sample_count} comparable stops${data.pit.green_basis === "whole_laps" ? "." : " measured between pit-adjacent timing sectors."}`}{" "}
          {call.best.neutralisation_saving_s > 0
            ? `Modelled first-stop saving ${seconds(call.best.neutralisation_saving_s)}.`
            : ""}
        </p>
        <p>
          Ranks by time to the flag. Check fresh-set stock and the event’s
          nominated compounds. Rejoin holds the timed field’s observed gaps
          fixed.
        </p>
        {data.pit.discount_basis &&
          Object.entries(data.pit.discount_basis).map(([phase, evidence]) => (
            <p key={phase}>
              {phase.toUpperCase()} pit discount uses {evidence.samples}{" "}
              {pitEvidence[evidence.scope]}.
            </p>
          ))}
      </details>
    </>
  );
}

const outcomes: Array<[Neutralisation, string]> = [
  ["sc", "Safety car"],
  ["vsc", "Virtual safety car"],
  ["red", "Red flag"],
  ["none", "No intervention"],
];

function RiskChart({ forecast }: { forecast: IncidentForecast }) {
  const sc = forecast.outcomes_pct.sc;
  return (
    <figure className="strategy-risk-chart">
      <figcaption>
        <strong>{Math.round(sc)}%</strong>
        <span>
          Safety car first
          <br />
          <small>Next {forecast.horizon_s / 60} minutes</small>
        </span>
      </figcaption>
      <div aria-hidden="true" className="strategy-risk-strip">
        {outcomes.map(([key]) => (
          <i
            key={key}
            data-outcome={key}
            style={{ width: `${forecast.outcomes_pct[key]}%` }}
          />
        ))}
      </div>
      <ul>
        {outcomes.map(([key, name]) => (
          <li key={key} data-outcome={key}>
            <i aria-hidden="true" />
            {name} <b>{Math.round(forecast.outcomes_pct[key])}%</b>
          </li>
        ))}
      </ul>
      <small>
        {forecast.episodes} similar episodes from {forecast.races} earlier races
        · {forecast.scope === "circuit" ? "Same circuit" : "Pooled circuits"} ·
        SC model interval {forecast.sc_interval_pct.map(Math.round).join("–")}%
        {forecast.reference_episodes
          ? ` · Pooled reference: ${forecast.reference_episodes} episodes`
          : null}
      </small>
    </figure>
  );
}

export function InterventionRiskWidget({ options }: Options) {
  return (
    <StrategySourcePanel
      title={panelTitle(options, "Race warnings & safety car")}
    >
      {(data) => <WarningFeed data={data} />}
    </StrategySourcePanel>
  );
}

function WarningFeed({ data }: { data: ReplayStrategy }) {
  const timeLabel = useSessionTimeLabel();
  const { entries } = useSessionWorkspace();
  const phase = data.incident.phase;
  const observed =
    phase === "4"
      ? "Safety car deployed"
      : phase === "6" || phase === "7"
        ? "Virtual safety car in effect"
        : phase === "5"
          ? "Race suspended"
          : undefined;
  const forecast = data.incident.forecast;
  const activeIndex = data.warnings.findIndex((warning) => warning.forecast);
  return (
    <>
      {observed ? <p className="strategy-active-flag">{observed}</p> : null}
      {data.incident.pit_entry_closed ? (
        <p className="strategy-active-flag">Pit entry closed</p>
      ) : null}
      {forecast ? (
        <RiskChart forecast={forecast} />
      ) : !observed ? (
        <p className="strategy-risk-status">
          {data.incident.episode_start_ms == null
            ? "No active race-control incident to assess."
            : "Too few comparable earlier incidents for a percentage."}
        </p>
      ) : null}
      {data.warnings.length ? (
        <ol className="strategy-warning-feed" aria-label="Recent race warnings">
          {data.warnings.map((warning, index) => {
            const drivers = warning.entry_ids
              .map((id) => entries.find((entry) => entry.id === id))
              .filter((entry) => entry != null);
            return (
              <li
                key={`${warning.time_ms}:${warning.kind}:${warning.entry_ids.join(",")}:${index}`}
              >
                <details>
                  <summary>
                    <time>{timeLabel(warning.time_ms)}</time>
                    <strong>
                      {warning.title}
                      {drivers.length
                        ? ` · ${drivers.map(getEntryDisplayName).join(" / ")}`
                        : ""}
                    </strong>
                    {index === activeIndex && forecast ? (
                      <b>{Math.round(forecast.outcomes_pct.sc)}% SC</b>
                    ) : null}
                  </summary>
                  <p>{warning.detail}</p>
                  <small>
                    {warning.source === "race_control"
                      ? "Race control"
                      : "Telemetry candidate · awaiting corroboration"}
                  </small>
                </details>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="strategy-risk-status">No recent incident warnings.</p>
      )}
    </>
  );
}

export function TyreOutlookWidget({ options }: Options) {
  return (
    <StrategySourcePanel
      title={panelTitle(options, "Tyre outlook")}
      driverFilter
    >
      {(data, driver) => {
        const profiles = Object.entries(data.compound_profiles);
        const scale = Math.max(
          1,
          ...profiles.map(([, profile]) => profile.observed_age),
          driver?.tyre_age ?? 0,
        );
        return (
          <>
            {driver?.tyre_age != null ? (
              <div className="strategy-current-tyre">
                <strong>
                  {getCompoundLabel(driver.compound)} · {driver.tyre_age} laps
                  old
                </strong>
                <span>
                  {driver.supported_laps_left == null
                    ? "Age estimate unavailable"
                    : `${driver.supported_laps_left} laps within observed age range`}
                </span>
              </div>
            ) : null}
            {profiles.length ? (
              <ul
                className="strategy-compounds"
                aria-label="Observed tyre age by compound"
              >
                {profiles.map(([compound, profile]) => (
                  <li key={compound}>
                    <div>
                      <strong>{getCompoundLabel(compound)}</strong>
                      <strong>{profile.observed_age} laps observed</strong>
                    </div>
                    <div className="strategy-age-track" aria-hidden="true">
                      <i
                        style={{
                          width: `${(profile.observed_age / scale) * 100}%`,
                          background: getCompoundColor(compound),
                        }}
                      />
                    </div>
                    <small>
                      {signed(profile.drift_s_lap, 3)} s/lap · {profile.runs}{" "}
                      clean long runs
                      {profile.practice_change_pct == null
                        ? ""
                        : ` · Practice start to end ${signed(profile.practice_change_pct)}%`}
                    </small>
                  </li>
                ))}
              </ul>
            ) : (
              <p>
                Needs comparable dry long runs. Import earlier same-circuit
                races or this weekend’s practice sessions to add evidence.
              </p>
            )}
            {driver?.stint.pace_s != null ? (
              <p>
                Current clean pace{" "}
                <strong>{formatLapTime(driver.stint.pace_s * 1000)}</strong>
                {driver.stint.current_change_pct != null
                  ? ` · Current set start to end ${signed(driver.stint.current_change_pct)}%`
                  : ""}
              </p>
            ) : null}
            {driver?.stint.persistent_loss_s_lap ? (
              <p className="strategy-call-note">
                Persistent pace loss{" "}
                {seconds(driver.stint.persistent_loss_s_lap)} per lap
                {driver.stint.loss_after_warning === "braking_anomaly"
                  ? " following a sampled braking anomaly"
                  : driver.stint.loss_after_warning
                    ? " following a contact report"
                    : " on this set"}
                .
              </p>
            ) : null}
            {driver?.stint.laps_to_one_percent_slower != null ? (
              <p>
                Projected <strong>+1% lap time</strong> in{" "}
                {driver.stint.laps_to_one_percent_slower} more laps at the
                fitted pace drift.
              </p>
            ) : null}
            <small>
              Age bars show the longest clean evidence in the model. Drift
              includes fuel, traffic and track evolution.
            </small>
          </>
        );
      }}
    </StrategySourcePanel>
  );
}
