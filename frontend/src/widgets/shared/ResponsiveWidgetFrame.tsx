import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { widgetCatalog } from "../registry/widget.catalog";
import { WidgetSizeContext } from "./widget-size";
import type { WidgetId } from "../registry/widget.types";

export function ResponsiveWidgetFrame({
  widgetId,
  children,
}: {
  widgetId: WidgetId;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const policy = widgetCatalog[widgetId];
  const [mode, setMode] = useState({ compact: false, short: false });
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      const compact = entry.contentRect.width < policy.sizing.compactBelowPx;
      const short =
        entry.contentRect.height > 0 &&
        entry.contentRect.height < policy.sizing.shortBelowPx;
      setMode((previous) =>
        previous.compact === compact && previous.short === short
          ? previous
          : { compact, short },
      );
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [policy]);
  return (
    <div
      ref={ref}
      className="responsive-widget"
      data-widget={widgetId}
      data-panel-kind={policy.previewKind}
      data-density={mode.compact ? "compact" : "comfortable"}
      data-height={mode.short ? "short" : "regular"}
    >
      <WidgetSizeContext.Provider value={mode}>
        {children}
      </WidgetSizeContext.Provider>
    </div>
  );
}
