import { DriverSelect } from "../../../components/DriverSelect";
import type { SessionEntryDto } from "../../../data/contracts/sessions.contracts";

type ChartDriverPickerProps = {
  drivers: { id: string; label: string; entry: SessionEntryDto }[];
  value: string;
  onChange: (id: string) => void;
};

export function ChartDriverPicker({
  drivers,
  value,
  onChange,
}: ChartDriverPickerProps) {
  if (drivers.length < 2) return null;

  return (
    <label className="chart-driver-picker">
      <span>Drivers</span>
      <DriverSelect
        aria-label="Drivers"
        value={value}
        onChange={onChange}
        options={[
          { value: "", label: `All selected (${drivers.length})` },
          ...drivers.map((driver) => ({ value: driver.id, label: driver.entry.driver_name || driver.label, driver: driver.entry })),
        ]}
      />
    </label>
  );
}
