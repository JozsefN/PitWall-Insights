import { memo, useMemo } from "react";
import type { PitMap } from "../utils/pit-map";
import { smoothTrackPath } from "../utils/track-curves";
import { metresToMapUnits } from "../utils/track-scale";

export const PitLaneDrawing = memo(function PitLaneDrawing({
  data,
  boxCount,
  unitPerPixel,
}: {
  data: PitMap;
  boxCount: number;
  unitPerPixel: number;
}) {
  const path = useMemo(
    () => smoothTrackPath(data.lane, false, metresToMapUnits(0.45)),
    [data.lane],
  );
  const halfSize = unitPerPixel * 3.1;
  return (
    <g
      className="track-map-pits"
      aria-label="Pit lane and estimated team boxes"
    >
      <path
        d={path}
        data-source={data.source}
        className="track-map-pits__lane"
        vectorEffect="non-scaling-stroke"
      >
        <title>
          {data.source === "position_traces"
            ? "Pit lane from recorded entries and exits"
            : "Pit lane from reported stops"}
        </title>
      </path>
      {data.boxes.slice(0, boxCount).map((box) => (
        <rect
          key={box.id}
          className="track-map-pits__box"
          x={box.x - halfSize}
          y={box.y - halfSize}
          width={halfSize * 2}
          height={halfSize * 2}
          rx={unitPerPixel}
          fill={box.color}
          vectorEffect="non-scaling-stroke"
        >
          <title>{box.name} · estimated pit box</title>
        </rect>
      ))}
    </g>
  );
});
