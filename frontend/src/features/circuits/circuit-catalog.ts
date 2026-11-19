import catalog from "../../../../shared/circuit-catalog.json" with { type: "json" };

export type CircuitDefinition = {
  id: string;
  host: string;
  openf1Key: number;
  aliases: readonly string[];
  widthProfile?: { file: string; source: string };
  illustratedWidthLimitM?: number;
};

export type CircuitRoadAsset = {
  file: string;
  width: "profile" | "estimated";
  credits: readonly { label: string; url: string }[];
};

type Venue = {
  circuit_key?: string | null;
  location?: string | null;
  event_name: string;
};

function normalize(value: string) {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const circuits: readonly CircuitDefinition[] = catalog.circuits;
const roadSources = new Map(Object.entries(catalog.roadSources));
const byOpenF1Key = new Map(
  circuits.map((circuit) => [String(circuit.openf1Key), circuit]),
);
const aliases = circuits
  .flatMap((circuit) =>
    circuit.aliases.map((alias) => ({ circuit, name: normalize(alias) })),
  )
  .sort((left, right) => right.name.length - left.name.length);
const countryCodes = new Map(
  Object.entries(catalog.hosts).flatMap(([code, host]) =>
    [code, host.name, ...host.aliases].map(
      (name) => [normalize(name), code] as const,
    ),
  ),
);

function circuitByName(value: string | null | undefined) {
  if (!value) return undefined;
  const phrase = " " + normalize(value) + " ";
  return aliases.find(({ name }) => phrase.includes(" " + name + " "))?.circuit;
}

export function sessionCircuit(venue: Venue) {
  if (venue.circuit_key) return byOpenF1Key.get(venue.circuit_key);
  return circuitByName(venue.location) ?? circuitByName(venue.event_name);
}

export function sessionHostFlag(venue: Venue & { country?: string | null }) {
  return (
    sessionCircuit(venue)?.host ??
    countryCodes.get(normalize(venue.country ?? ""))
  );
}

export function circuitRoadAssets(circuit: CircuitDefinition): {
  centreline: CircuitRoadAsset;
  profile?: CircuitRoadAsset;
} {
  const profile = circuit.widthProfile;
  const profileSource = profile && roadSources.get(profile.source);
  return {
    centreline: {
      file: `centrelines/${circuit.id}.csv`,
      width: "estimated",
      credits: catalog.roadSources["f1-circuits"].credits,
    },
    profile:
      profile && profileSource
        ? {
            file: profile.file,
            width: "profile",
            credits: profileSource.credits,
          }
        : undefined,
  };
}
