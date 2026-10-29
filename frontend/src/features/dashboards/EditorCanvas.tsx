import { useRef, useState } from "react";
import type { PointerEvent, KeyboardEvent } from "react";
import { widgetRegistry } from "../../widgets/registry/widget.registry";
import type {
  GridPlacement,
  WidgetId,
} from "../../widgets/registry/widget.types";
import {
  canPlace,
  clampResize,
  GRID_COLUMNS,
  GRID_GAP,
  GRID_ROW_HEIGHT,
} from "./editor-model";
import type { EditorSection } from "./editor-model";
import { WidgetBlueprint } from "../../widgets/shared/WidgetBlueprint";
import {
  dashboardGrid,
  widgetSizeError,
} from "../../widgets/registry/widget.catalog";
import { DesignScale } from "./DesignScale";
import { TierBadge } from "./TierBadge";

type Props = {
  section: EditorSection;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onPlacement: (id: string, placement: GridPlacement) => void;
  onAdd: (id: WidgetId, placement: Partial<GridPlacement>) => void;
  onRemove: (id: string) => void;
  onMessage: (message: string) => void;
};

type Gesture = {
  id: string;
  mode: "move" | "resize";
  startX: number;
  startY: number;
  columnSize: number;
  original: GridPlacement;
  scale: number;
};

