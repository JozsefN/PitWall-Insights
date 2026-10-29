import { createContext, useContext } from "react";

export const WidgetSizeContext = createContext({
  compact: false,
  short: false,
});

/** Runtime panel modes; defaults also support rendering without a dashboard frame. */
export function useWidgetSize() {
  return useContext(WidgetSizeContext);
}
