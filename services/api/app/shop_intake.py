from __future__ import annotations

import json
import logging
import os
import re
from io import StringIO

import httpx
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.detect import Fleet, _build_engine, register_sensor
from app.explain import MODEL, XAI_URL, configured
from app.limits import CSV_MAX_CHARS

logger = logging.getLogger("anodet")
DRAFT_TIMEOUT = 20.0
UNIT_HINTS = ("unit", "engine", "asset", "machine", "id")
CYCLE_HINTS = ("cycle", "hour", "hours", "time", "sample", "row", "index")


def check_healthy_window(healthy_from: int, healthy_limit: int) -> None:
    if healthy_from < 1 or healthy_limit < healthy_from + 7 or healthy_limit > 2000:
        raise ValueError("Mark at least eight healthy hours or cycles, ending after they start.")


def peek_history(raw: str) -> dict[str, object]:
    frame = _read_table(raw)
    if _looks_like_nasa(frame):
        return {
            "kind": "nasa",
            "headers": list(frame.columns),
            "preview": _preview(frame),
            "mapping": {
                "unit": "unit",
                "cycle": "cycle",
                "sensors": [],
                "healthyLimit": 30,
            },
            "provider": "template",
            "trace": "NASA FD001 column order. Scored with the sample-fleet model.",
        }
    mapping = _heuristic_map(frame)
    provider = "template"
    trace = "Mapped from column names. Confirm the healthy window, then import."
    if configured():
        try:
            mapping = _grok_map(frame, mapping)
            provider = "xai"
            trace = f"Grok · {MODEL} mapped the columns. Confirm before the model is fit."
        except (httpx.HTTPError, ValueError, TimeoutError) as error:
            logger.warning("column map failed %s", type(error).__name__)
            trace = "The model did not map the file. The column-name map stays."
    return {
        "kind": "shop",
        "headers": list(frame.columns),
        "preview": _preview(frame),
        "mapping": mapping,
        "provider": provider,
        "trace": trace,
    }


def parse_manual(text: str) -> dict[str, object]:
    cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if not cleaned:
        raise ValueError("Paste the procedure you actually use.")
    fallback = _split_manual(text)
    if not configured():
        return {**fallback, "provider": "template", "trace": "Split on numbered lines. Confirm before it becomes the shop manual."}
    try:
        body = _grok_manual(text)
        steps = [str(step).strip() for step in body.get("steps", []) if str(step).strip()]
        if len(steps) < 2 or len(steps) > 8:
            raise ValueError("step count")
        return {
            "id": str(body.get("id") or "S.1")[:12],
            "title": str(body.get("title") or "Shop procedure")[:80],
            "steps": steps[:8],
            "provider": "xai",
            "trace": f"Grok · {MODEL} split the page. Confirm. Saving does not change an OEM PDF.",
        }
    except (httpx.HTTPError, ValueError, TimeoutError) as error:
        logger.warning("manual parse failed %s", type(error).__name__)
        return {**fallback, "provider": "template", "trace": "The model did not split the page. Numbered lines were kept."}


def import_shop_history(
    fleet: Fleet,
    raw: str,
    mapping: dict[str, object],
    healthy_limit: int,
    healthy_from: int = 1,
) -> list[int]:
    from app.detect import import_cycles, refresh_summaries

    frame = _read_table(raw)
    if _looks_like_nasa(frame) and not mapping.get("sensors"):
        return import_cycles(fleet, raw)

    work, keys = _shop_work(raw, mapping)
    check_healthy_window(healthy_from, healthy_limit)

    next_id = max(fleet.engines) + 1
    imported: list[int] = []
    for source_unit, group in work.groupby("unit", sort=False):
        ordered = group.sort_values("cycle")
        if int(ordered["cycle"].max()) < healthy_limit:
            raise ValueError(f"Each asset needs cycles through {healthy_limit} so the healthy window exists.")
        shifted = ordered.copy()
        shifted["unit"] = next_id
        engine = _finish_shop_engine(
            next_id,
            shifted,
            keys,
            healthy_from,
            healthy_limit,
            int(source_unit),
        )
        fleet.engines[next_id] = engine
        imported.append(next_id)
        next_id += 1

    refresh_summaries(fleet)
    return imported


