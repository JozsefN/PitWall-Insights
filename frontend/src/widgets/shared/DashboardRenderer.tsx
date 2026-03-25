import { widgetRegistry } from "../registry/widget.registry";
import type {
  DashboardConfig,
  DashboardSection,
  SectionLayoutNode,
  LayoutGroupNode,
  LayoutWidgetNode,
} from "../registry/widget.types";
import "./dashboard-renderer.css";

type DashboardRendererProps = {
  config: DashboardConfig;
};

export function DashboardRenderer({ config }: DashboardRendererProps) {
  return (
    <div className="dashboard">
      {(config.title || config.subtitle) && (
        <header className="dashboard__hero">
          <div>
            {config.title ? <h1 className="dashboard__title">{config.title}</h1> : null}
            {config.subtitle ? (
              <p className="dashboard__subtitle">{config.subtitle}</p>
            ) : null}
          </div>
        </header>
      )}

      <div className="dashboard__sections">
        {config.sections.map((section) => (
          <DashboardSectionView key={section.id} section={section} />
        ))}
      </div>
    </div>
  );
}

function DashboardSectionView({ section }: { section: DashboardSection }) {
  return (
    <section className="dashboard-section">
      {(section.title || section.description) && (
        <div className="dashboard-section__header">
          {section.title ? (
            <h2 className="dashboard-section__title">{section.title}</h2>
          ) : null}
          {section.description ? (
            <p className="dashboard-section__description">{section.description}</p>
          ) : null}
        </div>
      )}

      <div className="dashboard-section__body">
        <LayoutNodeRenderer node={section.layout} />
      </div>
    </section>
  );
}

function LayoutNodeRenderer({ node }: { node: SectionLayoutNode }) {
  if (node.type === "group") {
    return <LayoutGroupRenderer node={node} />;
  }

  return <LayoutWidgetRenderer node={node} />;
}

function LayoutGroupRenderer({ node }: { node: LayoutGroupNode }) {
  return (
    <div
      className={`layout-group layout-group--${node.direction}`}
      style={{
        gap: node.gap ?? 16,
      }}
    >
      {node.children.map((child, index) => (
        <LayoutNodeRenderer key={index} node={child} />
      ))}
    </div>
  );
}

function LayoutWidgetRenderer({ node }: { node: LayoutWidgetNode }) {
  const definition = widgetRegistry[node.widgetId];

  if (!definition) return null;

  const Component = definition.component;

  return (
    <div
      className={[
        "layout-widget",
        `layout-widget--width-${sanitizeClassToken(node.width ?? "fill")}`,
        `layout-widget--height-${sanitizeClassToken(node.height ?? "auto")}`,
        node.className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{
        minHeight: node.minHeight,
        maxHeight: node.maxHeight,
        flexGrow: node.grow ?? 0,
      }}
    >
      <Component />
    </div>
  );
}

function sanitizeClassToken(value: string) {
  return value.replace(/\//g, "-");
}