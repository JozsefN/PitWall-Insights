import type { ReactNode } from "react";
import type { ReviewGroup } from "./contracts";
import { ReviewContext, useReviewQuery } from "./review-query";

export function ReviewProvider({
  groups,
  children,
}: {
  groups: ReviewGroup[];
  children: ReactNode;
}) {
  const query = useReviewQuery(groups);
  return (
    <ReviewContext.Provider value={query}>{children}</ReviewContext.Provider>
  );
}
