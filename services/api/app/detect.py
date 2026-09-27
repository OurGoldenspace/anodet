from __future__ import annotations

import os
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.limits import CSV_MAX_CHARS

HEALTHY_CYCLE_LIMIT = 30
SMOOTH_WINDOW = 8
WARNING_HEALTH = 60.0
CRITICAL_HEALTH = 35.0

SENSOR_META: dict[str, tuple[str, str]] = {
    "s2": ("T24", "LPC outlet temperature"),
    "s3": ("T30", "HPC outlet temperature"),
    "s4": ("T50", "LPT outlet temperature"),
    "s7": ("P30", "HPC outlet pressure"),
    "s8": ("Nf", "Physical fan speed"),
    "s9": ("Nc", "Physical core speed"),
    "s11": ("Ps30", "HPC outlet static pressure"),
    "s12": ("phi", "Fuel-flow to Ps30 ratio"),
    "s13": ("NRf", "Corrected fan speed"),
    "s14": ("NRc", "Corrected core speed"),
    "s15": ("BPR", "Bypass ratio"),
    "s17": ("htBleed", "Bleed enthalpy"),
    "s20": ("W31", "HPT coolant bleed"),
    "s21": ("W32", "LPT coolant bleed"),
}

# Sign of the drift NASA's FD001 wear pattern produces. +1 rises, -1 falls.
EXPECTED_DIRECTION: dict[str, int] = {
    "s2": 1,
    "s3": 1,
    "s4": 1,
    "s7": -1,
    "s8": 1,
    "s9": 1,
    "s11": 1,
    "s12": -1,
    "s13": 1,
    "s14": 1,
    "s15": 1,
    "s17": 1,
    "s20": -1,
    "s21": -1,
}

COLUMNS = ["unit", "cycle", "op1", "op2", "op3", *[f"s{index}" for index in range(1, 22)]]


@dataclass
class EngineRecord:
    unit_id: int
    cycles: np.ndarray
    health: np.ndarray
    anomaly: np.ndarray
    if_outlier: np.ndarray
    if_score: np.ndarray
    readings: dict[str, np.ndarray]
    zscores: dict[str, np.ndarray]
    baseline: dict[str, float]
    warning_index: int
    critical_index: int | None
    agreement: float
    pattern: str
    mechanism: str
    top_sensors: list[dict[str, object]] = field(default_factory=list)
    origin: str = "sample"
    trained_on: str = "cycles 1–30 across the fleet, before degradation is fit"
    source_unit: int | None = None
    healthy_from: int = 1
    healthy_limit: int = 30

    @property
    def life(self) -> int:
        return int(self.cycles[-1])

    @property
    def warning_cycle(self) -> int:
        return int(self.cycles[self.warning_index])

    @property
    def lead_time(self) -> int:
        return self.life - self.warning_cycle


@dataclass
class Fleet:
    engines: dict[int, EngineRecord]
    summaries: list[dict[str, object]]
    recommended_unit_id: int
    active_sensors: list[str]
    dropped_sensors: list[str]
    threshold: float
    stats: dict[str, float | int]
    healthy_std: pd.Series
    scaler: StandardScaler
    forest: IsolationForest
    signatures: dict[int, list[dict[str, str]]] = field(default_factory=dict)
    recall: dict[int, int] = field(default_factory=dict)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "cmapss" / "train_FD001.txt"
        if candidate.exists():
            return parent
    raise FileNotFoundError("Could not find data/cmapss/train_FD001.txt")


def dataset_path() -> Path:
    override = os.environ.get("ANODET_DATA")
    if override:
        return Path(override)
    return repo_root() / "data" / "cmapss" / "train_FD001.txt"


