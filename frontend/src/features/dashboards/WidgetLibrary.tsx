import { useState } from "react";
import { widgetCatalog } from "../../widgets/registry/widget.catalog";
import type {
  DashboardAudience,
  SessionKind,
  WidgetId,
} from "../../widgets/registry/widget.types";
import { WidgetBlueprint } from "../../widgets/shared/WidgetBlueprint";
import { TierBadge } from "./TierBadge";
import { Availability } from "./Availability";
import { widgetBlockReason } from "./compatibility";

export function WidgetLibrary({
  modes,
  compatibleKinds,
  target,
  onAdd,
}: {
  modes: DashboardAudience[];
  compatibleKinds: SessionKind[];
  target: string;
  onAdd: (id: WidgetId) => void;
}) {
  const [search, setSearch] = useState("");
  const [tier, setTier] = useState("all");
  const [showRestricted, setShowRestricted] = useState(false);
  const available = (
    Object.entries(widgetCatalog) as [
      WidgetId,
      (typeof widgetCatalog)[WidgetId],
    ][]
  ).filter(
    ([id, widget]) =>
      widget.builderEnabled &&
      (showRestricted ||
        search.trim() ||
        !widgetBlockReason(id, modes, compatibleKinds)) &&
      `${widget.title} ${widget.description} ${widget.category} ${(widget.searchTerms ?? []).join(" ")}`
        .toLowerCase()
        .includes(search.toLowerCase().trim()) &&
      (tier === "all" ||
        (tier === "free"
          ? widget.accessTier === 0
          : tier === "subscription"
            ? widget.accessTier > 0
            : widget.accessTier === Number(tier))),
  );
  return (
    <aside className="editor-library" aria-label="Widget library">
      <h3>Widget library</h3>
      <p>Drag to any group, or use Add.</p>
      <label>
        Search widgets
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Pace, map, telemetry..."
        />
      </label>
      <label className="editor-compatibility-filter">
        <input
          type="checkbox"
          checked={showRestricted}
          onChange={(event) => setShowRestricted(event.target.checked)}
        />{" "}
        Show restricted panels
      </label>
      <label>
        Widget access
        <select
          aria-label="Widget access"
          value={tier}
          onChange={(event) => setTier(event.target.value)}
        >
          <option value="all">All access levels</option>
          <option value="free">Free</option>
          <option value="subscription">Subscription</option>
          <option value="1">Tier 1</option>
          <option value="2">Tier 2</option>
          <option value="3">Tier 3</option>
        </select>
      </label>
      <small>All current analysis widgets are free.</small>
      <p className="editor-library__target">
        Add destination: <strong>{target}</strong>
      </p>
      <div className="editor-library__list">
        {available.map(([id, widget]) => {
          const blocked = widgetBlockReason(id, modes, compatibleKinds);
          return (
            <article
              key={id}
              className="editor-library__widget"
              data-blocked={Boolean(blocked)}
              draggable={!blocked && widget.accessTier === 0}
              onDragStart={(event) => {
                event.dataTransfer.setData("application/x-pitwall-widget", id);
                event.dataTransfer.effectAllowed = "copy";
              }}
            >
              <div>
                <strong>{widget.title}</strong>
                <TierBadge tier={widget.accessTier} />
              </div>
              <div className="editor-library__thumbnail">
                <WidgetBlueprint widgetId={id} width={480} height={220} />
              </div>
              <p>{widget.description}</p>
              <Availability
                modes={widget.supportedAudiences}
                kinds={widget.sessionKinds ?? []}
              />
              <small>{widget.availabilityNote}</small>
              {blocked ? (
                <p className="layout-availability-message">{blocked}</p>
              ) : null}
              <small>
                Min {widget.sizing.minW} × {widget.sizing.minH}
                {(widget.sizing.minAspect ?? 0) >= 1
                  ? " · Wide shape"
                  : " · Flexible shape"}
              </small>
              <button
                className="button-secondary"
                type="button"
                aria-label={`Add ${widget.title}`}
                disabled={Boolean(blocked) || widget.accessTier > 0}
                onClick={() => onAdd(id)}
              >
                + Add
              </button>
            </article>
          );
        })}
        {!available.length ? (
          <p role="status">
            No matching widgets. Change the filters or show restricted panels.
          </p>
        ) : null}
      </div>
    </aside>
  );
}
