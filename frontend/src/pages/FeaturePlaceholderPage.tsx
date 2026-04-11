import { Link } from "react-router-dom";
import { PageContainer } from "../app/layout/PageContanier";

type PillTone = "focus" | "improved" | "live" | "ready" | "soon";

type FeaturePlaceholderDetail = {
  title: string;
  body: string;
};

type FeaturePlaceholderPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  tone?: PillTone;
  details: FeaturePlaceholderDetail[];
};

export function FeaturePlaceholderPage({
  eyebrow,
  title,
  description,
  details,
  tone = "soon",
}: FeaturePlaceholderPageProps) {
  return (
    <PageContainer>
      <section className="surface-card overflow-hidden p-6 sm:p-8 lg:p-10">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <span className={`ui-pill ui-pill--${tone}`}>{eyebrow}</span>
            <h1 className="display-font mt-5 text-[2.2rem] leading-none text-white sm:text-[2.8rem]">
              {title}
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--color-text-secondary)] sm:text-base">
              {description}
            </p>
          </div>

          <span className="rounded-full border border-[var(--color-border-subtle)] bg-white/[0.02] px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
            Preview surface
          </span>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {details.map((detail) => (
            <article key={detail.title} className="surface-card rounded-[18px] p-5">
              <span className={`ui-pill ui-pill--${tone}`}>Coming soon</span>
              <h2 className="mt-4 text-lg font-semibold text-white">{detail.title}</h2>
              <p className="mt-3 text-sm leading-7 text-[var(--color-text-secondary)]">
                {detail.body}
              </p>
            </article>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/" className="button-primary">
            Back to home
          </Link>
        </div>
      </section>
    </PageContainer>
  );
}
