"""Causal race-control episodes and chronological intervention cohorts."""

from dataclasses import dataclass, field
import re

from scipy.stats import beta

HORIZON_S = 120
MIN_COHORT = 12
MIN_RACES = 3
POOLED_PRIOR_WEIGHT = 60
OUTCOMES = ("sc", "vsc", "red", "none")
LABELS = {
    "yellow": "Yellow flag",
    "double_yellow": "Double yellow",
    "stopped": "Stopped car reported",
    "retired": "Retirement reported",
    "contact": "Contact reported",
    "off_track": "Off-track car reported",
}


def intervention(row):
    text = str(row.get("message") or "").upper()
    flag = str(row.get("flag") or "").upper()
    if (
        text.startswith(("VIRTUAL SAFETY CAR DEPLOYED", "VSC DEPLOYED"))
        or flag == "VSC"
    ):
        return "vsc"
    if (
        text.startswith(("SAFETY CAR DEPLOYED", "SC DEPLOYED"))
        or flag in ("SC", "SAFETY CAR")
    ) and "VIRTUAL" not in text:
        return "sc"
    if flag == "RED" and str(row.get("scope") or "").lower() == "track":
        return "red"
    return None


def is_race_green(row):
    return (
        str(row.get("flag") or "").upper() in ("GREEN", "CLEAR")
        and str(row.get("scope") or "").lower() == "track"
        and "PIT EXIT" not in str(row.get("message") or "").upper()
    )


def current_race_control(rows):
    phase, entry_closed = None, False
    for row in rows:
        message = str(row.get("message") or "").upper()
        deployment = intervention(row)
        if deployment:
            phase = {"sc": "4", "vsc": "6", "red": "5"}[deployment]
        elif is_race_green(row):
            phase = "1"
        elif phase == "6" and message.startswith(
            ("VSC ENDING", "VIRTUAL SAFETY CAR ENDING")
        ):
            phase = "7"
        status = re.match(r"^PIT (?:LANE )?ENTRY (CLOSED|OPEN)\b", message)
        if status:
            entry_closed = status.group(1) == "CLOSED"
    return phase, entry_closed


def warning_kind(row):
    text = str(row.get("message") or "").upper()
    flag = str(row.get("flag") or "").upper().replace("_", " ")
    if flag in ("YELLOW", "DOUBLE YELLOW"):
        return flag.lower().replace(" ", "_")
    if any(
        word in text
        for word in (
            "INVESTIGATION",
            "NOTED",
            "NO CONTACT",
            "PENALTY",
            "TRACK LIMIT",
            "LAP TIME DELETED",
            "DELETED LAP",
            "PIT LANE",
            "PIT ENTRY",
        )
    ):
        return None
    if re.search(r"\b(?:CAR|CARS)\s+\d+\b", text):
        if re.search(r"\b(?:STOPPED|STATIONARY)\b", text):
            return "stopped"
        if re.search(r"\b(?:RETIRED|RETIREMENT)\b", text):
            return "retired"
        if re.search(r"\b(?:OFF TRACK|OFF THE TRACK|IN THE GRAVEL)\b", text):
            return "off_track"
        if re.search(r"\b(?:CONTACT|COLLISION|CRASHED)\b", text):
            return "contact"
    return None


@dataclass
class Episode:
    start_ms: int
    signals: list = field(default_factory=list)
    outcome: str | None = None
    response_ms: int | None = None
    restart_ms: int | None = None
    clear_ms: int | None = None
    phases: list = field(default_factory=list)
    sectors: set = field(default_factory=set)
    track_yellow: bool = False


def race_episodes(rows, start_ms):
    """Group official reports causally. Procedures and repeated flags are not samples."""
    episodes = []
    active = None
    neutral = None
    neutralised = False
    for row in sorted(rows, key=lambda item: item["session_time_ms"]):
        stamp = row["session_time_ms"]
        if stamp < start_ms:
            continue
        if str(row.get("flag") or "").upper() == "CHEQUERED":
            break
        if is_race_green(row):
            if active is not None:
                active.clear_ms = stamp
            if neutral is not None:
                neutral.restart_ms = stamp
                neutral.phases[-1][2] = stamp
            active = neutral = None
            neutralised = False
            continue
        outcome = intervention(row)
        if outcome:
            if active is not None:
                active.outcome, active.response_ms = outcome, stamp
                neutral = active
            if neutral is not None:
                if not neutral.phases:
                    neutral.phases.append([outcome, stamp, None])
                elif neutral.phases[-1][0] != outcome:
                    neutral.phases[-1][2] = stamp
                    neutral.phases.append([outcome, stamp, None])
            active = None
            neutralised = True
            continue
        sector = (
            row.get("sector")
            if str(row.get("scope") or "").lower() == "sector"
            else None
        )
        flag = str(row.get("flag") or "").upper()
        if (
            active is not None
            and sector in active.sectors
            and flag in ("GREEN", "CLEAR")
        ):
            active.sectors.discard(sector)
            if not active.sectors and not active.track_yellow:
                active.clear_ms = stamp
                active = None
            continue
        kind = warning_kind(row)
        if not kind or neutralised:
            continue
        if active is None or stamp - active.start_ms > HORIZON_S * 1000:
            active = Episode(stamp)
            episodes.append(active)
        active.signals.append((stamp, kind))
        if sector is not None and kind in ("yellow", "double_yellow"):
            active.sectors.add(sector)
        elif str(row.get("scope") or "").lower() == "track" and kind in (
            "yellow",
            "double_yellow",
        ):
            active.track_yellow = True
    return episodes


