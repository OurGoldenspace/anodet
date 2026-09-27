from __future__ import annotations

from app.detect import Fleet, cycle_evidence
from app.manual import REVIEWED_HOT_SECTION_STEPS, section_for
from app.store import best_match, clear_sample_fixes, list_fixes, save_fix

DEMO_CAUSE = "Hot-section wear confirmed by coolant bleed and fan speed, before a borescope."


def build_case(fleet: Fleet, unit_id: int, cycle: int | None = None) -> dict[str, object]:
    engine = fleet.engines.get(unit_id)
    if engine is None:
        raise KeyError(unit_id)
    chosen_cycle = engine.warning_cycle if cycle is None else cycle
    evidence = cycle_evidence(engine, chosen_cycle, fleet.threshold)
    signature = _signature(evidence["contributors"])
    manual = section_for("shop" if engine.origin == "import" else str(evidence["pattern"]))
    own = next((item for item in list_fixes(100) if int(item["unitId"]) == unit_id), None)
    match = best_match(signature, exclude_unit=unit_id)
    shop: dict[str, object] | None = None
    if match is not None:
        fix, shared = match
        shop = {
            "unitId": fix["unitId"],
            "cycle": fix["cycle"],
            "shared": shared,
            "sharedText": _shared_text(int(fix["unitId"]), shared),
            "steps": fix["steps"],
            "cause": fix["cause"],
            "resolved": fix["resolved"],
            "outcome": fix.get("outcome") or "too_soon",
            "decision": fix["decision"],
            "manualSection": fix["manualSection"],
            "author": fix["author"],
        }
    stage = _stage(float(evidence["health"]))
    return {
        "unitId": unit_id,
        "cycle": evidence["cycle"],
        "stage": stage,
        "whatHappened": _what_happened(evidence, signature, stage),
        "evidence": evidence["contributors"],
        "signature": signature,
        "manual": manual,
        "suggestedSteps": list(shop["steps"]) if shop else list(manual["steps"]),
        "shopMemory": shop,
        "ownFix": None
        if own is None
        else {
            "cause": own["cause"],
            "resolved": own["resolved"],
            "outcome": own.get("outcome") or "too_soon",
            "steps": own["steps"],
            "author": own["author"],
        },
        "aiSummary": _summary(evidence, manual, shop, signature),
        "recallUnitId": find_recall_unit(fleet, unit_id),
    }


def attach_recall(fleet: Fleet) -> None:
    for engine in fleet.engines.values():
        if engine.unit_id in fleet.signatures:
            continue
        evidence = cycle_evidence(engine, engine.warning_cycle, fleet.threshold)
        fleet.signatures[engine.unit_id] = _signature(evidence["contributors"])
    fleet.recall = _recall_map(fleet)


def find_recall_unit(fleet: Fleet, source_id: int) -> int | None:
    if source_id not in fleet.signatures:
        attach_recall(fleet)
    return fleet.recall.get(source_id)


def save_case(
    fleet: Fleet,
    unit_id: int,
    cycle: int,
    decision: str,
    steps: list[str],
    cause: str,
    resolved: bool,
    note: str,
    author: str,
    outcome: str = "too_soon",
) -> dict[str, object]:
    case = build_case(fleet, unit_id, cycle)
    manual = case["manual"]
    assert isinstance(manual, dict)
    cleaned = [step.strip() for step in steps if step.strip()]
    if decision == "use_as_written":
        cleaned = list(manual["steps"])
    if not cleaned:
        raise ValueError("A reviewed fix needs at least one step.")
    if decision == "different_cause" and not cause.strip():
        raise ValueError("Name the cause the manual missed.")
    if not author.strip():
        raise ValueError("A reviewed fix needs the technician's name.")
    stored_cause = cause.strip() or str(manual["title"])
    stored_outcome = outcome if outcome in {"worked", "did_not", "too_soon"} else "too_soon"
    save_fix(
        unit_id=unit_id,
        cycle=int(case["cycle"]),
        signature=list(case["signature"]),
        manual_section=f"{manual['id']} {manual['title']}",
        decision=decision,
        steps=cleaned,
        cause=stored_cause,
        resolved=resolved if stored_outcome == "too_soon" else stored_outcome == "worked",
        note=note,
        author=author.strip(),
        outcome=stored_outcome,
    )
    return build_case(fleet, unit_id, int(case["cycle"]))


