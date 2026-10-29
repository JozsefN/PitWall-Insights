# Dashboard Builder

## Ownership and navigation

`/dashboard-builder` is the authenticated home for reusable session layouts. New layout stays above the library in a sticky toolbar so it remains reachable with large collections. Layout cards contain the previews; there is no separate preview pane. The library offers source and audience filters, inline favorite stars, editing and deletion for personal layouts, and Use template for factory layouts.

A layout is one scrolling dashboard. Its optional groups (`sections` in stored documents) are vertical blocks, not tabs or alternate views. The editor shows all groups together with ordering controls; Whole dashboard uses the same group order and proportions as chooser thumbnails.

Factory definitions remain in `widgets/registry/dashboard.config.ts`. They are never updated or deleted. Starting from one makes a deep copy with independent widget instances. Personal layouts are stored in `user_dashboard_layouts`, linked to `users.id` through `owner_user_id`; ownership comes from the authenticated request, never the submitted document.

## Frontend boundaries

- `pages/DashboardBuilderPage.tsx` composes the library and editor and coordinates their navigation.
- `features/dashboards/editor-model.ts` owns pure draft conversion, placement, collision checks and document serialization. It translates legacy row/column templates while preserving their relative arrangement, section metadata and widget options.
- `features/dashboards/LayoutEditor.tsx` owns editing history, all-group composition, ordering, whole-dashboard mode, save/retry and unsaved-change protection. `WidgetLibrary.tsx` owns discovery/filtering; `PanelSettings.tsx` owns per-panel settings.
- `features/dashboards/EditorCanvas.tsx` owns palette drops, pointer capture for moving/resizing, keyboard handles, placement feedback and section scroll reset. Add buttons and numeric position/size fields provide alternatives to dragging. The editor uses a 1200-pixel design surface scaled to fit; pointer deltas are transformed back into design coordinates. Groups are all visible and have no nested vertical canvas scrolling.
- `features/dashboards/layout-catalog.ts` remains the shared catalog and compatibility layer. Favorites sort first using a stable sort; they do not form a separate row. The session feature retains its existing exports.
- `features/dashboards/LayoutPreview.tsx` draws the whole layout in one proportional SVG. `widgets/shared/WidgetBlueprint.tsx` supplies distinct table, chart, stint, circuit and replay-card structures. Library cards, editor bodies and Whole dashboard share these deterministic blueprints and do not request telemetry.
- `shared/dashboard-widgets.json` owns widget discovery, supported audiences, size/shape rules, access tiers and defaults for both frontend and backend. `widgets/registry` binds these entries to runtime components. The eight session-analysis widgets are Free; System Health and Sessions remain platform-only and cannot be added to a session layout. The builder supports Free, Subscription, and Tier 1/2/3 filters; paid filters currently return an empty collection. This implements discovery metadata, not a billing system. Future paid widgets require matching server entitlement policy before launch.
- `widgets/shared/DashboardRenderer.tsx` renders both existing row/column configurations and saved grid layouts using the same widget components. Tier badges appear only in the builder. Narrow session screens stack grid panels for readability.
- `data/queries/layouts.queries.ts` owns layout and favorite queries/mutations. Both personal caches are scoped by account. The existing auth feature delegates to the shared auth query so the data layer has no dependency on feature hooks.

## Persistence contract

Schema version 1 remains readable for existing layouts. Version 2 extends the existing `DashboardConfig` tree with an optional grid on groups and placement/instance identity on widget nodes:

```json
{
  "type": "group",
  "direction": "row",
  "gap": 12,
  "grid": { "columns": 12, "rowHeight": 48 },
  "children": [
    {
      "type": "widget",
      "widgetId": "lap-table",
      "instanceId": "unique-within-section",
      "placement": { "x": 0, "y": 0, "w": 6, "h": 5 },
      "options": { "title": "Race lap data" }
    }
  ]
}
```

Size policies are documented in the [widget creation runbook](widget-creation-runbook.md). Each widget has an enforced minimum/default/maximum cell size and optional pixel aspect bounds. The editor and backend read the same policy file. `ResponsiveWidgetFrame` measures actual panel width/height and provides compact/short modes to CSS and `useWidgetSize`; smaller stint panels expose secondary controls through a disclosure.

Positions use zero-based cells. The editor snaps movement and resizing to the grid. Invalid overlaps are rejected rather than silently moving other panels. Each section allows 200 rows; widgets have widths of 2–12 columns and heights of 3–20 rows. Layouts support at most 20 sections and 100 widgets. Blank names and empty sections cannot be saved. Undo/redo keeps up to 50 draft snapshots. Save errors keep the draft intact. Browser unload and application navigation both protect unsaved changes.

Existing layout CRUD endpoints handle create/read/update/delete. Updating retains the same database id and supports clearing descriptions. Server validation in `dashboard_layouts/domain/validation.py` checks schema versions, structure, widget identities, audience compatibility and grid bounds/overlaps, including requests made outside the UI. The server accepts all currently registered widgets as free; client tier labels are not an entitlement authority.

Favorites use `GET /api/layouts/favorites` and `PUT /api/layouts/favorites` with `{ "layoutId": "builtin:compare-lap", "favorite": true }`. The `user_layout_favorites` table has the composite primary key `(owner_user_id, layout_key)`. Personal references use `user:<database-id>` and are checked against ownership. Favoriting is idempotent. Deleting a personal layout also removes its favorite. Deleting a profile cascades to its layouts and favorites.

Migration: `f6c2a91d7b30_add_layout_favorites.py`, following `e4b7c9d2a610`. Apply with `python -m alembic upgrade head` from `backend` using its virtual environment. This migration was applied to the running local database during implementation.

## Verification

See [Layout Builder Validation](../testing/layout-builder-validation.md) for reproducible commands, live backend coverage and screenshots. The live tests use separate temporary accounts and clean up only their own accounts and associated records. They do not require or modify an existing user's credentials.

## Widget development

Follow the [precise widget creation runbook](widget-creation-runbook.md) for registration, the shared contract, data resources, sizing, structural previews, adaptive behavior, API validation and required checks. Backend source deployments must include the sibling `shared` directory; restart the backend when changing JSON policies.
