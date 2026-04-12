import type { PropsWithChildren } from "react";

type PageContainerProps = PropsWithChildren<{
  size?: "default" | "wide" | "full";
}>;

const sizeClassNames: Record<NonNullable<PageContainerProps["size"]>, string> = {
  default: "max-w-7xl",
  wide: "max-w-[1680px]",
  full: "max-w-none",
};

export function PageContainer({
  children,
  size = "default",
}: PageContainerProps) {
  return (
    <div
      className={[
        "mx-auto w-full px-4 py-6 sm:px-6 lg:px-8",
        sizeClassNames[size],
      ].join(" ")}
    >
      {children}
    </div>
  );
}