def append_shop_hours(
    fleet: Fleet,
    raw: str,
    mapping: dict[str, object],
    unit_id: int | None = None,
) -> list[int]:
    from app.detect import refresh_summaries

    work, keys = _shop_work(raw, mapping)
    updated: list[int] = []
    if unit_id is not None:
        engine = fleet.engines.get(unit_id)
        if engine is None or engine.origin != "import":
            raise ValueError("Append later hours to an imported asset.")
        _append_rows(engine, work, keys, fleet)
        updated.append(unit_id)
        refresh_summaries(fleet)
        return updated
    for source_unit, group in work.groupby("unit", sort=False):
        engine = next(
            (
                item
                for item in fleet.engines.values()
                if item.origin == "import" and item.source_unit == int(source_unit)
            ),
            None,
        )
        if engine is None:
            raise ValueError(f"No imported asset matches unit {int(source_unit)}. Import the history first.")
        _append_rows(engine, group, keys, fleet)
        updated.append(engine.unit_id)
    if not updated:
        raise ValueError("Those hours did not match an imported asset.")
    refresh_summaries(fleet)
    return updated


def _shop_work(raw: str, mapping: dict[str, object]) -> tuple[pd.DataFrame, list[str]]:
    frame = _read_table(raw)
    if _looks_like_nasa(frame) and not mapping.get("sensors"):
        raise ValueError("NASA files are the sample fleet. Use a shop CSV to add later hours.")
    unit_col = str(mapping["unit"])
    cycle_col = str(mapping["cycle"])
    sensors = mapping.get("sensors")
    if not isinstance(sensors, list) or len(sensors) < 2:
        raise ValueError("Map at least two numeric channels.")

    keys: list[str] = []
    for item in sensors[:8]:
        if not isinstance(item, dict):
            continue
        column = str(item["column"])
        key = _safe_key(str(item.get("key") or column))
        name = str(item.get("name") or column)[:40]
        description = str(item.get("description") or name)[:80]
        if column not in frame.columns:
            raise ValueError(f"The file has no column named {column}.")
        register_sensor(key, name, description)
        frame[key] = pd.to_numeric(frame[column], errors="coerce")
        keys.append(key)
    if len(keys) < 2:
        raise ValueError("Map at least two numeric channels.")

    work = pd.DataFrame(
        {
            "unit": pd.to_numeric(frame[unit_col], errors="coerce"),
            "cycle": pd.to_numeric(frame[cycle_col], errors="coerce"),
        }
    )
    for key in keys:
        work[key] = frame[key]
    work = work.dropna()
    if work.empty:
        raise ValueError("Those columns did not produce numeric rows.")
    return work, keys


def _append_rows(engine, extra: pd.DataFrame, keys: list[str], fleet: Fleet) -> None:
    existing = list(engine.readings.keys())
    if set(keys) != set(existing):
        raise ValueError("The new hours must use the same channels as the imported asset.")
    old = pd.DataFrame({"cycle": engine.cycles, **{key: engine.readings[key] for key in keys}})
    added = extra[["cycle", *keys]].copy()
    merged = pd.concat([old, added], ignore_index=True).drop_duplicates("cycle", keep="last").sort_values("cycle")
    rebuilt = _finish_shop_engine(
        engine.unit_id,
        merged,
        keys,
        engine.healthy_from,
        engine.healthy_limit,
        engine.source_unit if engine.source_unit is not None else engine.unit_id,
    )
    fleet.engines[engine.unit_id] = rebuilt


