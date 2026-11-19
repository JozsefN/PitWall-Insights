import { DriverSelect } from "../../components/DriverSelect";
import { driverOption } from "../../components/driver-select-options";
import { useState, type CSSProperties } from "react";
import type {
  DriverStrategy,
  RivalScenario,
} from "../../features/replay-strategy/replay-strategy.contracts";
import { useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import { getEntryDisplayName } from "../../features/sessions/session-utils";
import { getCompoundLabel } from "../telemetry/utils/stint-analysis";
import { StrategySourcePanel } from "./StrategySourcePanel";

type Options = { options?: Record<string, unknown> };
const signed = (value: number) =>
  `${value > 0 ? "+" : ""}${value.toFixed(2)} s`;

function gapLabel(gap: number) {
  return Math.abs(gap) < 0.05
    ? "Level"
    : `${Math.abs(gap).toFixed(1)} s ${gap > 0 ? "behind" : "ahead"}`;
}

function useRivalName() {
  const { entries } = useSessionWorkspace();
  const map = new Map(
    entries.map((entry) => [entry.id, getEntryDisplayName(entry)]),
  );
  return (id: string) => map.get(id) ?? "Driver";
}

export function RivalComparisonWidget({ options }: Options) {
  return (
    <StrategySourcePanel
      title={
        typeof options?.title === "string"
          ? options.title
          : "Rival gaps & lap comparison"
      }
      driverFilter
    >
      {(_, driver) => driver && <RivalComparison driver={driver} />}
    </StrategySourcePanel>
  );
}

function RivalComparison({ driver }: { driver: DriverStrategy }) {
  const { entries } = useSessionWorkspace();
  const [rivalId, setRival] = useState("");
  const name = useRivalName();
  const rivals = driver.rivals ?? [];
  const rival = rivals.find((row) => row.entry_id === rivalId) ?? rivals[0];
  if (!rival)
    return (
      <p>
        No supported rivals at this replay time. Waiting for comparable laps or
        fresh race gaps.
      </p>
    );
  const comparison = rival.comparison;
  const scale = Math.max(
    0.1,
    ...(comparison?.sectors.map((sector) => Math.abs(sector.delta_s ?? 0)) ??
      []),
  );
  return (
    <>
      <label className="rival-select">
        Rival{" "}
        <DriverSelect
          className="strategy-driver-select"
          aria-label="Rival comparison driver"
          value={rival.entry_id}
          onChange={setRival}
          options={rivals.map((row) => {
            const entry = entries.find((item) => item.id === row.entry_id);
            return entry
              ? driverOption(entry)
              : { value: row.entry_id, label: name(row.entry_id) };
          })}
        />
      </label>
      <dl className="strategy-call-context">
        <div>
          <dt>Current gap to {name(rival.entry_id)}</dt>
          <dd>{rival.gap_s == null ? "Unavailable" : gapLabel(rival.gap_s)}</dd>
        </div>
        {rival.pre_pit_gap_s != null ? (
          <div>
            <dt>Before the recent stop</dt>
            <dd>{gapLabel(rival.pre_pit_gap_s)}</dd>
          </div>
        ) : null}
        {rival.championship_before ? (
          <div>
            <dt>Rival before the race</dt>
            <dd>
              P{rival.championship_before[0]} in the championship
              {rival.championship_before[1] != null
                ? ` · ${rival.championship_before[1]} pts`
                : ""}
            </dd>
          </div>
        ) : null}
        {rival.grid_gap != null ? (
          <div>
            <dt>Starting grid difference</dt>
            <dd>{rival.grid_gap} places</dd>
          </div>
        ) : null}
      </dl>
      {rival.outlap ? (
        <section
          className="strategy-pit-phase"
          aria-label="Early out-lap timing"
        >
          <strong>
            {name(rival.entry_id)} · Out-lap S{rival.outlap.sector}
          </strong>
          <p>
            {rival.outlap.split_s.toFixed(3)} s on{" "}
            {getCompoundLabel(rival.outlap.compound).toLowerCase()} tyres
            {rival.outlap.loss_s != null
              ? ` · ${signed(rival.outlap.loss_s)} vs ${rival.outlap.peers} nearby drivers`
              : ""}
          </p>
          {rival.outlap.typical_warmup_s != null ? (
            <small>
              Typical same-tyre warm-up in this sector ·{" "}
              {signed(rival.outlap.typical_warmup_s)}
            </small>
          ) : null}
          {rival.outlap.rejoin_margin_s != null &&
          rival.outlap.projected_rejoin_margin_s != null ? (
            <p>
              Box at current gaps · {gapLabel(-rival.outlap.rejoin_margin_s)}.
              With estimated remaining out-lap loss ·{" "}
              {gapLabel(-rival.outlap.projected_rejoin_margin_s)}.
            </p>
          ) : null}
        </section>
      ) : null}
      {comparison ? (
        <section
          className="rival-lap-compare"
          aria-label="Recent sector differences"
        >
          <div>
            <strong>
              {name(driver.entry_id)} vs {name(rival.entry_id)} ·{" "}
              {signed(comparison.lap_delta_s)} per lap
            </strong>
            <small>
              {comparison.laps} matched laps through lap {comparison.last_lap} ·
              negative is faster
            </small>
          </div>
          <div className="rival-sector-grid">
            {comparison.sectors.map((sector, index) => (
              <div className="rival-sector" key={index}>
                <strong>S{index + 1}</strong>
                <b>{sector.delta_s == null ? "—" : signed(sector.delta_s)}</b>
                {sector.delta_s != null ? (
                  <div
                    className="rival-sector-track"
                    data-gain={sector.delta_s < 0}
                    aria-hidden="true"
                    style={
                      {
                        "--rival-delta": `${(Math.abs(sector.delta_s) / scale) * 50}%`,
                      } as CSSProperties
                    }
                  >
                    <i />
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : (
        <p>
          Sector comparisons need three clean laps by both drivers on the same
          race laps.
        </p>
      )}
      <small>
        Rival order weighs recent pace and proximity most. A close pre-pit gap
        is retained through the pit cycle.
      </small>
    </>
  );
}

const assumptions: Record<RivalScenario["assumption"], string> = {
  holds: "Stays out this lap",
  boxes: "Pits this lap",
  finishes: "Runs to the flag",
};
const actions = {
  box: "Box this lap",
  extend: "Extend the stint",
  finish: "Stay out to finish",
};

export function RivalPitScenariosWidget({ options }: Options) {
  return (
    <StrategySourcePanel
      title={
        typeof options?.title === "string"
          ? options.title
          : "Rival pit scenarios"
      }
      driverFilter
    >
      {(_, driver) => driver && <RivalPitScenarios driver={driver} />}
    </StrategySourcePanel>
  );
}

function RivalPitScenarios({ driver }: { driver: DriverStrategy }) {
  const { entries } = useSessionWorkspace();
  const [rivalId, setRival] = useState("");
  const [branch, setBranch] = useState<RivalScenario["assumption"]>("holds");
  const name = useRivalName();
  const matchups = driver.matchups ?? [];
  const matchup =
    matchups.find((item) => item.rival_entry_id === rivalId) ?? matchups[0];
  const scenario =
    matchup?.scenarios.find((item) => item.assumption === branch) ??
    matchup?.scenarios[0];
  if (!matchup || !scenario)
    return (
      <p>
        Needs a supported plan and a current timing gap for both drivers before
        it can compare pit options.
      </p>
    );
  return (
    <>
      <div className="rival-scenario-controls">
        <label className="rival-select">
          Rival{" "}
          <DriverSelect
            className="strategy-driver-select"
            aria-label="Rival for pit scenarios"
            value={matchup.rival_entry_id}
            onChange={setRival}
            options={matchups.map((item) => {
              const entry = entries.find(
                (row) => row.id === item.rival_entry_id,
              );
              return entry
                ? driverOption(entry)
                : {
                    value: item.rival_entry_id,
                    label: name(item.rival_entry_id),
                  };
            })}
          />
        </label>
        <label className="rival-select">
          Rival action{" "}
          <select
            className="strategy-driver-select"
            aria-label="Rival action"
            value={scenario.assumption}
            onChange={(event) =>
              setBranch(event.target.value as RivalScenario["assumption"])
            }
          >
            {matchup.scenarios.map((item) => (
              <option key={item.assumption} value={item.assumption}>
                {assumptions[item.assumption]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {matchup.slow_stop_window && scenario.assumption !== "boxes" ? (
        <p className="strategy-pit-phase">
          Recent{" "}
          {matchup.slow_stop_window.basis === "stationary"
            ? "stationary service"
            : "pit-lane visit"}{" "}
          was {matchup.slow_stop_window.excess_s.toFixed(1)} s longer than
          comparable stops. Box now to rejoin an estimated{" "}
          {matchup.slow_stop_window.margin_s.toFixed(1)} s ahead of this rival,
          versus {Math.abs(matchup.slow_stop_window.normal_margin_s).toFixed(1)}{" "}
          s behind with their usual stop.
        </p>
      ) : null}
      <p>
        {scenario.rival_first_stop
          ? `${name(matchup.rival_entry_id)}’s branch fits ${getCompoundLabel(scenario.rival_first_stop.compound).toLowerCase()} on lap ${scenario.rival_first_stop.lap}.`
          : `${name(matchup.rival_entry_id)} stays on the current set in this branch.`}
      </p>
      <ul className="rival-action-list" aria-label="Conditional pit options">
        {scenario.choices.map((choice) => (
          <li
            key={choice.action}
            data-preferred={choice.action === scenario.preferred_action}
          >
            <div>
              <strong>{actions[choice.action]}</strong>
              <b>
                {choice.cost_vs_best_s > 0.05
                  ? `${choice.cost_vs_best_s.toFixed(1)} s slower`
                  : "Quickest"}
              </b>
            </div>
            {choice.first_stop ? (
              <span>
                Lap {choice.first_stop.lap} ·{" "}
                {getCompoundLabel(choice.first_stop.compound)}
              </span>
            ) : null}
            <span>
              At the flag vs {name(matchup.rival_entry_id)} ·{" "}
              {gapLabel(-choice.finish_margin_s)}
            </span>
            {choice.positions_lost != null ? (
              <small>
                {choice.positions_lost > 0
                  ? `Rejoin ${choice.positions_lost} places lower`
                  : choice.positions_lost < 0
                    ? `Rejoin ${-choice.positions_lost} places higher`
                    : "Same rejoin position"}
              </small>
            ) : null}
            {choice.post_pit_pace_advantage_s != null ? (
              <small>
                {Math.abs(choice.post_pit_pace_advantage_s).toFixed(2)} s/lap{" "}
                {choice.post_pit_pace_advantage_s >= 0 ? "faster" : "slower"}{" "}
                than rival over up to three laps after the stop
              </small>
            ) : null}
            {choice.crossover_lap != null ? (
              <small>Timing crossover on lap {choice.crossover_lap}</small>
            ) : null}
            {choice.traffic_loss_s > 0.05 ? (
              <small>
                {choice.traffic_loss_s.toFixed(1)} s modelled following loss
              </small>
            ) : null}
          </li>
        ))}
      </ul>
      <small>
        Rejoin holds the rest of the field’s current gaps fixed. Crossover
        compares modelled lap times.
      </small>
    </>
  );
}
