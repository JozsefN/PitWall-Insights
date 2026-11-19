import { createContext, useContext } from "react";

export const WidgetSizeContext = createContext({
  compact: false,
  short: false,
  width: 0,
  height: 0,
});

/** Runtime panel modes; defaults also support rendering without a dashboard frame. */
export function useWidgetSize() {
  return useContext(WidgetSizeContext);
}

export function useTelemetryPlotSize() {
  const panel = useWidgetSize();
  return {
    width: panel.width
      ? Math.max(260, panel.width - (panel.compact || panel.short ? 30 : 46))
      : 860,
    height: panel.height
      ? Math.round(
          Math.max(panel.short ? 176 : 190, Math.min(360, panel.height * 0.57)),
        )
      : 240,
  };
}
