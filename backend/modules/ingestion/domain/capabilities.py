"""Capabilities of the configured historical OpenF1 data path."""


def capability(feature, supported, note):
    return {"feature": feature, "supported": supported, "note": note}


DATA_CAPABILITIES = [
    capability("Speed and throttle traces", True, "Available when the session has car telemetry."),
    capability("Brake trace", True, "Brake on/off only; brake pressure is not supplied."),
    capability("RPM, gear and DRS", True, "Public telemetry channels; missing samples remain unknown."),
    capability("Track map and historical replay", True, "Uses approximate XYZ positions, subject to session coverage."),
    capability("Lap times, sectors, tyres and stints", True, "Available observations are retained without inventing missing values."),
    capability("Clean-lap filtering", True, "PitWall checks sectors, clocks, flags, pit events and deleted laps."),
    capability("Historical strategy calculations", True, "Calculations require sufficient inputs and calibrated models."),
    capability("Weather and wind", True, "Public session weather, rather than weather at each car."),
    capability("Race control, flags and safety cars", True, "Derived from timestamped race-control messages."),
    capability("Pit visits and gap calculations", True, "Native pit and interval reports plus PitWall calculations, where available."),
    capability("Historical sessions before 2023", False, "OpenF1 historical coverage starts in 2023."),
    capability("Live race viewer", False, "This version provides historical sessions and replay."),
    capability("Fuel mass, tyre temperatures and precise track edges", False, "These measurements are not supplied by the public source."),
]
