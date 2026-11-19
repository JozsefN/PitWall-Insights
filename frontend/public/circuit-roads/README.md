# Circuit road data

Sakhir, Suzuka and Silverstone are unmodified track CSVs from [TUMFTM's racetrack database](https://github.com/TUMFTM/racetrack-database/tree/e59595d1f3573b30d1ded6a08984935b957688e0/tracks). The supplied licence is in `LICENSE-TUMFTM.txt`. The dataset uses OpenStreetMap centrelines and imagery-derived widths. Its accuracy varies around each circuit.

© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). The OpenStreetMap data is available under the [ODbL](https://opendatacommons.org/licenses/odbl/1-0/).

`centrelines/<circuit-id>.csv` covers all 26 venues on the 2023–2026 race calendars. Each file contains a local projection of a LineString from the pinned GitHub revision. Run `python scripts/sync_circuit_roads.py` from the repo root to download and validate the centrelines and width profiles listed by the catalog. The supplied licence is in `LICENSE-f1-circuits.txt`. [Shared circuit catalog](../../../shared/circuit-catalog.json) · [Pinned f1-circuits data](https://github.com/bacinger/f1-circuits/tree/8094e957b8d6aa8b9f4510c93968556cccd30e02/circuits)

The catalog identifies each venue by its OpenF1 circuit key and stores its host, legacy names and optional width profile. The map fits a width profile first, then tries the bundled centreline with an illustrated width. The illustration uses 12 m by default. Imola uses a catalog value of 12.5 m informed by the circuit's published width range. [Imola circuit specifications](https://www.autodromoimola.it/downloads/Presentazione_MICE_Autodromo_2021_EN.pdf)

Both assets use a rigid fit to a closed session lap. The fit checks circuit length and distance from the observed trace. It preserves distances and the original car coordinates. If a fit fails, the map illustrates the available telemetry outline and labels the source. Measured incident and track-limit analyses require a registered surface profile.

Every CSV uses four numeric columns in metres. They give local east, local north, distance to the right edge, and distance to the left edge. Comment lines begin with `#`. The browser loads the current venue's file and caches the parsed rows by path. The runtime serves these files locally.

To add a venue, record its provider key, host and aliases in the catalog and add the host flag if needed. The circuit ID identifies the upstream LineString and the generated CSV. An optional width profile references a source and filename in the catalog. Record new source licences here. The registration tests check every listed asset. Use a real lap to verify the venue's geometry and orientation.
