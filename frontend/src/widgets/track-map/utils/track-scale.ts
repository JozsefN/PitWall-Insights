// The existing position pipeline uses decimetres. Surface profiles use metres.
export const metresToMapUnits = (metres: number) => metres * 10;

export function replayCarDimensions(season: number) {
  // Representative overall lengths. The widths follow the FIA bodywork dimensions.
  return season >= 2026
    ? { lengthM: 5.3, widthM: 1.9 }
    : { lengthM: 5.5, widthM: 2 };
}

export function illustratedRoadWidthLimitM(circuit?: {
  illustratedWidthLimitM?: number;
}) {
  return circuit?.illustratedWidthLimitM ?? 16;
}

export function mapScaleBar(unitsPerPixel: number) {
  const metres = [1, 2, 5, 10, 20, 50, 100, 200, 500].find(
    (value) => metresToMapUnits(value) / unitsPerPixel >= 44,
  );
  return metres
    ? { metres, widthPx: metresToMapUnits(metres) / unitsPerPixel }
    : undefined;
}
