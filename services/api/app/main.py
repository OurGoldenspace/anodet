from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import (
    SHOP_NAME,
    allow_sign_in,
    allow_summary,
    demo_tools_enabled,
    passphrase_hint,
    require_lead,
    require_member,
    sign_in,
)
from app.cases import attach_recall, build_case, reset_memory, save_case, seed_demo
from app.draft import draft_procedure
from app.explain import configured, explain_summary
from app.detect import Fleet, drop_imported_unit, engine_detail, import_cycles, load_fleet, refresh_summaries
from app.limits import CSV_MAX_CHARS
from app.manual import SECTIONS, save_shop_procedure, update_section
from app.shop_intake import append_shop_hours, import_shop_history, parse_manual, peek_history
from app.store import (
    shop_id,
    connect,
    clear_all_fixes,
    ensure_shop_manual,
    init_db,
    list_fixes,
    list_imported_cycles,
    list_removed_units,
    list_shop_appends,
    list_shop_imports,
    mark_removed_unit,
    list_tester_notes,
    save_shop_append,
    save_shop_import,
    save_tester_note,
    seed_manual,
    tester_note_for,
)

fleet: Fleet | None = None
logger = logging.getLogger("anodet")
logging.basicConfig(level=logging.INFO, format="%(levelname)s anodet %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global fleet
    init_db()
    seed_manual(SECTIONS)
    ensure_shop_manual()
    fleet = load_fleet()
    for raw in list_imported_cycles():
        try:
            import_cycles(fleet, raw)
        except ValueError as error:
            logger.warning("skipped stored import")
    removed = list_removed_units()
    for raw, mapping, healthy_limit, healthy_from, unit_ids in list_shop_imports():
        if unit_ids and all(unit_id in removed for unit_id in unit_ids):
            continue
        try:
            import_shop_history(fleet, raw, mapping, healthy_limit, healthy_from)
        except ValueError as error:
            logger.warning("skipped shop import")
    for unit_id in removed:
        if unit_id in fleet.engines:
            del fleet.engines[unit_id]
    for raw, mapping, unit_id in list_shop_appends():
        if unit_id is not None and unit_id in removed:
            continue
        try:
            append_shop_hours(fleet, raw, mapping, unit_id)
        except ValueError as error:
            logger.warning("skipped shop append")
    refresh_summaries(fleet)
    attach_recall(fleet)
    logger.info(
        "ready shop=%s engines=%s recommended=%s summary=%s",
        shop_id(),
        fleet.stats.get("engines"),
        fleet.recommended_unit_id,
        "xai" if configured() else "template",
    )
    yield


def _origins() -> list[str]:
    configured = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="Anodet", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


class CaseSaveRequest(BaseModel):
    unitId: int
    cycle: int
    decision: Literal["use_as_written", "modify", "different_cause"]
    steps: list[str] = Field(default_factory=list)
    cause: str = ""
    resolved: bool = True
    note: str = Field(default="", max_length=400)
    outcome: Literal["worked", "did_not", "too_soon"] = "too_soon"


class SessionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    passphrase: str = Field(min_length=1, max_length=80)


class InterestRequest(BaseModel):
    machine: str = Field(min_length=1, max_length=200)


class ManualUpdateRequest(BaseModel):
    pattern: Literal["degradation", "sensor", "mixed", "shop"]
    steps: list[str]


class ManualParseRequest(BaseModel):
    text: str = Field(min_length=8, max_length=8000)


class ShopManualRequest(BaseModel):
    title: str = Field(default="Shop procedure", max_length=80)
    id: str = Field(default="S.1", max_length=12)
    steps: list[str]


class SensorMap(BaseModel):
    column: str
    key: str = ""
    name: str = ""
    description: str = ""


class ShopMapping(BaseModel):
    unit: str
    cycle: str
    sensors: list[SensorMap] = Field(default_factory=list)
    healthyLimit: int = 20


class ShopImportRequest(BaseModel):
    csv: str = Field(min_length=1, max_length=CSV_MAX_CHARS)
    mapping: ShopMapping
    healthyFrom: int = Field(default=1, ge=1, le=2000)
    healthyLimit: int = Field(default=20, ge=8, le=2000)


class ShopAppendRequest(BaseModel):
    csv: str = Field(min_length=1, max_length=CSV_MAX_CHARS)
    mapping: ShopMapping
    unitId: int | None = None


class DraftRequest(BaseModel):
    unitId: int
    cycle: int


class ImportRequest(BaseModel):
    csv: str = Field(min_length=1, max_length=CSV_MAX_CHARS)


class ExplainMark(BaseModel):
    name: str = Field(max_length=40)
    direction: Literal["high", "low"]


class ExplainShop(BaseModel):
    unitId: int
    sharedText: str = Field(default="", max_length=400)
    author: str = Field(default="", max_length=80)
    resolved: bool = True


class ExplainRequest(BaseModel):
    unitId: int
    cycle: int
    stage: str = Field(max_length=20)
    whatHappened: str = Field(max_length=600)
    signature: list[ExplainMark] = Field(default_factory=list, max_length=3)
    manualId: str = Field(max_length=20)
    manualTitle: str = Field(max_length=80)
    template: str = Field(max_length=800)
    shop: ExplainShop | None = None


def require_fleet() -> Fleet:
    if fleet is None:
        raise HTTPException(status_code=503, detail="The fleet model is still loading. Wait a moment and refresh.")
    return fleet


def require_demo_tools() -> None:
    if not demo_tools_enabled():
        raise HTTPException(status_code=403, detail="Demo tools are off on this shop.")


def fleet_payload(loaded: Fleet) -> dict[str, object]:
    has_shop = any(engine.origin == "import" for engine in loaded.engines.values())
    return {
        "dataset": "NASA C-MAPSS FD001",
        "model": "Isolation Forest fit on cycles 1–30, plus a top-3 sensor health index",
        "shop": SHOP_NAME if has_shop else "Sample fleet",
        "hasShopAssets": has_shop,
        "recommendedUnitId": loaded.recommended_unit_id,
        "activeSensors": loaded.active_sensors,
        "droppedSensors": loaded.dropped_sensors,
        "threshold": loaded.threshold,
        "stats": loaded.stats,
        "engines": loaded.summaries,
    }


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, _error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "That request is missing a required field or uses the wrong format."},
    )


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, HTTPException):
        raise error
    logger.exception("unhandled request")
    return JSONResponse(
        status_code=500,
        content={"detail": "The shop desk hit an unexpected error. Reload and try the last step again."},
    )


