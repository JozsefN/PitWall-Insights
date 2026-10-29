import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { dashboardGrid } from "../../widgets/registry/widget.catalog";

export function DesignScale({
  height,
  children,
}: {
  height: number;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) =>
      setScale(
        Math.min(1, entry.contentRect.width / dashboardGrid.designWidth),
      ),
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={ref} className="design-scale" style={{ height: height * scale }}>
      <div
        className="design-scale__content"
        style={{
          width: dashboardGrid.designWidth,
          height,
          transform: `scale(${scale})`,
        }}
      >
        {children}
      </div>
    </div>
  );
}
