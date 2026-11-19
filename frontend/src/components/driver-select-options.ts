import type { SessionEntryDto } from "../data/contracts/sessions.contracts";

export type DriverSelectOption = {
  value: string;
  label: string;
  detail?: string;
  driver?: SessionEntryDto;
};

export function driverOption(
  entry: SessionEntryDto,
  value = entry.id,
): DriverSelectOption {
  return {
    value,
    label:
      entry.driver_name || entry.driver_abbreviation || `#${entry.car_number}`,
    driver: entry,
  };
}

export function driverBadgeColors(color: string | null | undefined) {
  const hex = color?.replace(/^#/, "");
  const background = hex && /^[\da-f]{6}$/i.test(hex) ? `#${hex}` : "#69655d";
  const rgb = [1, 3, 5].map((offset) => {
    const channel = parseInt(background.slice(offset, offset + 2), 16) / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  const luminance = rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  return { background, color: luminance > 0.179 ? "#000000" : "#ffffff" };
}

export function driverOptionText(option: DriverSelectOption) {
  const driver = option.driver;
  return driver
    ? `#${driver.car_number} ${driver.driver_abbreviation ?? ""} ${option.label}`
    : option.label;
}
