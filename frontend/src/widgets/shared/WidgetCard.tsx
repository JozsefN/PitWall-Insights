import type { ReactNode } from "react";

type WidgetCardProps = {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
};

export function WidgetCard({
  title,
  description,
  actions,
  children,
}: WidgetCardProps) {
  return (
    <article className="widget-card">
      <header className="widget-card__header">
        <div>
          <h3 className="widget-card__title">{title}</h3>
          {description ? (
            <p className="widget-card__description">{description}</p>
          ) : null}
        </div>

        {actions ? <div className="widget-card__actions">{actions}</div> : null}
      </header>

      <div className="widget-card__body">{children}</div>
    </article>
  );
}