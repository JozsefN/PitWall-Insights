import type { TrackMapOverlay } from "../models";

export const flagColours: Record<string, string> = {
  YELLOW: "#f5c74f",
  "DOUBLE YELLOW": "#f89839",
  RED: "#f56a76",
  "SAFETY CAR": "#f5c74f",
  "VIRTUAL SAFETY CAR": "#efac57",
  "VSC ENDING": "#efac57",
};

export const surfaceColours: Record<string, string> = {
  racing_surface: "#6685a6",
  pit_lane: "#a285cf",
  gravel: "#c2a476",
  runoff: "#48977f",
  recovery: "#63c9d9",
};

export function mapOverlayColour(overlay: TrackMapOverlay | undefined) {
  if (overlay?.layer === "weather" && overlay.weather?.rain_reported)
    return "#62bbfa";
  if (overlay?.layer === "flags" && overlay.flags?.track_flag)
    return flagColours[overlay.flags.track_flag];
}