export function EditorCanvas({
  section,
  selectedId,
  onSelect,
  onPlacement,
  onAdd,
  onRemove,
  onMessage,
}: Props) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const [ghost, setGhost] = useState<{
    id: string;
    box: GridPlacement;
    valid: boolean;
  } | null>(null);
  const rows = Math.max(
    section.widgets.length ? 3 : 6,
    ...section.widgets.map(
      (widget) => widget.placement.y + widget.placement.h + 1,
    ),
    ghost ? ghost.box.y + ghost.box.h + 1 : 0,
  );

  function start(
    event: PointerEvent<HTMLButtonElement>,
    id: string,
    mode: Gesture["mode"],
  ) {
    if (event.button !== 0 || !canvasRef.current) return;
    const original = section.widgets.find(
      (widget) => widget.instanceId === id,
    )!.placement;
    gesture.current = {
      id,
      mode,
      startX: event.clientX,
      startY: event.clientY,
      columnSize:
        ((dashboardGrid.designWidth + GRID_GAP) / GRID_COLUMNS) *
        (canvasRef.current.getBoundingClientRect().width /
          dashboardGrid.designWidth),
      scale:
        canvasRef.current.getBoundingClientRect().width /
        dashboardGrid.designWidth,
      original,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    onSelect(id);
    setGhost({ id, box: original, valid: true });
  }

  function move(event: PointerEvent<HTMLButtonElement>) {
    const active = gesture.current;
    if (!active) return;
    const dx = Math.round((event.clientX - active.startX) / active.columnSize);
    const dy = Math.round(
      (event.clientY - active.startY) /
        ((GRID_ROW_HEIGHT + GRID_GAP) * active.scale),
    );
    const box =
      active.mode === "move"
        ? {
            ...active.original,
            x: Math.max(
              0,
              Math.min(12 - active.original.w, active.original.x + dx),
            ),
            y: Math.max(
              0,
              Math.min(200 - active.original.h, active.original.y + dy),
            ),
          }
        : clampResize(
            section.widgets,
            section.widgets.find((widget) => widget.instanceId === active.id)!,
            { w: active.original.w + dx, h: active.original.h + dy },
          );
    setGhost({
      id: active.id,
      box,
      valid: canPlace(section.widgets, active.id, box),
    });
  }

  function end() {
    if (ghost?.valid) onPlacement(ghost.id, ghost.box);
    else if (ghost) {
      const widget = section.widgets.find(
        (item) => item.instanceId === ghost.id,
      )!;
      onMessage(
        widgetSizeError(widget.widgetId, ghost.box) ??
          "That position overlaps another panel. Move it to an open space.",
      );
    }
    gesture.current = null;
    setGhost(null);
  }

  function keyboard(
    event: KeyboardEvent<HTMLButtonElement>,
    id: string,
    mode: Gesture["mode"],
  ) {
    const delta = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    }[event.key];
    if (!delta) return;
    event.preventDefault();
    const widget = section.widgets.find((widget) => widget.instanceId === id)!;
    const original = widget.placement;
    const box =
      mode === "move"
        ? { ...original, x: original.x + delta[0], y: original.y + delta[1] }
        : clampResize(section.widgets, widget, {
            w: original.w + delta[0],
            h: original.h + delta[1],
          });
    if (canPlace(section.widgets, id, box)) onPlacement(id, box);
    else
      onMessage(
        widgetSizeError(
          section.widgets.find((widget) => widget.instanceId === id)!.widgetId,
          box,
        ) ?? "The panel must fit in an open space within the grid.",
      );
  }

  return (
    <div className="editor-canvas-scroll">
      <DesignScale height={rows * (GRID_ROW_HEIGHT + GRID_GAP) - GRID_GAP}>
        <div
          ref={canvasRef}
          className="editor-canvas"
          data-testid="editor-canvas"
          style={{ gridTemplateRows: `repeat(${rows}, ${GRID_ROW_HEIGHT}px)` }}
          onDragOver={(event) => {
            if (
              event.dataTransfer.types.includes("application/x-pitwall-widget")
            ) {
              event.preventDefault();
              event.dataTransfer.dropEffect = "copy";
            }
          }}
          onDrop={(event) => {
            event.preventDefault();
            const id = event.dataTransfer.getData(
              "application/x-pitwall-widget",
            ) as WidgetId;
            if (!widgetRegistry[id]) return;
            const rect = event.currentTarget.getBoundingClientRect();
            onAdd(id, {
              x: Math.floor(
                (event.clientX - rect.left) /
                  (((dashboardGrid.designWidth + GRID_GAP) / 12) *
                    (rect.width / dashboardGrid.designWidth)),
              ),
              y: Math.floor(
                (event.clientY - rect.top) /
                  ((GRID_ROW_HEIGHT + GRID_GAP) *
                    (rect.width / dashboardGrid.designWidth)),
              ),
            });
          }}
        >
          {!section.widgets.length ? (
            <div className="editor-canvas__empty">
              <strong>Build your view</strong>
              <p>Drag a widget here, or use Add in the widget library.</p>
            </div>
          ) : null}
          {section.widgets.map((widget) => {
            const box =
              ghost?.id === widget.instanceId ? ghost.box : widget.placement;
            const definition = widgetRegistry[widget.widgetId];
            const title =
              typeof widget.options?.title === "string"
                ? widget.options.title
                : definition.title;
            return (
              <div
                key={widget.instanceId}
                data-testid="editor-widget"
                data-widget-id={widget.instanceId}
                className={`editor-panel${selectedId === widget.instanceId ? " is-selected" : ""}${ghost?.id === widget.instanceId && !ghost.valid ? " is-colliding" : ""}`}
                style={{
                  gridColumn: `${box.x + 1} / span ${box.w}`,
                  gridRow: `${box.y + 1} / span ${box.h}`,
                }}
              >
                <div className="editor-panel__bar">
                  <button
                    type="button"
                    className="editor-panel__move"
                    aria-label={`Move ${title}`}
                    onPointerDown={(e) => start(e, widget.instanceId, "move")}
                    onPointerMove={move}
                    onPointerUp={end}
                    onPointerCancel={() => {
                      gesture.current = null;
                      setGhost(null);
                    }}
                    onKeyDown={(e) => keyboard(e, widget.instanceId, "move")}
                  >
                    <span aria-hidden="true">⠿</span> {title}
                  </button>
                  <TierBadge tier={definition.accessTier} />
                  <button
                    type="button"
                    aria-label={`Remove ${title}`}
                    className="editor-icon-button"
                    onClick={() => onRemove(widget.instanceId)}
                  >
                    ×
                  </button>
                </div>
                <button
                  className="editor-panel__body"
                  type="button"
                  onClick={() => onSelect(widget.instanceId)}
                  aria-label={`Configure ${title}`}
                >
                  <WidgetBlueprint
                    widgetId={widget.widgetId}
                    options={widget.options}
                    width={
                      box.w * ((dashboardGrid.designWidth + GRID_GAP) / 12) -
                      GRID_GAP -
                      2
                    }
                    height={
                      box.h * (GRID_ROW_HEIGHT + GRID_GAP) - GRID_GAP - 40
                    }
                    header={false}
                  />
                </button>
                <span className="editor-panel__size">
                  {box.w} × {box.h}
                </span>
                <button
                  type="button"
                  className="editor-panel__resize"
                  aria-label={`Resize ${title}`}
                  onPointerDown={(e) => start(e, widget.instanceId, "resize")}
                  onPointerMove={move}
                  onPointerUp={end}
                  onPointerCancel={() => {
                    gesture.current = null;
                    setGhost(null);
                  }}
                  onKeyDown={(e) => keyboard(e, widget.instanceId, "resize")}
                >
                  ◢
                </button>
              </div>
            );
          })}
        </div>
      </DesignScale>
    </div>
  );
}
