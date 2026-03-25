export function WidgetLoading() {
  return <div className="widget-state">Loading…</div>;
}

export function WidgetError() {
  return <div className="widget-state widget-state--error">Something went wrong.</div>;
}

export function WidgetEmpty({ message = "No data available." }: { message?: string }) {
  return <div className="widget-state">{message}</div>;
}