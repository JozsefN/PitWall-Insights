import assert from "node:assert/strict";
import { test } from "node:test";
import {
  driverBadgeColors,
  driverOption,
  driverOptionText,
} from "../src/components/driver-select-options.ts";
import type { SessionEntryDto } from "../src/data/contracts/sessions.contracts.ts";

test("driver badges retain team colors and meet 4.5:1 text contrast across the RGB range", () => {
  for (let r = 0; r <= 255; r += 17) {
    for (let g = 0; g <= 255; g += 17) {
      for (let b = 0; b <= 255; b += 17) {
        const hex = [r, g, b]
          .map((channel) => channel.toString(16).padStart(2, "0"))
          .join("");
        const { background, color } = driverBadgeColors(hex);
        assert.equal(background, `#${hex}`);
        const [red, green, blue] = [r, g, b].map((channel) => {
          const value = channel / 255;
          return value <= 0.04045
            ? value / 12.92
            : ((value + 0.055) / 1.055) ** 2.4;
        });
        const luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue;
        const ratio =
          color === "#000000"
            ? (luminance + 0.05) / 0.05
            : 1.05 / (luminance + 0.05);
        assert.ok(ratio >= 4.5, `${hex}: ${ratio}`);
      }
    }
  }
  assert.equal(driverBadgeColors("#FF8700").background, "#FF8700");
  for (const color of [
    null,
    undefined,
    "",
    "not-a-color",
    "url(x)",
    "ffffff00",
  ]) {
    assert.equal(driverBadgeColors(color).background, "#69655d");
  }
});

test("driver options keep numbers, abbreviations and names searchable without changing selection IDs", () => {
  const entry = {
    id: "driver-4",
    car_number: "4",
    driver_name: "Lando Norris",
    driver_abbreviation: "NOR",
  } as SessionEntryDto;
  assert.equal(driverOption(entry).value, entry.id);
  assert.equal(
    driverOption(entry, `entry:${entry.id}`).value,
    `entry:${entry.id}`,
  );
  assert.equal(driverOptionText(driverOption(entry)), "#4 NOR Lando Norris");
  assert.equal(
    driverOptionText({ value: "", label: "All selected (22)" }),
    "All selected (22)",
  );
  assert.equal(driverOption({ ...entry, driver_name: null }).label, "NOR");
  assert.equal(
    driverOption({ ...entry, driver_name: null, driver_abbreviation: null })
      .label,
    "#4",
  );
});
