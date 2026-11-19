import { DriverSelect } from "../../components/DriverSelect";
import { driverOption } from "../../components/driver-select-options";
import { useState, type CSSProperties } from "react";
import type {
  Benchmark,
  ReviewData,
} from "../../features/session-review/contracts";
import { useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import { getEntryAccent } from "../../features/sessions/session-utils";
import { seconds } from "./format";
import "./strategy-visuals.css";

type Name = (id: string) => string;
type Pace = NonNullable<ReviewData["groups"]["pace"]>;
type Pit = NonNullable<ReviewData["groups"]["pit"]>;
type Racecraft = NonNullable<ReviewData["groups"]["racecraft"]>;

export function FieldProjection({ pace, name }: { pace: Pace; name: Name }) {
  const [focus, setFocus] = useState("");
  const { entries } = useSessionWorkspace();
  const byId = new Map(entries.map((entry) => [entry.id, entry]));
  const timed = pace.field_projection.flatMap((row) =>
    row.projected_gap_s == null || row.order_among_projected_entries == null
      ? []
      : [
          {
            ...row,
            gap: row.projected_gap_s,
            place: row.order_among_projected_entries,
          },
        ],
  );
  const lapped = pace.field_projection.filter(
    (row) => row.laps_down_reported > 0,
  );
  const selected = timed.some((row) => row.entry_id === focus) ? focus : "";
  const max = Math.max(1, Math.ceil(Math.max(...timed.map((row) => row.gap))));
  if (!timed.length && !lapped.length)
    return (
      <p>
        Projection needs fresh green-flag timing and comparable completed race
        laps.
      </p>
    );

  return (
    <figure className="strategy-figure field-projection">
      <figcaption>
        <strong>Gap to projected leader</strong>
        {timed.length ? (
          <DriverSelect
            aria-label="Focus projected driver"
            value={selected}
            onChange={setFocus}
            options={[
              { value: "", label: "All projected drivers" },
              ...timed.map((row) => {
                const entry = byId.get(row.entry_id);
                return entry ? driverOption(entry) : { value: row.entry_id, label: name(row.entry_id) };
              }),
            ]}
          />
        ) : null}
      </figcaption>
      {timed.length ? <TimingAxis label="Seconds" end={max} /> : null}
      <ol className="strategy-timing-rows" aria-label="Projected order and gap">
        {timed
          .filter((row) => !selected || row.entry_id === selected)
          .map((row) => {
            const entry = byId.get(row.entry_id);
            return (
              <li
                className="strategy-timing-row"
                key={row.entry_id}
                data-highlight={row.entry_id === selected}
              >
                <span>
                  <b>P{row.place}</b> {name(row.entry_id)}
                </span>
                <div
                  className="strategy-timing-track"
                  aria-hidden="true"
                  style={
                    {
                      "--timing-point": pct(row.gap, max),
                      "--timing-colour": entry && getEntryAccent(entry),
                    } as CSSProperties
                  }
                >
                  <i />
                  <b />
                </div>
                <strong>
                  {row.place === 1 ? "Leader" : `+${seconds(row.gap)}`}
                </strong>
              </li>
            );
          })}
      </ol>
      {lapped.length ? (
        <details className="strategy-lapped">
          <summary>
            {lapped.length} {lapped.length === 1 ? "driver" : "drivers"}{" "}
            reported a lap down or more
          </summary>
          <ul className="review-list">
            {lapped.map((row) => (
              <li key={row.entry_id}>
                <strong>{name(row.entry_id)}</strong>
                <span>
                  {row.laps_down_reported}{" "}
                  {row.laps_down_reported === 1 ? "lap" : "laps"} down
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      <small>
        Scenario assumes each driver keeps their recent median pace.
      </small>
    </figure>
  );
}

export function RacePaceChart({
  rows,
  name,
}: {
  rows: Pace["drivers"];
  name: Name;
}) {
  const ordered = [...rows].sort((a, b) => a.median_pace_s - b.median_pace_s);
  const fastest = ordered[0];
  if (!fastest)
    return (
      <p>Comparable completed race laps are needed to compare median pace.</p>
    );
  const baseline = fastest.median_pace_s;
  const max = Math.max(
    0.2,
    Math.ceil((ordered[ordered.length - 1].median_pace_s - baseline) * 10) / 10,
  );
  return (
    <figure className="strategy-figure race-pace-chart">
      <figcaption>
        <strong>Recent median pace</strong>
        <small>
          {name(fastest.entry_id)} · {seconds(baseline, 3)} reference
        </small>
      </figcaption>
      <TimingAxis label="Seconds slower" end={max} />
      <ul
        className="strategy-timing-rows"
        aria-label="Median lap time compared with the fastest median"
      >
        {ordered.map((row) => {
          const delta = row.median_pace_s - baseline;
          return (
            <li className="strategy-timing-row" key={row.entry_id}>
              <span>
                {name(row.entry_id)} <small>{row.samples} laps</small>
              </span>
              <div
                className="strategy-timing-track"
                aria-hidden="true"
                style={{ "--timing-point": pct(delta, max) } as CSSProperties}
              >
                <i />
                <b />
              </div>
              <strong>{delta > 0 ? `+${seconds(delta, 3)}` : "Best"}</strong>
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

export function PitTimingProfile({ pit }: { pit: Pit }) {
  const rows: [string, Benchmark][] = [
    ["Net loss under green", pit.net_green_pit_loss],
    ["Time in pit lane", pit.pit_lane_duration],
    ["Stationary service", pit.stationary_service_duration],
  ];
  const max = Math.ceil(
    Math.max(
      1,
      ...rows.map(
        ([, row]) => (row.median_s ?? 0) + (row.robust_scatter_s ?? 0),
      ),
    ),
  );
  const hasTiming = rows.some(([, row]) => row.median_s != null);
  return (
    <figure className="strategy-figure pit-timing-profile">
      <figcaption>
        <strong>Comparable stops</strong>
        <small>Median and typical spread</small>
      </figcaption>
      {hasTiming ? <TimingAxis label="Seconds" end={max} /> : null}
      <ul className="strategy-timing-rows">
        {rows.map(([label, row]) => {
          const mid = row.median_s;
          const scatter = row.robust_scatter_s;
          return (
            <li className="pit-timing-row" key={label}>
              <div>
                <strong>{label}</strong>
                <strong>{mid == null ? "Unavailable" : seconds(mid)}</strong>
              </div>
              {mid != null ? (
                <div
                  className="strategy-timing-track"
                  aria-hidden="true"
                  style={
                    {
                      "--timing-point": pct(mid, max),
                      "--timing-low": pct(
                        Math.max(0, mid - (scatter ?? 0)),
                        max,
                      ),
                      "--timing-high": pct(mid + (scatter ?? 0), max),
                    } as CSSProperties
                  }
                >
                  <i />
                  <em />
                  <b />
                </div>
              ) : null}
              <small>
                {row.sample_count} {row.sample_count === 1 ? "stop" : "stops"} ·{" "}
                {row.session_ids.length}{" "}
                {row.session_ids.length === 1 ? "session" : "sessions"}
                {scatter == null
                  ? mid == null
                    ? " · needs 3 comparable stops"
                    : ""
                  : ` · typical spread ±${seconds(scatter)}`}
              </small>
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

export function PitRejoin({ pit, name }: { pit: Pit; name: Name }) {
  const { entries } = useSessionWorkspace();
  const [selected, setSelected] = useState("");
  const focus =
    pit.exit_scenarios.find((row) => row.entry_id === selected) ??
    pit.exit_scenarios[0];
  if (!focus)
    return (
      <p>
        Rejoin estimates need at least three comparable net-loss samples and
        fresh green-flag timing.
      </p>
    );

  return (
    <figure className="strategy-figure pit-rejoin-visual">
      <figcaption>
        <strong>If this driver pits now</strong>
        <DriverSelect
          aria-label="Pit rejoin driver"
          value={focus.entry_id}
          onChange={setSelected}
          options={pit.exit_scenarios.map((row) => {
            const entry = entries.find((item) => item.id === row.entry_id);
            return entry ? driverOption(entry) : { value: row.entry_id, label: name(row.entry_id) };
          })}
        />
      </figcaption>
      <ol
        className="pit-rejoin-grid"
        aria-label="Estimated rejoin position among timed drivers"
      >
        {Array.from({ length: focus.timed_entries }, (_, index) => {
          const place = index + 1;
          const rejoin = place === focus.exit_order_among_timed_entries;
          return (
            <li
              key={place}
              data-rejoin={rejoin}
              aria-label={`Position ${place}${rejoin ? ", estimated rejoin" : ""}`}
            >
              {place}
            </li>
          );
        })}
      </ol>
      <p>
        <strong>
          P{focus.exit_order_among_timed_entries} of {focus.timed_entries} timed
          drivers
        </strong>{" "}
        · {seconds(focus.projected_gap_to_current_leader_s)} behind the current
        leader’s timing
      </p>
      {focus.total_repair_stop_loss_s != null ? (
        <small>
          With assumed repair · {seconds(focus.total_repair_stop_loss_s)} total
          net loss. Position shown is for a standard stop.
        </small>
      ) : null}
      <small>Scenario holds other drivers’ gaps fixed.</small>
    </figure>
  );
}

export function BattleGaps({
  racecraft,
  name,
}: {
  racecraft: Racecraft;
  name: Name;
}) {
  const rows = racecraft.battles;
  const active = rows
    .filter((row) => row.active_battle || row.consistent_closing)
    .sort((a, b) => a.gap_s - b.gap_s);
  if (!active.length)
    return (
      <p>No pairs met the battle or sustained-closing criteria at this time.</p>
    );
  const battleGap = racecraft.close_following_threshold_s;
  const max =
    Math.ceil(
      Math.max(1, (battleGap ?? 0) * 1.25, ...active.map((row) => row.gap_s)) *
        10,
    ) / 10;
  return (
    <figure className="strategy-figure battle-gaps">
      <figcaption>
        <strong>Gap to the car ahead</strong>
        {battleGap != null ? (
          <small>Close following ≤ {seconds(battleGap, 1)}</small>
        ) : null}
      </figcaption>
      <TimingAxis label="Seconds" end={max} />
      <ul className="strategy-timing-rows">
        {active.map((row) => (
          <li className="pit-timing-row" key={row.follower_id}>
            <div>
              <strong>
                {name(row.follower_id)} → {name(row.ahead_id)}
              </strong>
              <strong>{seconds(row.gap_s)}</strong>
            </div>
            <div
              className="strategy-timing-track"
              aria-hidden="true"
              style={
                {
                  "--timing-point": pct(row.gap_s, max),
                  "--timing-threshold":
                    battleGap == null ? undefined : pct(battleGap, max),
                } as CSSProperties
              }
            >
              {battleGap != null ? <span /> : <i />}
              <b />
            </div>
            <small>
              {row.active_battle ? "Battle" : "Closing"}
              {row.active_battle && row.consistent_closing
                ? " · closing"
                : ""}{" "}
              · {row.sample_count} reports over {seconds(row.span_s, 0)}
              {row.pace_advantage_s_per_lap == null
                ? ""
                : ` · ${seconds(Math.abs(row.pace_advantage_s_per_lap))}/lap ${row.pace_advantage_s_per_lap >= 0 ? "faster" : "slower"}`}
            </small>
            {row.follower_compound || row.ahead_compound ? (
              <small>
                Tyres · {row.follower_compound ?? "Unknown"} /{" "}
                {row.ahead_compound ?? "Unknown"}
              </small>
            ) : null}
          </li>
        ))}
      </ul>
    </figure>
  );
}

export function RivalPitWindows({
  rows,
  name,
}: {
  rows: Pit["rival_windows"];
  name: Name;
}) {
  const visible = [...rows]
    .sort(
      (a, b) =>
        Number(b.position_flip_scenario) - Number(a.position_flip_scenario) ||
        Math.abs(a.exit_margin_s) - Math.abs(b.exit_margin_s),
    )
    .slice(0, 10);
  const max = Math.ceil(
    Math.max(
      1,
      ...visible.flatMap((row) => [
        Math.abs(row.exit_margin_s),
        Math.abs(row.normal_rival_stop_margin_s ?? 0),
      ]),
    ),
  );
  return (
    <details className="review-timing-evidence">
      <summary>Rival pit opportunities ({rows.length})</summary>
      <figure className="strategy-figure pit-rival-margins">
        <figcaption>
          <strong>Projected margin to rival</strong>
          <small>Each row uses the same seconds scale</small>
        </figcaption>
        <div className="pit-margin-axis" aria-hidden="true">
          <span>{max} s behind</span>
          <span>0</span>
          <span>{max} s ahead</span>
        </div>
        <ul className="strategy-timing-rows">
          {visible.map((row) => {
            const normal = row.normal_rival_stop_margin_s;
            return (
              <li
                className="pit-timing-row"
                key={`${row.entry_id}:${row.rival_entry_id}`}
              >
                <div>
                  <strong>
                    {name(row.entry_id)} vs {name(row.rival_entry_id)}
                  </strong>
                  {row.position_flip_scenario ? (
                    <small>Window opened</small>
                  ) : null}
                </div>
                <div
                  className="strategy-timing-track"
                  aria-hidden="true"
                  style={
                    {
                      "--timing-point": pct(max + row.exit_margin_s, 2 * max),
                      "--timing-normal":
                        normal == null ? undefined : pct(max + normal, 2 * max),
                    } as CSSProperties
                  }
                >
                  {normal != null ? <em /> : null}
                  <b />
                </div>
                <small>
                  Reported rival stop {marginLabel(row.exit_margin_s)}
                  {normal == null
                    ? ""
                    : ` · Typical rival stop ${marginLabel(normal)}`}
                </small>
              </li>
            );
          })}
        </ul>
        <small>
          Filled dot uses the reported stop. Ring uses the typical-stop
          scenario.
        </small>
      </figure>
    </details>
  );
}

function marginLabel(margin: number) {
  return `${seconds(Math.abs(margin))} ${margin >= 0 ? "ahead" : "behind"}`;
}

function TimingAxis({ label, end }: { label: string; end: number }) {
  return (
    <div className="strategy-timing-axis" aria-hidden="true">
      <div>
        <span>0</span>
        <span>{label}</span>
        <span>{Number(end.toFixed(1))}</span>
      </div>
    </div>
  );
}

function pct(value: number, max: number) {
  return `${(100 * value) / max}%`;
}