@app.get("/health")
def health() -> dict[str, object]:
    database = "ok"
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
    except Exception:
        database = "error"
        logger.exception("health database check failed")
    model = "ok" if fleet is not None else "loading"
    ready = database == "ok" and fleet is not None
    payload = {
        "status": "ok" if ready else "starting",
        "database": database,
        "model": model,
        "shopId": shop_id(),
        "demoTools": demo_tools_enabled(),
    }
    if not ready:
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.get("/shop")
def shop() -> dict[str, object]:
    return {
        "name": SHOP_NAME,
        "shopId": shop_id(),
        "passphraseHint": passphrase_hint(),
        "demoTools": demo_tools_enabled(),
    }


@app.post("/session")
def post_session(body: SessionRequest, request: Request) -> dict[str, object]:
    bucket = request.client.host if request.client else body.name
    if not allow_sign_in(bucket):
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Wait a few minutes and try again.")
    try:
        session = sign_in(body.name, body.passphrase)
        logger.info("signed in shop=%s", shop_id())
        return session
    except ValueError as error:
        logger.warning("sign-in rejected")
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.get("/notes")
def get_notes(_member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    return {"notes": list_tester_notes()}


@app.get("/interest")
def get_interest(member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    note = tester_note_for(str(member["name"]))
    return {"machine": None if note is None else note["machine"]}


@app.post("/interest")
def post_interest(body: InterestRequest, member: dict[str, object] = Depends(require_member)) -> dict[str, str]:
    try:
        return save_tester_note(str(member["name"]), body.machine)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/engines")
def list_engines(_member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    return fleet_payload(require_fleet())


@app.get("/engines/{unit_id}")
def get_engine(unit_id: int, _member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    loaded = require_fleet()
    engine = loaded.engines.get(unit_id)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"Engine {unit_id} is not in this shop.")
    return engine_detail(engine)


@app.delete("/engines/{unit_id}")
def delete_engine(unit_id: int, _member: dict[str, object] = Depends(require_lead)) -> dict[str, object]:
    loaded = require_fleet()
    try:
        drop_imported_unit(loaded, unit_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Engine {unit_id} is not in this shop.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    mark_removed_unit(unit_id)
    attach_recall(loaded)
    return fleet_payload(loaded)


@app.put("/manual")
def put_manual(body: ManualUpdateRequest, _member: dict[str, object] = Depends(require_lead)) -> dict[str, object]:
    try:
        return update_section(body.pattern, body.steps)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/manual/parse")
def post_manual_parse(body: ManualParseRequest, member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    if not allow_summary(int(member["id"])):
        parsed = parse_manual(body.text)
        parsed["provider"] = "template"
        parsed["trace"] = "Model limit reached. Numbered lines were kept."
        return parsed
    try:
        return parse_manual(body.text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/manual/shop")
def post_shop_manual(body: ShopManualRequest, _member: dict[str, object] = Depends(require_lead)) -> dict[str, object]:
    try:
        return save_shop_procedure(body.title, body.id, body.steps)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/assets/preview")
def post_preview(body: ImportRequest, _member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    try:
        return peek_history(body.csv)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/assets/shop")
def post_shop_import(body: ShopImportRequest, _member: dict[str, object] = Depends(require_lead)) -> dict[str, object]:
    loaded = require_fleet()
    mapping = body.mapping.model_dump()
    try:
        imported = import_shop_history(loaded, body.csv, mapping, body.healthyLimit, body.healthyFrom)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    save_shop_import(body.csv, mapping, body.healthyLimit, body.healthyFrom, imported)
    attach_recall(loaded)
    return {"importedUnitIds": imported, "fleet": fleet_payload(loaded)}


@app.post("/assets/append")
def post_shop_append(body: ShopAppendRequest, _member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    loaded = require_fleet()
    mapping = body.mapping.model_dump()
    try:
        updated = append_shop_hours(loaded, body.csv, mapping, body.unitId)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    save_shop_append(body.csv, mapping, body.unitId)
    attach_recall(loaded)
    return {"updatedUnitIds": updated, "fleet": fleet_payload(loaded)}


@app.get("/cases/{unit_id}")
def get_case(
    unit_id: int,
    cycle: int | None = None,
    _member: dict[str, object] = Depends(require_member),
) -> dict[str, object]:
    loaded = require_fleet()
    if unit_id not in loaded.engines:
        raise HTTPException(status_code=404, detail=f"Engine {unit_id} is not in this shop.")
    try:
        return build_case(loaded, unit_id, cycle)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Cycle {cycle} is not on engine {unit_id}.") from error


@app.post("/cases/explain")
def post_explain(
    body: ExplainRequest,
    member: dict[str, object] = Depends(require_member),
) -> dict[str, object]:
    if not allow_summary(int(member["id"])):
        return {
            "summary": body.template,
            "provider": "template",
            "model": None,
            "trace": "Summary limit reached. The written summary stays.",
        }
    return explain_summary(body.model_dump(), body.template)


@app.post("/cases/draft")
def post_draft(body: DraftRequest, member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    loaded = require_fleet()
    if body.unitId not in loaded.engines:
        raise HTTPException(status_code=404, detail=f"Engine {body.unitId} is not in this shop.")
    try:
        case = build_case(loaded, body.unitId, body.cycle)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="That cycle is not on this engine.") from error
    if not allow_summary(int(member["id"])):
        manual = case["manual"]
        assert isinstance(manual, dict)
        return {
            "steps": [
                {"source": index + 1, "text": step, "sensors": [], "moved": False}
                for index, step in enumerate(manual["steps"])
            ],
            "reason": None,
            "provider": "template",
            "model": None,
            "trace": "Model limit reached. The manual order stays.",
        }
    return draft_procedure(case)


@app.get("/fixes")
def get_fixes(_member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    return {"fixes": list_fixes()}


@app.post("/cases")
def post_case(body: CaseSaveRequest, member: dict[str, object] = Depends(require_member)) -> dict[str, object]:
    loaded = require_fleet()
    if body.unitId not in loaded.engines:
        raise HTTPException(status_code=404, detail=f"Engine {body.unitId} is not in this shop.")
    try:
        return save_case(
            loaded,
            body.unitId,
            body.cycle,
            body.decision,
            body.steps,
            body.cause,
            body.resolved,
            body.note,
            str(member["name"]),
            body.outcome,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="That cycle is not on this engine.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/demo/seed")
def post_demo_seed(member: dict[str, object] = Depends(require_lead)) -> dict[str, object]:
    require_demo_tools()
    loaded = require_fleet()
    try:
        seeded = seed_demo(loaded, loaded.recommended_unit_id, str(member["name"]))
        logger.info("demo seed shop=%s", shop_id())
        return seeded
    except KeyError as error:
        raise HTTPException(status_code=404, detail="The NASA demo engine is missing.") from error


@app.post("/demo/reset")
def post_demo_reset(_member: dict[str, object] = Depends(require_lead)) -> dict[str, str]:
    require_demo_tools()
    reset_memory()
    logger.info("demo reset shop=%s", shop_id())
    return {"status": "cleared"}


@app.post("/demo/empty")
def post_demo_empty(_member: dict[str, object] = Depends(require_lead)) -> dict[str, str]:
    require_demo_tools()
    clear_all_fixes()
    logger.info("demo emptied shop=%s", shop_id())
    return {"status": "empty"}