def load_fleet(path: Path | None = None) -> Fleet:
    frame = pd.read_csv(path or dataset_path(), sep=r"\s+", header=None, names=COLUMNS)
    sensor_columns = [f"s{index}" for index in range(1, 22)]
    spread = frame[sensor_columns].std()
    active = [column for column in sensor_columns if float(spread[column]) > 0.01]
    dropped = [column for column in sensor_columns if column not in active]

    healthy_mask = frame["cycle"] <= HEALTHY_CYCLE_LIMIT
    scaler = StandardScaler()
    scaler.fit(frame.loc[healthy_mask, active])
    scaled = scaler.transform(frame[active])
    forest = IsolationForest(
        n_estimators=200,
        max_samples=512,
        contamination=0.01,
        random_state=7,
        n_jobs=1,
    )
    healthy_rows = healthy_mask.to_numpy()
    forest.fit(scaled[healthy_rows])
    scores = forest.decision_function(scaled)
    threshold = float(np.quantile(scores[healthy_rows], 0.02))
    outliers = scores < threshold

    frame = frame.copy()
    frame["if_score"] = scores
    frame["if_outlier"] = outliers

    healthy_std = frame.loc[healthy_mask, active].std().clip(lower=1e-6)
    engines: dict[int, EngineRecord] = {}
    for unit_id, group in frame.groupby("unit"):
        engines[int(unit_id)] = _build_engine(int(unit_id), group.sort_values("cycle"), active, healthy_std)

    late_mask = frame.groupby("unit")["cycle"].transform("max") - frame["cycle"] <= 30
    stats: dict[str, float | int] = {
        "engines": len(engines),
        "cycles": int(len(frame)),
        "features": len(active),
        "estimators": 200,
        "healthyOutlierRate": round(float(outliers[healthy_rows].mean()), 3),
        "lateLifeOutlierRate": round(float(outliers[late_mask.to_numpy()].mean()), 3),
        "medianLeadTime": int(np.median([engine.lead_time for engine in engines.values()])),
    }

    summaries = [_summary(engine) for engine in engines.values()]
    summaries.sort(key=lambda item: int(item["leadTime"]), reverse=True)
    recommended = _recommend(list(engines.values()))
    return Fleet(
        engines=engines,
        summaries=summaries,
        recommended_unit_id=recommended,
        active_sensors=active,
        dropped_sensors=dropped,
        threshold=round(threshold, 4),
        stats=stats,
        healthy_std=healthy_std,
        scaler=scaler,
        forest=forest,
    )


def register_sensor(key: str, name: str, description: str) -> None:
    SENSOR_META[key] = (name, description)


def sensor_meta(key: str) -> tuple[str, str]:
    if key in SENSOR_META:
        return SENSOR_META[key]
    return (key.replace("_", " "), key)


def _build_engine(
    unit_id: int,
    group: pd.DataFrame,
    active: list[str],
    healthy_std: pd.Series,
    healthy_limit: int = HEALTHY_CYCLE_LIMIT,
    healthy_from: int = 1,
) -> EngineRecord:
    baseline_rows = group[(group["cycle"] >= healthy_from) & (group["cycle"] <= healthy_limit)]
    baseline_mean = baseline_rows[active].mean()
    zscores = (group[active] - baseline_mean) / healthy_std
    z_matrix = zscores.to_numpy()
    top3 = np.sort(np.abs(z_matrix), axis=1)[:, -3:].mean(axis=1)
    instant = 100 / (1 + np.exp(1.35 * (top3 - 3.1)))
    health = _rolling_mean(instant, SMOOTH_WINDOW)
    cycles = group["cycle"].to_numpy(dtype=int)
    warning_index = _first_index(cycles, health, WARNING_HEALTH, healthy_limit=healthy_limit)
    critical_index = _first_index(
        cycles, health, CRITICAL_HEALTH, start_index=warning_index, healthy_limit=healthy_limit
    )
    if critical_index is not None and critical_index <= warning_index:
        critical_index = None

    warning_z = {sensor: float(zscores.iloc[warning_index][sensor]) for sensor in active}
    agreement, pattern, mechanism, top_sensors = describe_sensors(warning_z)

    anomaly = health <= WARNING_HEALTH

    return EngineRecord(
        unit_id=unit_id,
        cycles=cycles,
        health=health,
        anomaly=anomaly,
        if_outlier=group["if_outlier"].to_numpy(),
        if_score=group["if_score"].to_numpy(dtype=float),
        readings={sensor: group[sensor].to_numpy(dtype=float) for sensor in active},
        zscores={sensor: zscores[sensor].to_numpy(dtype=float) for sensor in active},
        baseline={sensor: float(baseline_mean[sensor]) for sensor in active},
        warning_index=warning_index,
        critical_index=critical_index,
        agreement=agreement,
        pattern=pattern,
        mechanism=mechanism,
        top_sensors=top_sensors,
    )


def describe_sensors(
    zscores: dict[str, float],
) -> tuple[float, str, str, list[dict[str, object]]]:
    ranked = sorted(zscores.items(), key=lambda item: abs(item[1]), reverse=True)
    moving = [(sensor, value) for sensor, value in ranked if abs(value) >= 1.5]
    compared = moving or ranked[:3]
    matches = [
        sensor
        for sensor, value in compared
        if value * EXPECTED_DIRECTION.get(sensor, 0) > 0
    ]
    agreement = len(matches) / len(compared) if compared else 0.0
    top_sensors = [_sensor_payload(sensor, value, zscores) for sensor, value in ranked[:4]]

    lead_sensor, lead_z = ranked[0]
    second_z = ranked[1][1] if len(ranked) > 1 else 0.0
    lead_name = sensor_meta(lead_sensor)[0]
    if abs(lead_z) >= 3.2 and abs(second_z) < 1.4:
        mechanism = (
            f"{lead_name} moved {abs(lead_z):.1f}σ from this engine's healthy baseline "
            "while the rest of the suite stayed quiet. That looks like a probe or channel "
            "fault, not distributed hot-section wear."
        )
        return agreement, "sensor", mechanism, top_sensors

    if agreement >= 0.7 and len(moving) >= 3:
        names = ", ".join(sensor_meta(sensor)[0] for sensor, _value in moving[:3])
        mechanism = (
            f"{names} moved together, and {len(matches)} of {len(compared)} drifting "
            "channels match the FD001 hot-section wear signature. This is engine "
            "degradation, not a single bad sensor."
        )
        return agreement, "degradation", mechanism, top_sensors

    mechanism = (
        "Several channels left the healthy band, but their signs only partly match "
        "the usual wear signature. Treat this as a mixed pattern and confirm it "
        "before writing a shop order."
    )
    return agreement, "mixed", mechanism, top_sensors