def seed_demo(fleet: Fleet, unit_id: int, author: str) -> dict[str, object]:
    engine = fleet.engines.get(unit_id)
    if engine is None:
        raise KeyError(unit_id)
    evidence = cycle_evidence(engine, engine.warning_cycle, fleet.threshold)
    signature = _signature(evidence["contributors"])
    manual = section_for("degradation")
    save_fix(
        unit_id=unit_id,
        cycle=engine.warning_cycle,
        signature=signature,
        manual_section=f"{manual['id']} {manual['title']}",
        decision="modify",
        steps=REVIEWED_HOT_SECTION_STEPS,
        cause=DEMO_CAUSE,
        resolved=True,
        note="Cheap checks first. The borescope can wait until bleed and fan speed agree.",
        author=author.strip() or "Sample shop",
        source="demo",
        outcome="worked",
    )
    recall = find_recall_unit(fleet, unit_id)
    return {
        "reviewedUnitId": unit_id,
        "recallUnitId": recall,
        "fixes": list_fixes(limit=5),
    }


def reset_memory() -> None:
    clear_sample_fixes()


def _signature(contributors: object) -> list[dict[str, str]]:
    marks: list[dict[str, str]] = []
    if not isinstance(contributors, list):
        return marks
    for sensor in contributors:
        if not isinstance(sensor, dict):
            continue
        direction = str(sensor.get("direction"))
        if direction not in {"high", "low"}:
            continue
        marks.append(
            {
                "key": str(sensor["key"]),
                "name": str(sensor["name"]),
                "direction": direction,
            }
        )
        if len(marks) == 3:
            break
    return marks


def _recall_map(fleet: Fleet) -> dict[int, int]:
    recall: dict[int, int] = {}
    engines = list(fleet.engines.values())
    for source in engines:
        source_marks = fleet.signatures.get(source.unit_id, [])
        best_id: int | None = None
        best_shared = 0
        for engine in engines:
            if engine.unit_id == source.unit_id or engine.pattern not in {"degradation", "shop"}:
                continue
            shared = len(_overlap(source_marks, fleet.signatures.get(engine.unit_id, [])))
            if shared > best_shared:
                best_shared = shared
                best_id = engine.unit_id
        if best_id is not None and best_shared >= 2:
            recall[source.unit_id] = best_id
    return recall


def _overlap(left: list[dict[str, str]], right: list[dict[str, str]]) -> list[dict[str, str]]:
    wanted = {(mark["key"], mark["direction"]) for mark in right}
    return [mark for mark in left if (mark["key"], mark["direction"]) in wanted]


def _shared_text(unit_id: int, shared: list[dict[str, str]]) -> str:
    parts = [f"{mark['name']} {mark['direction']}" for mark in shared]
    return f"Same signature as Engine {unit_id}: {', '.join(parts)}."


def _stage(health: float) -> str:
    if health >= 75:
        return "early"
    if health >= 45:
        return "degrading"
    return "late"


def _what_happened(
    evidence: dict[str, object],
    signature: list[dict[str, str]],
    stage: str,
) -> str:
    names = ", ".join(f"{mark['name']} {mark['direction']}" for mark in signature) or "no channel"
    return (
        f"Health is {evidence['health']} at cycle {evidence['cycle']}. "
        f"Degradation stage: {stage}. Sensors that left the healthy band: {names}."
    )


def _summary(
    evidence: dict[str, object],
    manual: dict[str, object],
    shop: dict[str, object] | None,
    signature: list[dict[str, str]],
) -> str:
    moved = ", ".join(f"{mark['name']} {mark['direction']}" for mark in signature) or "the leading channels"
    if shop is None:
        return (
            f"No reviewed shop fix matches this signature. Manual section {manual['id']} "
            f"tells the shop to book a borescope before the cheap checks. "
            f"The evidence is {moved}. A technician should reorder that if the cheap check can come first."
        )
    return (
        f"Lead with the reviewed fix from Engine {shop['unitId']}. "
        f"{shop['sharedText']} {_outcome_line(shop)} The manual section is still underneath, unchanged. "
        f"This engine shows {moved}."
    )


def _outcome_line(shop: dict[str, object]) -> str:
    outcome = str(shop.get("outcome") or "too_soon")
    if outcome == "worked":
        return "The cheaper order worked on that job."
    if outcome == "did_not":
        return "That job still needed the expensive step."
    return "The shop has not recorded whether the cheaper order worked."
