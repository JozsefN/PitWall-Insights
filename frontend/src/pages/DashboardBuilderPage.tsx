import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PageContainer } from "../app/layout/PageContanier";
import {
  useLayoutsQuery,
  useDeleteLayoutMutation,
  useLayoutFavoritesQuery,
  useSetLayoutFavoriteMutation,
} from "../data/queries/layouts.queries";
import { resolveWorkspaceLayouts } from "../features/dashboards/layout-catalog";
import { LayoutPreview } from "../features/dashboards/LayoutPreview";
import { draftFromLayout } from "../features/dashboards/editor-model";
import { LayoutEditor } from "../features/dashboards/LayoutEditor";
import { FavoriteButton } from "../features/dashboards/FavoriteButton";
import type {
  LayoutRecord,
  DashboardAudience,
} from "../widgets/registry/widget.types";
import "./dashboard-builder-page.css";

const audiences: {
  id: DashboardAudience;
  label: string;
  description: string;
}[] = [
  {
    id: "session-lookback",
    label: "Lookback",
    description:
      "Compare laps, telemetry, and strategy across a completed session.",
  },
  {
    id: "live-race",
    label: "Live & replay",
    description:
      "Follow track position and race context as the session clock moves.",
  },
];

export function DashboardBuilderPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [source, setSource] = useState("all");
  const [editor, setEditor] = useState<{
    layout: LayoutRecord | null;
    copy: boolean;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const layoutsQuery = useLayoutsQuery();
  const favoritesQuery = useLayoutFavoritesQuery();
  const favoriteMutation = useSetLayoutFavoriteMutation();
  const deleteMutation = useDeleteLayoutMutation();
  const audience =
    audiences.find((item) => item.id === searchParams.get("audience")) ??
    audiences[0];
  const layouts = resolveWorkspaceLayouts(
    layoutsQuery.data,
    audience.id,
    favoritesQuery.data,
  );
  const visibleLayouts = layouts.filter(
    (layout) => source === "all" || layout.source === source,
  );
  const selectedLayout =
    visibleLayouts.find((layout) => layout.id === searchParams.get("layout")) ??
    visibleLayouts[0];

  function openEditor(layout: LayoutRecord | null = null, copy = false) {
    try {
      if (layout) draftFromLayout(layout, copy);
      setEditor({ layout, copy });
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "This layout cannot be opened in the editor.",
      );
    }
  }

  async function remove(layout: LayoutRecord) {
    if (
      !layout.storageId ||
      layout.source !== "user" ||
      !window.confirm(`Delete "${layout.name}"? This cannot be undone.`)
    )
      return;
    try {
      await deleteMutation.mutateAsync(layout.storageId);
      setNotice("Layout deleted.");
    } catch {
      setNotice("Could not delete the layout. Try again.");
    }
  }

  if (editor)
    return (
      <PageContainer size="wide">
        <LayoutEditor
          layout={editor.layout}
          audience={audience.id}
          copy={editor.copy}
          onClose={() => setEditor(null)}
          onSaved={(id) => {
            setEditor(null);
            setSearchParams(
              { audience: audience.id, layout: id },
              { replace: true },
            );
            setSource("all");
            setNotice("Layout saved to your profile.");
          }}
        />
      </PageContainer>
    );

  return (
    <PageContainer size="wide">
      <div className="builder-page">
        <header className="builder-hero">
          <div>
            <p className="builder-eyebrow">
              <span aria-hidden="true" />
              Your workspace, your perspective
            </p>
            <h1>Dashboard Builder</h1>
            <p>
              Your layouts, built around the way you read a race. Arrange
              widgets for telemetry, strategy, and replay, then open your view
              in any compatible session.
            </p>
          </div>
          <Link to="/sessions?view=explorer" className="button-secondary">
            Browse sessions <span aria-hidden="true">&#8599;</span>
          </Link>
        </header>
        <div className="builder-toolbar builder-toolbar--sticky">
          <button
            type="button"
            className="button-primary"
            onClick={() => openEditor()}
          >
            + New layout
          </button>
          <div
            className="builder-mode-switch"
            role="group"
            aria-label="Dashboard audience"
          >
            {audiences.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={audience.id === item.id}
                className={audience.id === item.id ? "is-active" : ""}
                onClick={() =>
                  setSearchParams({ audience: item.id }, { replace: true })
                }
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="builder-filter">
            <label htmlFor="builder-source">Show</label>
            <select
              id="builder-source"
              value={source}
              onChange={(event) => setSource(event.target.value)}
            >
              <option value="all">All layouts</option>
              <option value="builtin">Built-in layouts</option>
              <option value="user">Your layouts</option>
            </select>
          </div>
        </div>
        {notice ? (
          <p className="builder-query-state" role="status">
            {notice}
          </p>
        ) : null}
        {favoritesQuery.isError ? (
          <div className="builder-query-state" role="alert">
            Favorites could not be loaded.
            <button
              className="button-secondary"
              onClick={() => void favoritesQuery.refetch()}
            >
              Retry favorites
            </button>
          </div>
        ) : null}
        {layoutsQuery.isError ? (
          <div className="builder-query-state" role="alert">
            <span>
              We couldn't load your saved layouts. Built-in layouts are still
              available.
            </span>
            <button
              type="button"
              className="button-secondary"
              onClick={() => void layoutsQuery.refetch()}
            >
              Try again
            </button>
          </div>
        ) : layoutsQuery.isPending ? (
          <p className="builder-query-state" role="status">
            Loading your saved layouts...
          </p>
        ) : null}
        <section
          className="builder-library"
          aria-labelledby="builder-library-title"
        >
          <div className="builder-section-heading">
            <div>
              <h2 id="builder-library-title">
                Layout library <span>{visibleLayouts.length}</span>
              </h2>
              <p>
                {audience.description} Star favorites to show them first in
                Sessions.
              </p>
            </div>
          </div>
          {!visibleLayouts.length ? (
            <div className="builder-empty">
              <h3>
                {layoutsQuery.isPending
                  ? "Loading your layouts"
                  : layoutsQuery.isError
                    ? "Your layouts are unavailable"
                    : "A space for your perspective"}
              </h3>
              <p>
                Create a layout using the New layout button above, or start from
                a built-in template.
              </p>
              <button
                type="button"
                className="button-secondary"
                onClick={() => setSource("builtin")}
              >
                Explore built-in layouts
              </button>
            </div>
          ) : (
            <div className="builder-layout-grid">
              {visibleLayouts.map((layout) => (
                <article
                  key={layout.id}
                  className={`builder-layout-card${selectedLayout?.id === layout.id ? " is-selected" : ""}`}
                >
                  <div className="builder-card-actions">
                    <span>
                      {layout.source === "builtin"
                        ? "Factory layout"
                        : "Your layout"}
                    </span>
                    <FavoriteButton
                      name={layout.name}
                      favorite={
                        favoritesQuery.data?.includes(layout.id) ?? false
                      }
                      disabled={
                        favoriteMutation.isPending ||
                        favoritesQuery.isPending ||
                        favoritesQuery.isError
                      }
                      onToggle={() =>
                        favoriteMutation.mutate(
                          {
                            layoutId: layout.id,
                            favorite: !favoritesQuery.data?.includes(layout.id),
                          },
                          {
                            onError: () =>
                              setNotice(
                                "Could not update favorites. Try again.",
                              ),
                          },
                        )
                      }
                    />
                  </div>
                  <button
                    type="button"
                    className="builder-card-select"
                    aria-label={`Select ${layout.name}`}
                    aria-pressed={selectedLayout?.id === layout.id}
                    onClick={() =>
                      setSearchParams(
                        { audience: audience.id, layout: layout.id },
                        { replace: true },
                      )
                    }
                  >
                    <LayoutPreview config={layout.config} compact />
                    <span className="builder-layout-card__meta">
                      <span>{layout.config.sections.length} groups</span>
                      <span>
                        {selectedLayout?.id === layout.id ? "Selected" : ""}
                      </span>
                    </span>
                    <strong>{layout.name}</strong>
                    <span className="builder-layout-card__description">
                      {layout.description ?? "A custom session layout."}
                    </span>
                    {!layout.isValid ? (
                      <span className="builder-layout-card__warning">
                        Unavailable in sessions: {layout.invalidReason}
                      </span>
                    ) : null}
                  </button>
                  <div className="builder-card-actions">
                    {layout.source === "user" ? (
                      <>
                        <button
                          className="button-secondary"
                          type="button"
                          disabled={![1, 2].includes(layout.schemaVersion)}
                          onClick={() => openEditor(layout)}
                        >
                          Edit layout
                        </button>
                        <button
                          className="button-secondary"
                          type="button"
                          disabled={deleteMutation.isPending}
                          onClick={() => void remove(layout)}
                        >
                          Delete
                        </button>
                      </>
                    ) : (
                      <button
                        className="button-secondary"
                        type="button"
                        disabled={!layout.isValid}
                        onClick={() => openEditor(layout, true)}
                      >
                        Use template
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </PageContainer>
  );
}