def _sensor_payload(sensor: str, z_score: float, _zscores: dict[str, float]) -> dict[str, object]:
    name, description = sensor_meta(sensor)
    direction = "nominal"
    if z_score >= 1.2:
        direction = "high"
    elif z_score <= -1.2:
        direction = "low"
    return {
        "key": sensor,
        "name": name,
        "description": description,
        "zScore": round(float(z_score), 2),
        "direction": direction,
    }


def cycle_evidence(engine: EngineRecord, cycle: int, threshold: float) -> dict[str, object]:
    index = _index_for_cycle(engine, cycle)
    zscores = {sensor: float(engine.zscores[sensor][index]) for sensor in engine.zscores}
    agreement, pattern, mechanism, top_sensors = describe_sensors(zscores)
    contributors = []
    for sensor in top_sensors:
        key = str(sensor["key"])
        reading = float(engine.readings[key][index])
        baseline = engine.baseline[key]
        contributors.append(
            {
                **sensor,
                "value": round(reading, 3),
                "baseline": round(baseline, 3),
                "delta": round(reading - baseline, 3),
            }
        )

    health = float(engine.health[index])
    rul = engine.life - int(engine.cycles[index])
    is_anomaly = bool(engine.anomaly[index])
    if_outlier = bool(engine.if_outlier[index])
    return {
        "unitId": engine.unit_id,
        "cycle": int(engine.cycles[index]),
        "lifeCycles": engine.life,
        "health": round(health, 1),
        "rul": rul,
        "isAnomaly": is_anomaly,
        "pattern": pattern,
        "agreement": round(agreement, 2),
        "mechanism": mechanism,
        "contributors": contributors,
        "warningCycle": engine.warning_cycle,
        "leadTime": engine.lead_time,
        "isolationForest": {
            "isOutlier": if_outlier,
            "score": round(float(engine.if_score[index]), 4),
            "threshold": threshold,
            "trainedOn": engine.trained_on,
        },
    }


def engine_detail(engine: EngineRecord) -> dict[str, object]:
    signature = [str(sensor["key"]) for sensor in engine.top_sensors]
    series = []
    for index, cycle in enumerate(engine.cycles):
        series.append(
            {
                "cycle": int(cycle),
                "health": round(float(engine.health[index]), 1),
                "isAnomaly": bool(engine.anomaly[index]),
                "rul": engine.life - int(cycle),
                "readings": {
                    sensor: round(float(engine.readings[sensor][index]), 3) for sensor in signature
                },
            }
        )
    return {
        "unitId": engine.unit_id,
        "lifeCycles": engine.life,
        "warningCycle": engine.warning_cycle,
        "criticalCycle": None
        if engine.critical_index is None
        else int(engine.cycles[engine.critical_index]),
        "leadTime": engine.lead_time,
        "healthAtWarning": round(float(engine.health[engine.warning_index]), 1),
        "pattern": engine.pattern,
        "agreement": round(engine.agreement, 2),
        "mechanism": engine.mechanism,
        "origin": engine.origin,
        "trainedOn": engine.trained_on,
        "signatureSensors": [
            {
                "key": sensor,
                "name": sensor_meta(sensor)[0],
                "description": sensor_meta(sensor)[1],
                "baseline": round(engine.baseline[sensor], 3),
            }
            for sensor in signature
        ],
        "series": series,
    }


def _summary(engine: EngineRecord) -> dict[str, object]:
    if engine.pattern == "sensor":
        status = "sensor"
    elif engine.lead_time >= 50:
        status = "early"
    elif engine.lead_time <= 20:
        status = "late"
    else:
        status = "actionable"
    return {
        "unitId": engine.unit_id,
        "lifeCycles": engine.life,
        "warningCycle": engine.warning_cycle,
        "criticalCycle": None
        if engine.critical_index is None
        else int(engine.cycles[engine.critical_index]),
        "leadTime": engine.lead_time,
        "healthAtWarning": round(float(engine.health[engine.warning_index]), 1),
        "agreement": round(engine.agreement, 2),
        "pattern": engine.pattern,
        "status": status,
        "mechanism": engine.mechanism,
        "topSensors": engine.top_sensors[:3],
        "origin": engine.origin,
    }