def _finish_shop_engine(
    unit_id: int,
    group: pd.DataFrame,
    keys: list[str],
    healthy_from: int,
    healthy_limit: int,
    source_unit: int,
):
    scored = _score_shop_group(group, keys, healthy_from, healthy_limit)
    engine = _build_engine(
        unit_id,
        scored,
        keys,
        _shop_std(scored, keys, healthy_from, healthy_limit),
        healthy_limit,
        healthy_from,
    )
    engine.origin = "import"
    engine.pattern = "shop"
    engine.source_unit = source_unit
    engine.healthy_from = healthy_from
    engine.healthy_limit = healthy_limit
    names = ", ".join(key.replace("_", " ") for key in keys[:3])
    engine.mechanism = (
        f"{names} left the healthy window the shop marked (hours {healthy_from}–{healthy_limit}). "
        "Isolation Forest was fit only on those healthy rows from this file."
    )
    engine.trained_on = f"this file, hours {healthy_from}–{healthy_limit}"
    return engine


def _score_shop_group(group: pd.DataFrame, keys: list[str], healthy_from: int, healthy_limit: int) -> pd.DataFrame:
    healthy = group[(group["cycle"] >= healthy_from) & (group["cycle"] <= healthy_limit)]
    if len(healthy) < 8:
        raise ValueError("The healthy window needs at least eight rows.")
    scaler = StandardScaler()
    scaler.fit(healthy[keys])
    forest = IsolationForest(
        n_estimators=200,
        max_samples=min(256, max(8, len(healthy))),
        contamination=0.02,
        random_state=7,
        n_jobs=1,
    )
    forest.fit(scaler.transform(healthy[keys]))
    scores = forest.decision_function(scaler.transform(group[keys]))
    threshold = float(np.quantile(forest.decision_function(scaler.transform(healthy[keys])), 0.02))
    out = group.copy()
    out["if_score"] = scores
    out["if_outlier"] = scores < threshold
    return out


def _shop_std(group: pd.DataFrame, keys: list[str], healthy_from: int, healthy_limit: int) -> pd.Series:
    window = (group["cycle"] >= healthy_from) & (group["cycle"] <= healthy_limit)
    return group.loc[window, keys].std().clip(lower=1e-6)


def _read_table(raw: str) -> pd.DataFrame:
    text = raw.strip()
    if not text:
        raise ValueError("The file is empty.")
    if len(text) > CSV_MAX_CHARS:
        raise ValueError("Import one asset file at a time.")
    first = text.splitlines()[0]
    separator = "," if "," in first else r"\s+"
    sample = pd.read_csv(StringIO(text), sep=separator, header=None, nrows=1)
    if _row_is_numeric(sample.iloc[0]):
        from app.detect import COLUMNS

        return pd.read_csv(StringIO(text), sep=separator, header=None, names=COLUMNS)
    return pd.read_csv(StringIO(text), sep=separator)


def _looks_like_nasa(frame: pd.DataFrame) -> bool:
    columns = [str(column).lower() for column in frame.columns]
    return columns[:2] == ["unit", "cycle"] and any(column.startswith("s") and column[1:].isdigit() for column in columns)


def _row_is_numeric(row: pd.Series) -> bool:
    try:
        return all(float(str(value)) == float(str(value)) for value in row.tolist()[:4])
    except (TypeError, ValueError):
        return False


def _heuristic_map(frame: pd.DataFrame) -> dict[str, object]:
    columns = [str(column) for column in frame.columns]
    unit = _best_column(columns, UNIT_HINTS) or columns[0]
    cycle = _best_column(columns, CYCLE_HINTS) or (columns[1] if len(columns) > 1 else columns[0])
    sensors = []
    for column in columns:
        if column in {unit, cycle}:
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.notna().mean() < 0.8:
            continue
        if float(numeric.std() or 0) < 1e-6:
            continue
        sensors.append(
            {
                "column": column,
                "key": _safe_key(column),
                "name": column.replace("_", " "),
                "description": column.replace("_", " "),
            }
        )
        if len(sensors) == 8:
            break
    return {"unit": unit, "cycle": cycle, "sensors": sensors, "healthyLimit": 20}