def signal_class(signals):
    kinds = {kind for _, kind in signals}
    if "double_yellow" in kinds:
        return "double_yellow"
    if kinds & {"stopped", "retired"}:
        return "stopped"
    if "yellow" in kinds:
        return "yellow"
    if "contact" in kinds:
        return "contact"
    return "off_track"


def historical_episode(episode, race, finished_ms):
    """Store only normalized evidence and label times, not raw messages."""
    start = episode.start_ms
    offset = lambda stamp: None if stamp is None else (stamp - start) / 1000
    return {
        "race": race["session_key"],
        "circuit": race["circuit_key"],
        "available_after": race["ended_epoch"],
        "signals": [[offset(stamp), kind] for stamp, kind in episode.signals],
        "outcome": episode.outcome,
        "response_s": offset(episode.response_ms),
        "restart_s": offset(episode.restart_ms),
        "clear_s": offset(episode.clear_ms),
        "coverage_s": offset(finished_ms),
        "phases": [
            [name, offset(begin), offset(end if end is not None else finished_ms)]
            for name, begin, end in episode.phases
        ],
    }


def age_matched_cohort(episodes, age_s, before_epoch):
    rows = []
    for row in episodes:
        if row["available_after"] >= before_epoch:
            continue
        response, clear = row["response_s"], row["clear_s"]
        if (response is not None and response <= age_s) or (
            clear is not None and clear <= age_s
        ):
            continue
        if row["coverage_s"] < age_s + HORIZON_S and (
            response is None or response > row["coverage_s"]
        ):
            continue
        rows.append(row)
    return rows


def matched_cohort(episodes, incident_class, age_s, before_epoch, circuit):
    return incident_cohort(
        age_matched_cohort(episodes, age_s, before_epoch),
        incident_class,
        age_s,
        circuit,
    )


def incident_cohort(reference, incident_class, age_s, circuit):
    rows = []
    for row in reference:
        at_age = [(stamp, kind) for stamp, kind in row["signals"] if stamp <= age_s]
        if at_age and signal_class(at_age) == incident_class:
            rows.append(row)
    local = [row for row in rows if row["circuit"] == circuit]
    return (local, "circuit") if supported_cohort(local) else (rows, "pooled")


def supported_cohort(rows):
    return len(rows) >= MIN_COHORT and len({row["race"] for row in rows}) >= MIN_RACES


def first_outcome(row, age_s):
    response = row["response_s"]
    return (
        row["outcome"]
        if response is not None and response <= age_s + HORIZON_S
        else "none"
    )


def outcome_counts(cohort, age_s):
    counts = dict.fromkeys(OUTCOMES, 0)
    for row in cohort:
        counts[first_outcome(row, age_s)] += 1
    return counts


def probability_forecast(cohort, age_s, scope, reference=()):
    if not supported_cohort(cohort):
        return None
    counts = outcome_counts(cohort, age_s)
    total = len(cohort) + 0.5 * len(OUTCOMES)
    if len(reference) <= len(cohort):
        reference = ()
    reference_counts = outcome_counts(reference, age_s)
    broad_total = len(reference) + 0.5 * len(OUTCOMES)
    weight = POOLED_PRIOR_WEIGHT if reference else 0
    # Center the incident estimate on the age-matched archive. Broad evidence
    # regularizes the forecast without counting overlapping races twice for the interval.
    means = {
        key: (count + 0.5 + weight * (reference_counts[key] + 0.5) / broad_total)
        / (total + weight)
        for key, count in counts.items()
    }
    sc = means["sc"] * total
    return {
        "horizon_s": HORIZON_S,
        "episodes": len(cohort),
        "scope": scope,
        "races": len({row["race"] for row in cohort}),
        "reference_episodes": len(reference),
        "outcomes_pct": {key: 100 * value for key, value in means.items()},
        "sc_interval_pct": [
            float(bound) * 100 for bound in beta.ppf([0.025, 0.975], sc, total - sc)
        ],
    }


def phase_at_pit(cohort, episode_age_s, delay_s, forecast=None):
    if len(cohort) < MIN_COHORT or not 0 < delay_s <= HORIZON_S:
        return {}
    target = episode_age_s + delay_s
    supported = [
        row
        for row in cohort
        if row["coverage_s"] >= target
        and not (
            row.get("phases") is None
            and row["outcome"] in ("sc", "vsc")
            and row["response_s"] <= target
            and row["restart_s"] is None
        )
    ]
    if not supported_cohort(supported):
        return {}
    counts = dict.fromkeys(OUTCOMES, 0)
    active = {key: dict.fromkeys(("sc", "vsc"), 0) for key in OUTCOMES}
    for row in supported:
        response = row["response_s"]
        outcome = first_outcome(row, episode_age_s)
        counts[outcome] += 1
        phases = row.get("phases")
        if phases is None:
            phases = (
                [[row["outcome"], response, row["restart_s"]]]
                if response is not None and row["restart_s"] is not None
                else []
            )
        for phase, begin, end in phases:
            if phase in ("sc", "vsc") and begin <= target < end:
                active[outcome][phase] += 1
                break
    # P(active at the pit) = sum P(first outcome) × P(phase active at pit | first outcome).
    # With a displayed forecast, use those published posterior weights in the plan as well.
    probability = (
        forecast["outcomes_pct"]
        if forecast
        else {key: count / len(supported) * 100 for key, count in counts.items()}
    )
    return {
        phase: sum(
            probability[outcome] / 100 * active[outcome][phase] / count
            for outcome, count in counts.items()
            if count
        )
        for phase in ("sc", "vsc")
    }