def _recommend(engines: list[EngineRecord]) -> int:
    imported = [engine for engine in engines if engine.origin == "import"]
    pool = imported or engines
    ranked = sorted(
        pool,
        key=lambda engine: (
            engine.pattern in {"degradation", "shop"} and 20 <= engine.lead_time <= 70,
            engine.agreement,
            -abs(engine.lead_time - 45),
        ),
        reverse=True,
    )
    return ranked[0].unit_id


def refresh_summaries(fleet: Fleet) -> None:
    fleet.summaries = [_summary(engine) for engine in fleet.engines.values()]
    fleet.summaries.sort(key=lambda item: int(item["leadTime"]), reverse=True)
    fleet.stats["engines"] = len(fleet.engines)
    if fleet.engines:
        fleet.recommended_unit_id = _recommend(list(fleet.engines.values()))


def drop_imported_unit(fleet: Fleet, unit_id: int) -> None:
    engine = fleet.engines.get(unit_id)
    if engine is None:
        raise KeyError(unit_id)
    if engine.origin != "import":
        raise ValueError("Only an imported asset can be removed. The sample fleet stays.")
    del fleet.engines[unit_id]
    refresh_summaries(fleet)


def import_cycles(fleet: Fleet, raw: str) -> list[int]:
    frame = _parse_cycles(raw)
    next_id = max(fleet.engines) + 1
    pieces: list[pd.DataFrame] = []
    for _, group in frame.groupby("unit", sort=False):
        ordered = group.sort_values("cycle")
        if int(ordered["cycle"].max()) < HEALTHY_CYCLE_LIMIT:
            raise ValueError("Each imported engine needs cycles through 30 so the healthy baseline exists.")
        shifted = ordered.copy()
        shifted["unit"] = next_id
        pieces.append(shifted)
        next_id += 1
    merged = pd.concat(pieces, ignore_index=True)
    active = fleet.active_sensors
    scaled = fleet.scaler.transform(merged[active])
    scores = fleet.forest.decision_function(scaled)
    merged["if_score"] = scores
    merged["if_outlier"] = scores < fleet.threshold
    imported: list[int] = []
    for unit_id, group in merged.groupby("unit"):
        engine = _build_engine(int(unit_id), group.sort_values("cycle"), active, fleet.healthy_std)
        engine.origin = "import"
        fleet.engines[int(unit_id)] = engine
        imported.append(int(unit_id))
    fleet.summaries = [_summary(engine) for engine in fleet.engines.values()]
    fleet.summaries.sort(key=lambda item: int(item["leadTime"]), reverse=True)
    fleet.stats["engines"] = len(fleet.engines)
    fleet.stats["cycles"] = int(fleet.stats["cycles"]) + int(len(merged))
    return imported


def _parse_cycles(raw: str) -> pd.DataFrame:
    text = raw.strip()
    if not text:
        raise ValueError("The file is empty.")
    if len(text) > CSV_MAX_CHARS:
        raise ValueError("Import one engine file at a time.")
    first = text.splitlines()[0]
    separator = "," if "," in first else r"\s+"
    frame = pd.read_csv(StringIO(text), sep=separator, header=None, names=COLUMNS)
    if not _is_number(frame.iloc[0]["unit"]):
        frame = frame.iloc[1:].copy()
    frame = frame.apply(pd.to_numeric, errors="coerce").dropna(how="all")
    if frame.empty or frame[["unit", "cycle"]].isna().any().any():
        raise ValueError("Each row needs a numeric unit and cycle, then the NASA sensor columns.")
    return frame


def _is_number(value: object) -> bool:
    try:
        float(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _first_index(
    cycles: np.ndarray,
    health: np.ndarray,
    level: float,
    start_index: int = 0,
    healthy_limit: int = HEALTHY_CYCLE_LIMIT,
) -> int | None:
    begin = max(start_index, 0)
    for index in range(begin, len(cycles)):
        if int(cycles[index]) <= healthy_limit + SMOOTH_WINDOW:
            continue
        if health[index] <= level and float(np.mean(health[index:] <= level + 12)) > 0.85:
            return index
    if start_index > 0:
        return None
    return len(cycles) - 1


def _index_for_cycle(engine: EngineRecord, cycle: int) -> int:
    matches = np.where(engine.cycles == cycle)[0]
    if len(matches) == 0:
        raise KeyError(cycle)
    return int(matches[0])


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    result = np.empty(len(values), dtype=float)
    running = 0.0
    for index, value in enumerate(values):
        running += float(value)
        if index >= window:
            running -= float(values[index - window])
        count = min(index + 1, window)
        result[index] = running / count
    return result
