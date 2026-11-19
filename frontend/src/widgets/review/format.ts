export const seconds = (value: number | null | undefined, decimals = 2) =>
  value == null ? "Unavailable" : `${value.toFixed(decimals)} s`;
