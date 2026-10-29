import { useEffect, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";
import { isAxiosError } from "axios";
import {
  useCreateLayoutMutation,
  useUpdateLayoutMutation,
} from "../../data/queries/layouts.queries";
import type {
  DashboardAudience,
  GridPlacement,
  LayoutRecord,
  WidgetId,
} from "../../widgets/registry/widget.types";
import {
  widgetCatalog,
  widgetSizeError,
} from "../../widgets/registry/widget.catalog";
import { EditorCanvas } from "./EditorCanvas";
import {
  draftError,
  draftFromLayout,
  draftToConfig,
  emptyDraft,
  findSpace,
  newWidget,
  canPlace,
  clampResize,
} from "./editor-model";
import type { EditorDraft, EditorWidget } from "./editor-model";
import { WidgetLibrary } from "./WidgetLibrary";
import { PanelSettings } from "./PanelSettings";
import { LayoutPreview } from "./LayoutPreview";
import "./layout-editor.css";

type Props = {
  layout: LayoutRecord | null;
  audience: DashboardAudience;
  copy?: boolean;
  onClose: () => void;
  onSaved: (id: string) => void;
};

export function LayoutEditor({
  layout,
  audience,
  copy = false,
  onClose,
  onSaved,
}: Props) {
  const [initial] = useState(() =>
    layout ? draftFromLayout(layout, copy) : emptyDraft(audience),
  );
  const [history, setHistory] = useState<{
    past: EditorDraft[];
    present: EditorDraft;
    future: EditorDraft[];
  }>({ past: [], present: initial, future: [] });
  const draft = history.present;
  const [sectionId, setSectionId] = useState(initial.sections[0].id);
  const section =
    draft.sections.find((item) => item.id === sectionId) ?? draft.sections[0];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<"edit" | "preview">("edit");
  const [message, setMessage] = useState("");
  const savedRef = useRef(false);
  const createMutation = useCreateLayoutMutation();
  const updateMutation = useUpdateLayoutMutation();
  const saving = createMutation.isPending || updateMutation.isPending;
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial);
  const blocker = useBlocker(() => dirty && !savedRef.current);
  const editableId =
    !copy && layout?.source === "user" ? layout.storageId : undefined;
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  function change(next: EditorDraft) {
    setHistory((current) => ({
      past: [...current.past.slice(-49), current.present],
      present: next,
      future: [],
    }));
    setMessage("");
  }
  function widgetsChange(groupId: string, widgets: EditorWidget[]) {
    change({
      ...draft,
      sections: draft.sections.map((item) =>
        item.id === groupId ? { ...item, widgets } : item,
      ),
    });
  }
  function add(
    id: WidgetId,
    requested: Partial<GridPlacement> = {},
    groupId = section.id,
  ) {
    const policy = widgetCatalog[id];
    const group = draft.sections.find((item) => item.id === groupId)!;
    if (
      !policy?.builderEnabled ||
      !policy.supportedAudiences.includes(draft.audience)
    )
      return;
    if (policy.accessTier > 0) {
      setMessage("This widget requires a subscription.");
      return;
    }
    if (draft.sections.flatMap((item) => item.widgets).length >= 100) {
      setMessage("A layout supports at most 100 widgets.");
      return;
    }
    const placement = findSpace(group.widgets, requested, id);
    if (!placement) {
      setMessage("This group is full. Add another group to continue.");
      return;
    }
    const widget = newWidget(id, placement, policy.defaultOptions);
    widgetsChange(group.id, [...group.widgets, widget]);
    setSectionId(group.id);
    setSelectedId(widget.instanceId);
    setView("edit");
  }
  function place(groupId: string, id: string, placement: GridPlacement) {
    const group = draft.sections.find((item) => item.id === groupId)!;
    const current = group.widgets.find((item) => item.instanceId === id)!;
    if (
      placement.x === current.placement.x &&
      placement.y === current.placement.y
    )
      placement = clampResize(group.widgets, current, placement);
    const sizeError = widgetSizeError(current.widgetId, placement);
    if (sizeError || !canPlace(group.widgets, id, placement)) {
      setMessage(
        sizeError ?? "That position does not fit. Panels must not overlap.",
      );
      return;
    }
    if (JSON.stringify(current.placement) === JSON.stringify(placement)) {
      setMessage("");
      return;
    }
    widgetsChange(
      groupId,
      group.widgets.map((widget) =>
        widget.instanceId === id ? { ...widget, placement } : widget,
      ),
    );
  }
  function reorder(index: number, delta: number) {
    const sections = [...draft.sections];
    [sections[index], sections[index + delta]] = [
      sections[index + delta],
      sections[index],
    ];
    change({ ...draft, sections });
  }
  async function save() {
    const error = draftError(draft);
    if (error) {
      setMessage(error);
      return;
    }
    const payload = {
      name: draft.name.trim(),
      description: draft.description.trim() || null,
      audience: draft.audience,
      schemaVersion: 2,
      config: draftToConfig(draft, layout?.config.id ?? crypto.randomUUID()),
    };
    try {
      const result = editableId
        ? await updateMutation.mutateAsync({ layoutId: editableId, payload })
        : await createMutation.mutateAsync(payload);
      savedRef.current = true;
      onSaved(`user:${result.id}`);
    } catch (error) {
      const detail = isAxiosError(error) ? error.response?.data?.detail : null;
      setMessage(
        typeof detail === "string"
          ? detail
          : "Could not save the layout. Your changes are still here. Try again.",
      );
    }
  }
  return (
    <section className="layout-editor" aria-label="Layout editor">
      <header className="editor-toolbar">
        <div>
          <p className="builder-eyebrow">
            {editableId ? "Edit your layout" : "Create a layout"}
          </p>
          <h2>{draft.name || "Untitled dashboard"}</h2>
          <small>
            {draft.audience === "session-lookback"
              ? "Lookback"
              : "Live & replay"}{" "}
            · {draft.sections.length}{" "}
            {draft.sections.length === 1 ? "group" : "groups"} ·{" "}
            {draft.sections.flatMap((item) => item.widgets).length} panels ·{" "}
            {dirty ? "Unsaved changes" : "No unsaved changes"}
          </small>
        </div>
        <div className="editor-actions">
          <button
            type="button"
            className="button-secondary"
            disabled={!history.past.length || saving}
            onClick={() =>
              setHistory((current) => ({
                past: current.past.slice(0, -1),
                present: current.past.at(-1)!,
                future: [current.present, ...current.future],
              }))
            }
          >
            Undo
          </button>
          <button
            type="button"
            className="button-secondary"
            disabled={!history.future.length || saving}
            onClick={() =>
              setHistory((current) => ({
                past: [...current.past, current.present],
                present: current.future[0],
                future: current.future.slice(1),
              }))
            }
          >
            Redo
          </button>
          <button
            type="button"
            className="button-secondary"
            disabled={saving}
            onClick={() => {
              if (
                !dirty ||
                window.confirm("Discard your unsaved layout changes?")
              )
                onClose();
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            className="button-primary"
            disabled={saving}
            onClick={() => void save()}
          >
            {saving ? "Saving..." : "Save layout"}
          </button>
        </div>
      </header>
      {message ? (
        <div className="editor-message" role="alert">
          {message}
        </div>
      ) : null}
      {blocker.state === "blocked" ? (
        <div className="editor-message" role="alert">
          <span>You have unsaved changes. Leave this editor?</span>
          <button className="button-secondary" onClick={() => blocker.reset()}>
            Keep editing
          </button>
          <button
            className="button-secondary"
            onClick={() => blocker.proceed()}
          >
            Discard and leave
          </button>
        </div>
      ) : null}
      <div inert={saving}>
        <div className="editor-metadata">
          <label>
            Layout name
            <input
              maxLength={160}
              value={draft.name}
              onChange={(event) =>
                change({ ...draft, name: event.target.value })
              }
              placeholder="My race dashboard"
            />
          </label>
          <label>
            Description
            <input
              maxLength={600}
              value={draft.description}
              onChange={(event) =>
                change({ ...draft, description: event.target.value })
              }
              placeholder="What do you want to follow?"
            />
          </label>
        </div>
        <div className="editor-body">
          <WidgetLibrary
            audience={draft.audience}
            target={
              section.title || `Group ${draft.sections.indexOf(section) + 1}`
            }
            onAdd={(id) => add(id)}
          />
          <div className="editor-stage">
            <div className="editor-view-controls">
              <div role="group" aria-label="Dashboard view">
                <button
                  className="button-secondary"
                  aria-pressed={view === "edit"}
                  onClick={() => setView("edit")}
                >
                  Arrange panels
                </button>
                <button
                  className="button-secondary"
                  aria-pressed={view === "preview"}
                  onClick={() => setView("preview")}
                >
                  Whole dashboard
                </button>
              </div>
              <button
                className="button-secondary"
                disabled={draft.sections.length >= 20}
                onClick={() => {
                  const id = crypto.randomUUID();
                  change({
                    ...draft,
                    sections: [
                      ...draft.sections,
                      { id, title: "", widgets: [] },
                    ],
                  });
                  setSectionId(id);
                  setSelectedId(null);
                  setView("edit");
                }}
              >
                + Group
              </button>
            </div>
            <p className="editor-help">
              One scrolling dashboard. Groups are optional blocks displayed
              together, from top to bottom. All previews use illustrative data
              and scale to fit.
            </p>
            {view === "preview" ? (
              <div
                className="editor-whole-preview"
                data-testid="whole-dashboard-preview"
              >
                <h3>Whole dashboard</h3>
                <p>
                  All groups in session order. Live content adapts to the
                  available panel size.
                </p>
                <LayoutPreview
                  config={draftToConfig(draft, "draft-preview")}
                  full
                />
              </div>
            ) : (
              draft.sections.map((group, index) => {
                const selected = group.widgets.find(
                  (widget) => widget.instanceId === selectedId,
                );
                return (
                  <section
                    key={group.id}
                    className={`editor-group${section.id === group.id ? " is-active" : ""}`}
                    data-testid="editor-group"
                    aria-label={group.title || `Group ${index + 1}`}
                  >
                    <header className="editor-group__header">
                      <h3>{group.title || `Group ${index + 1}`}</h3>
                      <div className="editor-actions">
                        <button
                          className="button-secondary"
                          aria-pressed={section.id === group.id}
                          onClick={() => setSectionId(group.id)}
                        >
                          Add widgets here
                        </button>
                        <button
                          className="button-secondary"
                          aria-label={`Move group ${index + 1} up`}
                          disabled={index === 0}
                          onClick={() => reorder(index, -1)}
                        >
                          ↑
                        </button>
                        <button
                          className="button-secondary"
                          aria-label={`Move group ${index + 1} down`}
                          disabled={index === draft.sections.length - 1}
                          onClick={() => reorder(index, 1)}
                        >
                          ↓
                        </button>
                        <button
                          className="button-secondary"
                          aria-label={`Remove group ${index + 1}`}
                          disabled={draft.sections.length === 1}
                          onClick={() => {
                            if (
                              group.widgets.length &&
                              !window.confirm(
                                "Remove this group and its widgets?",
                              )
                            )
                              return;
                            change({
                              ...draft,
                              sections: draft.sections.filter(
                                (item) => item.id !== group.id,
                              ),
                            });
                            if (section.id === group.id)
                              setSectionId(
                                draft.sections.find(
                                  (item) => item.id !== group.id,
                                )!.id,
                              );
                            setSelectedId(null);
                          }}
                        >
                          Remove group
                        </button>
                      </div>
                    </header>
                    <label className="editor-section-title">
                      Group title
                      <input
                        value={group.title}
                        maxLength={160}
                        placeholder="Optional group title"
                        onChange={(event) =>
                          change({
                            ...draft,
                            sections: draft.sections.map((item) =>
                              item.id === group.id
                                ? { ...item, title: event.target.value }
                                : item,
                            ),
                          })
                        }
                      />
                    </label>
                    <p className="editor-help">
                      Drag the top bar to move, or the corner to resize. Both
                      handles support arrow keys. Size rules prevent unreadable
                      panels.
                    </p>
                    <EditorCanvas
                      section={group}
                      selectedId={selectedId}
                      onSelect={(id) => {
                        setSelectedId(id);
                        setSectionId(group.id);
                      }}
                      onAdd={(id, box) => add(id, box, group.id)}
                      onPlacement={(id, box) => place(group.id, id, box)}
                      onRemove={(id) => {
                        widgetsChange(
                          group.id,
                          group.widgets.filter(
                            (widget) => widget.instanceId !== id,
                          ),
                        );
                        if (selectedId === id) setSelectedId(null);
                      }}
                      onMessage={setMessage}
                    />
                    {selected ? (
                      <PanelSettings
                        widget={selected}
                        onPlace={(box) =>
                          place(group.id, selected.instanceId, box)
                        }
                        onOptions={(options) =>
                          widgetsChange(
                            group.id,
                            group.widgets.map((widget) =>
                              widget.instanceId === selected.instanceId
                                ? { ...widget, options }
                                : widget,
                            ),
                          )
                        }
                        onDuplicate={() => {
                          if (
                            draft.sections.flatMap((item) => item.widgets)
                              .length >= 100
                          ) {
                            setMessage(
                              "A layout supports at most 100 widgets.",
                            );
                            return;
                          }
                          const placement = findSpace(
                            group.widgets,
                            selected.placement,
                            selected.widgetId,
                          );
                          if (!placement) {
                            setMessage("No room to duplicate this panel.");
                            return;
                          }
                          const widget = newWidget(
                            selected.widgetId,
                            placement,
                            selected.options,
                          );
                          widgetsChange(group.id, [...group.widgets, widget]);
                          setSelectedId(widget.instanceId);
                        }}
                      />
                    ) : null}
                  </section>
                );
              })
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
