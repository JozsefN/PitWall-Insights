import { useState } from "react";
import { widgetCatalog } from "../../widgets/registry/widget.catalog";
import type {
  DashboardAudience,
  WidgetId,
} from "../../widgets/registry/widget.types";
import { WidgetBlueprint } from "../../widgets/shared/WidgetBlueprint";
import { TierBadge } from "./TierBadge";

export function WidgetLibrary({
  audience,
  target,
  onAdd,
}: {
  audience: DashboardAudience;
  target: string;
  onAdd: (id: WidgetId) => void;
}) {
  const [search, setSearch] = useState("");
  const [tier, setTier] = useState("all");
  const available = (
    Object.entries(widgetCatalog) as [
      WidgetId,
      (typeof widgetCatalog)[WidgetId],
    ][]
  ).filter(
    ([, widget]) =>
      widget.builderEnabled &&
      widget.supportedAudiences.includes(audience) &&
      `${widget.title} ${widget.description} ${widget.category}`
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
        {available.map(([id, widget]) => (
          <article
            key={id}
            className="editor-library__widget"
            draggable={widget.accessTier === 0}
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
            <small>
              Min {widget.sizing.minW} × {widget.sizing.minH}
              {(widget.sizing.minAspect ?? 0) >= 1 ? " · Wide shape" : " · Flexible shape"}
            </small>
            <button
              className="button-secondary"
              type="button"
              aria-label={`Add ${widget.title}`}
              disabled={widget.accessTier > 0}
              onClick={() => onAdd(id)}
            >
              + Add
            </button>
          </article>
        ))}
        {!available.length ? (
          <p role="status">
            No matching widgets. Try another search or access filter.
          </p>
        ) : null}
      </div>
    </aside>
  );
}
