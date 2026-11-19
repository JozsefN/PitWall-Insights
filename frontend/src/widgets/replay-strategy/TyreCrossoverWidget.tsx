import type { CSSProperties, FormEvent } from "react";
import type {
  CrossoverDecision,
  ReplayStrategy,
  TyreFamily,
} from "../../features/replay-strategy/replay-strategy.contracts";
import { useStrategyReplay } from "../../features/replay-strategy/strategy-replay-context";
import {
  crossoverHeadline,
  crossoverTyreNames as names,
} from "../../features/replay-strategy/crossover-presentation";
import { useSessionTimeLabel } from "../../features/sessions/SessionWorkspaceContext";
import { getCompoundLabel } from "../telemetry/utils/stint-analysis";
import { StrategySourcePanel } from "./StrategySourcePanel";

const colors: Record<TyreFamily, string> = {
  SLICK: "var(--color-focus)",
  INTERMEDIATE: "#4ab676",
  WET: "#629de8",
};
const families: TyreFamily[] = ["SLICK", "INTERMEDIATE", "WET"];
const seconds = (delta: number) => `${Math.abs(delta).toFixed(1)} s`;

export function TyreCrossoverWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  return (
    <StrategySourcePanel
      title={
        typeof options?.title === "string" ? options.title : "Tyre crossover"
      }
      driverFilter
    >
      {(data, driver) => (
        <Crossover
          data={data}
          decision={
            driver ? data.crossover?.decisions[driver.entry_id] : undefined
          }
        />
      )}
    </StrategySourcePanel>
  );
}

function Crossover({
  data,
  decision,
}: {
  data: ReplayStrategy;
  decision?: CrossoverDecision;
}) {
  const clock = useSessionTimeLabel();
  const { setRainScenario } = useStrategyReplay();
  const crossover = data.crossover;

  function runScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const start = data.as_of_ms + Number(fields.get("arrival")) * 60_000;
    setRainScenario({
      issued_at_ms: data.as_of_ms,
      starts_at_ms: start,
      ends_at_ms: start + Number(fields.get("duration")) * 60_000,
      probability_pct: Number(fields.get("chance")),
      intensity: fields.get("intensity") === "heavy" ? "heavy" : "rain",
    });
  }

  return (
    <>
      <div
        className="crossover-field"
        aria-label="Current tyres across the field"
      >
        {families.map((family) => (
          <span
            key={family}
            style={{ "--compound": colors[family] } as CSSProperties}
          >
            <strong>{crossover?.field[family] ?? 0}</strong> {names[family]}
          </span>
        ))}
      </div>
      {crossover?.forecast ? (
        <p className="strategy-pit-phase">
          Scenario · {crossover.forecast.probability_pct}% chance of{" "}
          {crossover.forecast.intensity === "heavy" ? "heavy rain" : "rain"} at{" "}
          {clock(crossover.forecast.starts_at_ms)}
        </p>
      ) : null}
      {crossover?.grip.length ? (
        <div className="crossover-sectors" aria-label="Latest slick pace loss">
          {crossover.grip.map((sector) => (
            <span key={sector.sector}>
              S{sector.sector} slick pace loss {seconds(sector.slowdown_s)} ·{" "}
              {sector.drivers} drivers
            </span>
          ))}
        </div>
      ) : null}
      {decision ? (
        <>
          <section
            className="strategy-call-card"
            data-action={decision.action.includes("box") ? "box" : "extend"}
          >
            <small>
              {decision.laps}-lap comparison ·{" "}
              {getCompoundLabel(decision.compound)} fitted
            </small>
            <h4>{crossoverHeadline(decision)}</h4>
            {decision.pit_cost_s != null && decision.action !== "closed" ? (
              <p>Estimated pit cost {seconds(decision.pit_cost_s)}</p>
            ) : null}
          </section>
          {decision.options.length ? (
            <ul
              className="rival-action-list"
              aria-label="Crossover tyre options"
            >
              {decision.options.map((option) => (
                <li
                  key={option.target}
                  data-preferred={option.target === decision.target}
                >
                  <div>
                    <strong>{names[option.target]}</strong>
                    <b>
                      {option.box_s == null
                        ? "Box unavailable"
                        : `Box now · ${seconds(option.box_s)} ${option.box_s >= 0 ? "gain" : "loss"}`}
                    </b>
                  </div>
                  <small>
                    {option.sectors.length
                      ? `${option.scouts} on ${names[option.target].toLowerCase()} · ${option.references} on ${option.reference_compound ? getCompoundLabel(option.reference_compound).toLowerCase() + " tyres" : "the current tyre family"}`
                      : `${option.historical_races} earlier races · conditional estimate`}
                  </small>
                  {option.sectors.length ? (
                    <div
                      className="crossover-sectors"
                      aria-label="Matched sector differences"
                    >
                      {option.sectors.map((sector) => (
                        <span key={sector.sector} data-gain={sector.gain_s > 0}>
                          <b>S{sector.sector}</b> {seconds(sector.gain_s)}{" "}
                          {sector.gain_s >= 0 ? "faster" : "slower"}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {option.wait_s != null ? (
                    <small>
                      Box next lap · {seconds(option.wait_s)}{" "}
                      {option.wait_s >= 0 ? "gain" : "loss"} vs staying out
                    </small>
                  ) : null}
                  {option.earlier_switch_s != null ? (
                    <small>
                      {option.earlier_switch_s >= 0
                        ? "Switching now"
                        : "Waiting a lap"}{" "}
                      gains {seconds(option.earlier_switch_s)} if both options
                      include a stop.
                    </small>
                  ) : null}
                  {option.warmup_s != null ? (
                    <small>
                      Measured S2–S3 warm-up · {seconds(option.warmup_s)}{" "}
                      {option.warmup_included
                        ? "charged once"
                        : "covered by the whole-lap pit estimate"}
                    </small>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p>Waiting for comparable sectors on another tyre.</p>
          )}
        </>
      ) : (
        <p>
          {crossover?.active
            ? "Waiting for sector timing and a confirmed fitted tyre."
            : "Crossover timing appears when rain or mixed tyre use is recorded."}
        </p>
      )}
      <details>
        <summary>Test an incoming rain scenario</summary>
        <form className="crossover-form" onSubmit={runScenario}>
          <label>
            Rain begins in{" "}
            <select name="arrival" defaultValue="2">
              <option value="1">1 minute</option>
              <option value="2">2 minutes</option>
              <option value="3">3 minutes</option>
            </select>
          </label>
          <label>
            Duration{" "}
            <select name="duration" defaultValue="4">
              <option value="2">2 minutes</option>
              <option value="4">4 minutes</option>
              <option value="8">8 minutes</option>
            </select>
          </label>
          <label>
            Chance (%){" "}
            <input
              name="chance"
              type="number"
              min="0"
              max="100"
              defaultValue="80"
              required
            />
          </label>
          <label>
            Intensity{" "}
            <select name="intensity">
              <option value="rain">Rain</option>
              <option value="heavy">Heavy rain</option>
            </select>
          </label>
          <small>Uses your forecast assumptions and earlier races.</small>
          <div>
            <button type="submit" className="button-secondary">
              Apply scenario
            </button>
            {crossover?.forecast ? (
              <button
                type="button"
                className="button-secondary"
                onClick={() => setRainScenario(null)}
              >
                Clear scenario
              </button>
            ) : null}
          </div>
        </form>
      </details>
    </>
  );
}
