export function WidgetLoading() {
  return <div className="widget-state">Loading…</div>;
}

export function WidgetError({
  message = "Something went wrong.",
}: {
  message?: string | null;
}) {
  return (
    <div className="widget-state widget-state--error" role="alert">
      {message || "Something went wrong."}
    </div>
  );
}

export function WidgetEmpty({
  message = "No data available.",
}: {
  message?: string;
}) {
  return <div className="widget-state">{message}</div>;
}
