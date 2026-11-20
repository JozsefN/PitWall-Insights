import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PageContainer } from "../app/layout/PageContanier";
import {
  useLayoutsQuery,
  useDeleteLayoutMutation,
  useLayoutFavoritesQuery,
  useSetLayoutFavoriteMutation,
} from "../data/queries/layouts.queries";
import { resolveWorkspaceLayouts } from "../features/dashboards/layout-catalog";
import { useMembership } from "../data/queries/billing.queries";
import { layoutPlanRestriction } from "../features/dashboards/plan-access";
import { LayoutPreview } from "../features/dashboards/LayoutPreview";
import { draftFromLayout } from "../features/dashboards/editor-model";
import { LayoutEditor } from "../features/dashboards/LayoutEditor";
import { FavoriteButton } from "../features/dashboards/FavoriteButton";
import { Availability } from "../features/dashboards/Availability";
import {
  getLayoutGuide,
  recommendedLayoutId,
} from "../features/dashboards/layout-guides";
import {
  layoutModes,
  sessionKindLabel,
  sessionKinds,
  supportedSessionKinds,
  widgetIds,
} from "../features/dashboards/compatibility";
import type {
  LayoutRecord,
  DashboardAudience,
  SessionKind,
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
    description: "Review laps and telemetry after the session.",
  },
  {
    id: "live-race",
    label: "Replay",
    description: "Follow timing and telemetry as the replay clock moves.",
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
  const [preview, setPreview] = useState<LayoutRecord | null>(null);
  const layoutsQuery = useLayoutsQuery();
  const plan = useMembership().data?.plan;
  const layoutCount = layoutsQuery.data?.length ?? 0;
  const slotsFull = Boolean(plan && layoutCount >= plan.saved_layouts);
  const favoritesQuery = useLayoutFavoritesQuery();
  const favoriteMutation = useSetLayoutFavoriteMutation();
  const deleteMutation = useDeleteLayoutMutation();
  const audience =
    audiences.find((item) => item.id === searchParams.get("audience")) ??
    audiences[0];
  const selectedId = searchParams.get("layout");
  const kindParam = searchParams.get("sessionKind");
  const sessionKind =
    sessionKinds.find((kind) => kind === kindParam) ??
    (kindParam === "all" || selectedId ? undefined : "race");
  const layouts = resolveWorkspaceLayouts(
    layoutsQuery.data,
    audience.id,
    favoritesQuery.data,
    sessionKind,
  );
  const visibleLayouts = layouts.filter(
    (layout) =>
      (source === "all" || layout.source === source) &&
      (!sessionKind ||
        layout.id === selectedId ||
        supportedSessionKinds(
          widgetIds(layout.config),
          layout.config.sessionKind,
        ).includes(sessionKind)),
  ).map(layout => ({ ...layout, planRestriction: layoutPlanRestriction(layout, plan, layoutsQuery.data) }));
  const selectedLayout = visibleLayouts.find(
    (layout) => layout.id === selectedId,
  );

  function setLibraryScope(
    mode: DashboardAudience,
    kind?: SessionKind,
    layout?: string,
  ) {
    setSearchParams(
      {
        audience: mode,
        sessionKind: kind ?? "all",
        ...(layout ? { layout } : {}),
      },
      { replace: true },
    );
  }

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
          sessionKind={sessionKind}
          copy={editor.copy}
          onClose={() => setEditor(null)}
          onSaved={(id, savedAudience, savedKind) => {
            setEditor(null);
            setLibraryScope(savedAudience, savedKind ?? sessionKind, id);
            setSource("all");
            setNotice("Layout saved to your profile.");
          }}
        />
      </PageContainer>
    );

  return (
    <PageContainer size="wide">
      <div className="builder-page">
        <header className="builder-hero feature-banner">
          <div>
            <h1 className="feature-banner__title">Dashboard Builder</h1>
            <p className="feature-banner__detail">
              Arrange panels for telemetry, strategy or replay. Saved layouts
              appear when you open a compatible session.
            </p>
          </div>
          <Link to="/sessions?view=explorer" className="button-secondary">
            Browse sessions <span aria-hidden="true">&#8599;</span>
          </Link>
        </header>
        <div className="builder-toolbar builder-toolbar--sticky">
          <div className="builder-toolbar__main">
            <button
              type="button"
              className="button-primary"
              onClick={() => openEditor()}
              disabled={slotsFull}
            >
              + New layout
            </button>
            {plan ? <Link to="/profile?tab=subscription">{layoutCount} / {plan.saved_layouts} saved layouts</Link> : null}
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
                  onClick={() => setLibraryScope(item.id, sessionKind)}
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
          <div
            className="builder-session-switch"
            role="group"
            aria-label="Session type"
          >
            {(
              [
                "race",
                "sprint",
                "qualifying",
                "practice",
                ...(sessionKind === "other" ? ["other" as const] : []),
                undefined,
              ] as const
            ).map((kind) => (
              <button
                type="button"
                key={kind ?? "all"}
                aria-pressed={sessionKind === kind}
                onClick={() => setLibraryScope(audience.id, kind)}
              >
                {kind ? sessionKindLabel[kind] : "All sessions"}
              </button>
            ))}
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
                {sessionKind
                  ? `${sessionKindLabel[sessionKind]} ${audience.label.toLowerCase()}`
                  : "Layout library"}{" "}
                <span>{visibleLayouts.length}</span>
              </h2>
              <p>
                {sessionKind === "qualifying"
                  ? "Includes Sprint Qualifying. "
                  : ""}
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
                    <span
                      className="layout-guide-label"
                      data-recommended={
                        layout.id ===
                        recommendedLayoutId(audience.id, sessionKind)
                      }
                    >
                      {getLayoutGuide(layout.id)?.label ?? "Your layout"}
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
                    aria-label={`Preview ${layout.name}`}
                    onClick={() => {
                      setLibraryScope(audience.id, sessionKind, layout.id);
                      setPreview(layout);
                    }}
                  >
                    <strong>{layout.name}</strong>
                    {layout.planRestriction ? <small>{layout.planRestriction}</small> : null}
                    <LayoutPreview config={layout.config} compact lead />
                    <Availability
                      modes={layoutModes(layout)}
                      kinds={supportedSessionKinds(
                        widgetIds(layout.config),
                        layout.config.sessionKind,
                      )}
                    />
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
                          disabled={![1, 2].includes(layout.schemaVersion) || slotsFull}
                          onClick={() => openEditor(layout, true)}
                        >
                          Copy layout
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
                        disabled={!layout.isValid || slotsFull || Boolean(layout.planRestriction)}
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
        {preview ? (
          <LayoutPreviewDialog
            layout={preview}
            onClose={() => setPreview(null)}
          />
        ) : null}
      </div>
    </PageContainer>
  );
}

function LayoutPreviewDialog({
  layout,
  onClose,
}: {
  layout: LayoutRecord;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className="builder-preview-dialog"
      onClose={onClose}
      aria-labelledby="preview-layout-name"
    >
      <header>
        <h2 id="preview-layout-name">{layout.name}</h2>
        <button
          className="button-secondary"
          onClick={() => ref.current?.close()}
        >
          Close preview
        </button>
      </header>
      <LayoutPreview config={layout.config} full />
    </dialog>
  );
}
