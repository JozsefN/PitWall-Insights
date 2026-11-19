import { useState } from "react";
import type { DriverCard as ReviewDriver } from "../../features/session-review/contracts";
import { useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import {
  getEntryAccent,
  formatLapTime,
} from "../../features/sessions/session-utils";
import { widgetIds } from "../../features/dashboards/compatibility";
import { DriverCard } from "./DriverCardIdentity";

export function QualifyingDriverCards({ cards }: { cards: ReviewDriver[] }) {
  const { entries, selectedLayout, selectQualifyingLap, session } =
    useSessionWorkspace();
  const phasePrefix = /sprint|shootout/i.test(session.session_name) ? "SQ" : "Q";
  const [phase, setPhase] = useState(0);
  const phases = [1, 2, 3].filter((number) =>
    cards.some((card) => card.qualifying.some((lap) => lap.phase === number)),
  );
  const selected = phases.includes(phase) ? phase : 0;
  const visible = cards.flatMap((card) => {
    const times = card.qualifying.filter(
      (lap) => !selected || lap.phase === selected,
    );
    return selected && !times.length ? [] : [{ card, times }];
  });
  if (selected)
    visible.sort((a, b) => a.times[0].lap_time_s - b.times[0].lap_time_s);
  const scale = Math.max(
    1,
    Math.ceil(
      Math.max(
        0,
        ...visible.flatMap(({ times }) =>
          times.map((lap) => lap.gap_to_phase_best_s),
        ),
      ),
    ),
  );
  const byEntry = new Map(entries.map((entry) => [entry.id, entry]));
  const hasLapMap =
    !!selectedLayout &&
    widgetIds(selectedLayout.config).includes("qualifying-lap-map");
  if (!cards.length) return <p>No qualifying driver data is available.</p>;

  return (
    <>
      {phases.length ? (
        <div
          className="qualifying-card-tools"
          role="group"
          aria-label="Qualifying phase"
        >
          {[0, ...phases].map((number) => (
            <button
              key={number}
              type="button"
              className="button-secondary"
              aria-pressed={number === selected}
              onClick={() => setPhase(number)}
            >
              {number ? `${phasePrefix}${number}` : "All phases"}
            </button>
          ))}
          <small>Gap to phase best · 0–{scale} s</small>
        </div>
      ) : null}
      <div className="driver-card-grid">
        {visible.map(({ card, times }) => {
          const entry = byEntry.get(card.entry_id);
          return (
            <DriverCard
              key={card.entry_id}
              className="qualifying-driver-card"
              identity={{
                entryId: card.entry_id,
                carNumber: card.car_number,
                name: card.name ?? card.abbreviation ?? `#${card.car_number}`,
                team: card.team,
                accent: entry ? getEntryAccent(entry) : "var(--color-focus)",
                headshot: card.headshot_url,
              }}
            >
              {times.length ? (
                times.map((lap) => (
                  <div
                    key={lap.phase}
                    className="qualifying-card-lap review-phase"
                    data-phase={lap.phase}
                  >
                    <strong>{phasePrefix}{lap.phase}</strong>
                    <span>{formatLapTime(lap.lap_time_s * 1000)}</span>
                    <small>
                      {lap.gap_to_phase_best_s === 0
                        ? "Fastest"
                        : `+${lap.gap_to_phase_best_s.toFixed(3)} s`}
                    </small>
                    <div
                      className="qualifying-card-lap__gap"
                      aria-hidden="true"
                    >
                      <i
                        style={{
                          width: `${(100 * lap.gap_to_phase_best_s) / scale}%`,
                        }}
                      />
                    </div>
                    {lap.provider_colours.some((sector) => sector.length) ? (
                      <div
                        className="review-microsectors"
                        aria-label={`${phasePrefix}${lap.phase} recorded minisector colours`}
                      >
                        {lap.provider_colours.map((sector, index) => (
                          <div key={index}>
                            {sector.map((colour, i) => (
                              <i
                                key={i}
                                data-colour={colour}
                                title={`Sector ${index + 1}, segment ${i + 1}: ${colour}`}
                              />
                            ))}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {lap.lap_number != null && hasLapMap ? (
                      <button
                        type="button"
                        className="button-secondary qualifying-card-lap__open"
                        onClick={(event) => {
                          if (lap.lap_number == null) return;
                          selectQualifyingLap({
                            entry_id: card.entry_id,
                            lap_number: lap.lap_number,
                          });
                          const map = event.currentTarget
                            .closest(".dashboard")
                            ?.querySelector(
                              '[data-widget="qualifying-lap-map"]',
                            );
                          map?.scrollIntoView({ block: "start" });
                          map?.querySelector("select")?.focus({ preventScroll: true });
                        }}
                      >
                        Inspect lap {lap.lap_number}
                      </button>
                    ) : null}
                  </div>
                ))
              ) : (
                <p>
                  {card.best_clean_lap_s == null ? (
                    "No comparable timed lap"
                  ) : (
                    <>
                      Best clean lap{" "}
                      <strong>
                        {formatLapTime(card.best_clean_lap_s * 1000)}
                      </strong>
                    </>
                  )}
                </p>
              )}
            </DriverCard>
          );
        })}
      </div>
    </>
  );
}
