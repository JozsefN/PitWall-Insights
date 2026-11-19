import { useState, type CSSProperties, type PropsWithChildren } from "react";
import "./driver-cards.css";

type Identity = {
  entryId: string;
  name: string;
  carNumber: string;
  team: string | null;
  accent: string;
  headshot?: string | null;
};

export function DriverCard({
  identity,
  className,
  children,
}: PropsWithChildren<{
  identity: Identity;
  className: string;
}>) {
  const [failed, setFailed] = useState<string>();
  const { entryId, name, carNumber, team, accent, headshot } = identity;
  return (
    <article
      className={`driver-card ${className}`}
      data-entry-id={entryId}
      style={{ "--driver-accent": accent } as CSSProperties}
    >
      <header className="driver-card__identity review-driver-identity">
        <span className="driver-card__number" aria-hidden="true">
          {carNumber}
        </span>
        {headshot && failed !== headshot ? (
          <img
            loading="lazy"
            src={headshot}
            alt=""
            referrerPolicy="no-referrer"
            onError={() => setFailed(headshot)}
          />
        ) : null}
        <div className="driver-card__name">
          {team ? <small>{team}</small> : null}
          <h4>{name}</h4>
          <span className="driver-card__number-label">#{carNumber}</span>
        </div>
      </header>
      <div className="driver-card__body">{children}</div>
    </article>
  );
}