def _best_column(columns: list[str], hints: tuple[str, ...]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    for hint in hints:
        if hint in lowered:
            return lowered[hint]
    for column in columns:
        if any(hint in column.lower() for hint in hints):
            return column
    return None


def _safe_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return key[:32] or "channel"


def _preview(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for _, row in frame.head(4).iterrows():
        rows.append({str(key): _cell(row[key]) for key in frame.columns[:10]})
    return rows


def _cell(value: object) -> str | float:
    if pd.isna(value):
        return ""
    if isinstance(value, (int, float, np.integer, np.floating)):
        return round(float(value), 3)
    return str(value)[:40]


def _split_manual(text: str) -> dict[str, object]:
    steps = []
    for line in text.splitlines():
        cleaned = re.sub(r"^\s*(?:\d+[\).\]]\s*|[-*]\s*)", "", line).strip()
        if cleaned:
            steps.append(cleaned[:220])
    if len(steps) < 2:
        pieces = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        steps = pieces[:6]
    if len(steps) < 2:
        raise ValueError("The procedure needs at least two steps.")
    return {"id": "S.1", "title": "Shop procedure", "steps": steps[:8]}


def _grok_map(frame: pd.DataFrame, guess: dict[str, object]) -> dict[str, object]:
    key = os.environ.get("XAI_API_KEY", "").strip()
    headers = list(frame.columns)
    sample = _preview(frame)
    response = httpx.post(
        XAI_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": MODEL,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Map a maintenance history file to unit, cycle, and sensor channels. "
                        "Use only the given column names. Return JSON: "
                        '{"unit":"<col>","cycle":"<col>","healthyLimit":20,'
                        '"sensors":[{"column":"<col>","key":"oil_temp","name":"Oil temp","description":"sump temperature"}]}'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"headers": headers, "preview": sample, "guess": guess}),
                },
            ],
        },
        timeout=DRAFT_TIMEOUT,
    )
    response.raise_for_status()
    body = _json_content(response.json())
    unit = str(body.get("unit") or guess["unit"])
    cycle = str(body.get("cycle") or guess["cycle"])
    if unit not in headers or cycle not in headers:
        raise ValueError("mapped missing column")
    sensors = []
    for item in body.get("sensors", []):
        if not isinstance(item, dict) or item.get("column") not in headers:
            continue
        sensors.append(
            {
                "column": str(item["column"]),
                "key": _safe_key(str(item.get("key") or item["column"])),
                "name": str(item.get("name") or item["column"])[:40],
                "description": str(item.get("description") or item["column"])[:80],
            }
        )
    if len(sensors) < 2:
        raise ValueError("too few sensors")
    limit = int(body.get("healthyLimit") or guess.get("healthyLimit") or 20)
    return {"unit": unit, "cycle": cycle, "sensors": sensors[:8], "healthyLimit": max(8, min(limit, 200))}


def _grok_manual(text: str) -> dict[str, object]:
    key = os.environ.get("XAI_API_KEY", "").strip()
    response = httpx.post(
        XAI_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": MODEL,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Split a maintenance procedure into 2 to 8 short steps. "
                        "Do not add parts, tools, or checks that are not in the text. "
                        'Return JSON: {"id":"S.1","title":"...","steps":["..."]}'
                    ),
                },
                {"role": "user", "content": text[:4000]},
            ],
        },
        timeout=DRAFT_TIMEOUT,
    )
    response.raise_for_status()
    return _json_content(response.json())


def _json_content(body: dict[str, object]) -> dict[str, object]:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("empty completion")
    message = choices[0].get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ValueError("missing content")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("not an object")
    return parsed
