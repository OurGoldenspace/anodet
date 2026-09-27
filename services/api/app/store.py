from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

_LOCK = Lock()


def shop_id() -> str:
    value = os.environ.get("SHOP_ID", "sample").strip().lower()
    return value or "sample"


def shop_lead_name() -> str:
    return os.environ.get("SHOP_LEAD", "").strip()


def database_path() -> Path:
    override = os.environ.get("ANODET_DB")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "audit.db"


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _LOCK, connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reviewed_fixes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                unit_id INTEGER NOT NULL,
                cycle INTEGER NOT NULL,
                signature TEXT NOT NULL,
                manual_section TEXT NOT NULL,
                decision TEXT NOT NULL,
                steps TEXT NOT NULL,
                cause TEXT NOT NULL,
                resolved INTEGER NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'technician',
                author TEXT NOT NULL DEFAULT ''
            )
            """
        )
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(reviewed_fixes)")}
        if "author" not in columns:
            connection.execute("ALTER TABLE reviewed_fixes ADD COLUMN author TEXT NOT NULL DEFAULT ''")
        if "outcome" not in columns:
            connection.execute("ALTER TABLE reviewed_fixes ADD COLUMN outcome TEXT NOT NULL DEFAULT 'too_soon'")
        connection.execute("DROP TABLE IF EXISTS decisions")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS manual_sections (
                pattern TEXT PRIMARY KEY,
                section_id TEXT NOT NULL,
                title TEXT NOT NULL,
                steps TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT
            )
            """
        )
        member_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(members)")}
        if "expires_at" not in member_columns:
            connection.execute("ALTER TABLE members ADD COLUMN expires_at TEXT")
        if "role" not in member_columns:
            connection.execute("ALTER TABLE members ADD COLUMN role TEXT NOT NULL DEFAULT 'technician'")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS imported_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                raw TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS shop_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                raw TEXT NOT NULL,
                mapping TEXT NOT NULL,
                healthy_limit INTEGER NOT NULL
            )
            """
        )
        shop_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(shop_imports)")}
        if "healthy_from" not in shop_columns:
            connection.execute("ALTER TABLE shop_imports ADD COLUMN healthy_from INTEGER NOT NULL DEFAULT 1")
        if "unit_ids" not in shop_columns:
            connection.execute("ALTER TABLE shop_imports ADD COLUMN unit_ids TEXT NOT NULL DEFAULT '[]'")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS removed_units (
                unit_id INTEGER PRIMARY KEY
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tester_notes (
                member_name TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                machine TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS shop_appends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                raw TEXT NOT NULL,
                mapping TEXT NOT NULL,
                unit_id INTEGER
            )
            """
        )
        for table in (
            "reviewed_fixes",
            "manual_sections",
            "members",
            "imported_cycles",
            "shop_imports",
            "removed_units",
            "tester_notes",
            "shop_appends",
        ):
            _ensure_shop_column(connection, table)
        _migrate_manual_pk(connection)
        _migrate_tester_notes_pk(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS reviewed_fixes_shop_id ON reviewed_fixes (shop_id, id)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS members_shop_token ON members (shop_id, token)")
        connection.execute("CREATE INDEX IF NOT EXISTS shop_imports_shop_id ON shop_imports (shop_id)")


def seed_manual(sections: dict[str, dict[str, object]]) -> None:
    shop = shop_id()
    with _LOCK, connect() as connection:
        existing = connection.execute(
            "SELECT COUNT(*) FROM manual_sections WHERE shop_id = ?",
            (shop,),
        ).fetchone()
        if existing is not None and int(existing[0]) > 0:
            return
        for pattern, section in sections.items():
            connection.execute(
                """
                INSERT INTO manual_sections (shop_id, pattern, section_id, title, steps)
                VALUES (?, ?, ?, ?, ?)
                """,
                (shop, pattern, section["id"], section["title"], json.dumps(section["steps"])),
            )


def get_manual(pattern: str) -> dict[str, object] | None:
    with _LOCK, connect() as connection:
        row = connection.execute(
            """
            SELECT pattern, section_id, title, steps
            FROM manual_sections
            WHERE shop_id = ? AND pattern = ?
            """,
            (shop_id(), pattern),
        ).fetchone()
    if row is None:
        return None
    return {
        "pattern": row["pattern"],
        "id": row["section_id"],
        "title": row["title"],
        "source": "Shop manual" if str(row["pattern"]) == "shop" else "Sample shop manual",
        "steps": json.loads(str(row["steps"])),
    }


def save_manual(pattern: str, steps: list[str]) -> None:
    with _LOCK, connect() as connection:
        connection.execute(
            "UPDATE manual_sections SET steps = ? WHERE shop_id = ? AND pattern = ?",
            (json.dumps(steps), shop_id(), pattern),
        )


def upsert_manual(pattern: str, section_id: str, title: str, steps: list[str]) -> None:
    with _LOCK, connect() as connection:
        connection.execute(
            """
            INSERT INTO manual_sections (shop_id, pattern, section_id, title, steps)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(shop_id, pattern) DO UPDATE SET
                section_id = excluded.section_id,
                title = excluded.title,
                steps = excluded.steps
            """,
            (shop_id(), pattern, section_id, title, json.dumps(steps)),
        )


def ensure_shop_manual() -> None:
    if get_manual("shop") is not None:
        return
    from app.manual import SECTIONS

    section = SECTIONS["shop"]
    upsert_manual("shop", str(section["id"]), str(section["title"]), list(section["steps"]))


def save_shop_import(
    raw: str,
    mapping: dict[str, object],
    healthy_limit: int,
    healthy_from: int = 1,
    unit_ids: list[int] | None = None,
) -> None:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _LOCK, connect() as connection:
        connection.execute(
            """
            INSERT INTO shop_imports (shop_id, created_at, raw, mapping, healthy_limit, healthy_from, unit_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (shop_id(), created_at, raw, json.dumps(mapping), healthy_limit, healthy_from, json.dumps(unit_ids or [])),
        )


def mark_removed_unit(unit_id: int) -> None:
    shop = shop_id()
    with _LOCK, connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO removed_units (shop_id, unit_id) VALUES (?, ?)",
            (shop, unit_id),
        )
        connection.execute(
            "DELETE FROM reviewed_fixes WHERE shop_id = ? AND unit_id = ?",
            (shop, unit_id),
        )


def list_removed_units() -> set[int]:
    with _LOCK, connect() as connection:
        rows = connection.execute(
            "SELECT unit_id FROM removed_units WHERE shop_id = ?",
            (shop_id(),),
        ).fetchall()
    return {int(row["unit_id"]) for row in rows}


def list_shop_imports() -> list[tuple[str, dict[str, object], int, int, list[int]]]:
    with _LOCK, connect() as connection:
        rows = connection.execute(
            """
            SELECT raw, mapping, healthy_limit, healthy_from, unit_ids
            FROM shop_imports
            WHERE shop_id = ?
            ORDER BY id ASC
            """,
            (shop_id(),),
        ).fetchall()
    imports: list[tuple[str, dict[str, object], int, int, list[int]]] = []
    for row in rows:
        stored = json.loads(str(row["unit_ids"] or "[]"))
        unit_ids = [int(item) for item in stored] if isinstance(stored, list) else []
        imports.append(
            (
                str(row["raw"]),
                json.loads(str(row["mapping"])),
                int(row["healthy_limit"]),
                int(row["healthy_from"] or 1),
                unit_ids,
            )
        )
    return imports


def save_shop_append(raw: str, mapping: dict[str, object], unit_id: int | None) -> None:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _LOCK, connect() as connection:
        connection.execute(
            "INSERT INTO shop_appends (shop_id, created_at, raw, mapping, unit_id) VALUES (?, ?, ?, ?, ?)",
            (shop_id(), created_at, raw, json.dumps(mapping), unit_id),
        )


def list_shop_appends() -> list[tuple[str, dict[str, object], int | None]]:
    with _LOCK, connect() as connection:
        rows = connection.execute(
            "SELECT raw, mapping, unit_id FROM shop_appends WHERE shop_id = ? ORDER BY id ASC",
            (shop_id(),),
        ).fetchall()
    appends: list[tuple[str, dict[str, object], int | None]] = []
    for row in rows:
        unit_id = row["unit_id"]
        appends.append(
            (
                str(row["raw"]),
                json.loads(str(row["mapping"])),
                None if unit_id is None else int(unit_id),
            )
        )
    return appends


def save_fix(
    unit_id: int,
    cycle: int,
    signature: list[dict[str, str]],
    manual_section: str,
    decision: str,
    steps: list[str],
    cause: str,
    resolved: bool,
    note: str,
    author: str,
    source: str = "technician",
    outcome: str = "too_soon",
) -> dict[str, object]:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stored_outcome = outcome if outcome in {"worked", "did_not", "too_soon"} else "too_soon"
    with _LOCK, connect() as connection:
        if source == "demo":
            connection.execute(
                "DELETE FROM reviewed_fixes WHERE shop_id = ? AND source = 'demo'",
                (shop_id(),),
            )
        cursor = connection.execute(
            """
            INSERT INTO reviewed_fixes (
                shop_id, created_at, unit_id, cycle, signature, manual_section, decision,
                steps, cause, resolved, note, source, author, outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop_id(),
                created_at,
                unit_id,
                cycle,
                json.dumps(signature),
                manual_section,
                decision,
                json.dumps(steps),
                cause.strip(),
                1 if resolved else 0,
                note.strip(),
                source,
                author.strip(),
                stored_outcome,
            ),
        )
        fix_id = int(cursor.lastrowid)
    return _fix_row(
        {
            "id": fix_id,
            "created_at": created_at,
            "unit_id": unit_id,
            "cycle": cycle,
            "signature": json.dumps(signature),
            "manual_section": manual_section,
            "decision": decision,
            "steps": json.dumps(steps),
            "cause": cause.strip(),
            "resolved": 1 if resolved else 0,
            "note": note.strip(),
            "source": source,
            "author": author.strip(),
            "outcome": stored_outcome,
        }
    )


def list_fixes(limit: int = 20) -> list[dict[str, object]]:
    with _LOCK, connect() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, unit_id, cycle, signature, manual_section, decision,
                   steps, cause, resolved, note, source, author, outcome
            FROM reviewed_fixes
            WHERE shop_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (shop_id(), limit),
        ).fetchall()
    return [_fix_row(row) for row in rows]


def clear_sample_fixes() -> None:
    with _LOCK, connect() as connection:
        connection.execute(
            "DELETE FROM reviewed_fixes WHERE shop_id = ? AND source = 'demo'",
            (shop_id(),),
        )


def clear_all_fixes() -> None:
    with _LOCK, connect() as connection:
        connection.execute("DELETE FROM reviewed_fixes WHERE shop_id = ?", (shop_id(),))


def best_match(
    signature: list[dict[str, str]],
    exclude_unit: int,
) -> tuple[dict[str, object], list[dict[str, str]]] | None:
    wanted = {(mark["key"], mark["direction"]) for mark in signature}
    best: tuple[dict[str, object], list[dict[str, str]]] | None = None
    for fix in list_fixes(limit=100):
        if int(fix["unitId"]) == exclude_unit:
            continue
        stored = fix["signature"]
        if not isinstance(stored, list):
            continue
        shared = [
            mark
            for mark in stored
            if isinstance(mark, dict) and (mark.get("key"), mark.get("direction")) in wanted
        ]
        if len(shared) < 2:
            continue
        if best is None or len(shared) > len(best[1]):
            best = (fix, shared)
    return best


def _fix_row(row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "createdAt": row["created_at"],
        "unitId": int(row["unit_id"]),
        "cycle": int(row["cycle"]),
        "signature": json.loads(str(row["signature"])),
        "manualSection": row["manual_section"],
        "decision": row["decision"],
        "steps": json.loads(str(row["steps"])),
        "cause": row["cause"],
        "resolved": bool(row["resolved"]),
        "note": row["note"],
        "source": row["source"],
        "author": row["author"],
        "outcome": _outcome(row),
    }


def _outcome(row: sqlite3.Row | dict[str, object]) -> str:
    if isinstance(row, dict):
        value = str(row.get("outcome") or "too_soon")
    else:
        keys = row.keys()
        value = str(row["outcome"]) if "outcome" in keys and row["outcome"] is not None else "too_soon"
    if value in {"worked", "did_not", "too_soon"}:
        return value
    return "too_soon"


def open_member(name: str) -> dict[str, object]:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 80:
        raise ValueError("Enter your name.")
    now = datetime.now(timezone.utc)
    created_at = now.isoformat(timespec="seconds")
    expires_at = (now + timedelta(hours=12)).isoformat(timespec="seconds")
    token = secrets.token_urlsafe(32)
    with _LOCK, connect() as connection:
        row = connection.execute(
            "SELECT id, name, role FROM members WHERE shop_id = ? AND lower(name) = lower(?)",
            (shop_id(), cleaned),
        ).fetchone()
        if row is not None:
            role = _member_role(connection, cleaned, str(row["role"] or "technician"))
            connection.execute(
                "UPDATE members SET token = ?, expires_at = ?, role = ? WHERE id = ? AND shop_id = ?",
                (token, expires_at, role, int(row["id"]), shop_id()),
            )
            return {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "token": token,
                "shopId": shop_id(),
                "role": role,
            }
        role = _member_role(connection, cleaned, None)
        cursor = connection.execute(
            "INSERT INTO members (shop_id, created_at, name, token, expires_at, role) VALUES (?, ?, ?, ?, ?, ?)",
            (shop_id(), created_at, cleaned, token, expires_at, role),
        )
        return {
            "id": int(cursor.lastrowid),
            "name": cleaned,
            "token": token,
            "shopId": shop_id(),
            "role": role,
        }


def member_from_token(token: str) -> dict[str, object] | None:
    with _LOCK, connect() as connection:
        row = connection.execute(
            "SELECT id, name, token, expires_at, role FROM members WHERE token = ? AND shop_id = ?",
            (token, shop_id()),
        ).fetchone()
    if row is None or row["expires_at"] is None:
        return None
    expires_at = datetime.fromisoformat(str(row["expires_at"]))
    if expires_at < datetime.now(timezone.utc):
        return None
    role = str(row["role"] or "technician")
    if role not in {"lead", "technician"}:
        role = "technician"
    return {
        "id": int(row["id"]),
        "name": str(row["name"]),
        "token": str(row["token"]),
        "shopId": shop_id(),
        "role": role,
    }


def _member_role(connection: sqlite3.Connection, cleaned: str, current: str | None) -> str:
    named = shop_lead_name()
    leads = connection.execute(
        "SELECT COUNT(*) FROM members WHERE shop_id = ? AND role = 'lead'",
        (shop_id(),),
    ).fetchone()
    lead_count = 0 if leads is None else int(leads[0])
    if named:
        if cleaned.lower() == named.lower():
            return "lead"
        return "lead" if current == "lead" else "technician"
    if lead_count == 0:
        return "lead"
    if current in {"lead", "technician"}:
        return current
    return "technician"


def save_imported_cycles(raw: str) -> None:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _LOCK, connect() as connection:
        connection.execute(
            "INSERT INTO imported_cycles (shop_id, created_at, raw) VALUES (?, ?, ?)",
            (shop_id(), created_at, raw),
        )


def save_tester_note(member_name: str, machine: str) -> dict[str, str]:
    cleaned = " ".join(machine.split())
    if not cleaned:
        raise ValueError("Name the machine you repair twice.")
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _LOCK, connect() as connection:
        connection.execute(
            """
            INSERT INTO tester_notes (shop_id, member_name, created_at, machine)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(shop_id, member_name) DO UPDATE SET created_at = excluded.created_at, machine = excluded.machine
            """,
            (shop_id(), member_name, created_at, cleaned[:200]),
        )
    return {"name": member_name, "machine": cleaned[:200]}


def list_tester_notes() -> list[dict[str, str]]:
    with _LOCK, connect() as connection:
        rows = connection.execute(
            "SELECT member_name, machine FROM tester_notes WHERE shop_id = ? ORDER BY created_at DESC",
            (shop_id(),),
        ).fetchall()
    return [{"name": str(row["member_name"]), "machine": str(row["machine"])} for row in rows]


def tester_note_for(member_name: str) -> dict[str, str] | None:
    with _LOCK, connect() as connection:
        row = connection.execute(
            "SELECT member_name, machine FROM tester_notes WHERE shop_id = ? AND member_name = ?",
            (shop_id(), member_name),
        ).fetchone()
    if row is None:
        return None
    return {"name": str(row["member_name"]), "machine": str(row["machine"])}


def list_imported_cycles() -> list[str]:
    with _LOCK, connect() as connection:
        rows = connection.execute(
            "SELECT raw FROM imported_cycles WHERE shop_id = ? ORDER BY id ASC",
            (shop_id(),),
        ).fetchall()
    return [str(row["raw"]) for row in rows]


def _ensure_shop_column(connection: sqlite3.Connection, table: str) -> None:
    columns = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    if "shop_id" not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN shop_id TEXT NOT NULL DEFAULT 'sample'")


def _pk_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})") if int(row[5]) > 0]


def _migrate_manual_pk(connection: sqlite3.Connection) -> None:
    if set(_pk_columns(connection, "manual_sections")) == {"shop_id", "pattern"}:
        return
    connection.execute(
        """
        CREATE TABLE manual_sections_next (
            shop_id TEXT NOT NULL,
            pattern TEXT NOT NULL,
            section_id TEXT NOT NULL,
            title TEXT NOT NULL,
            steps TEXT NOT NULL,
            PRIMARY KEY (shop_id, pattern)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO manual_sections_next (shop_id, pattern, section_id, title, steps)
        SELECT shop_id, pattern, section_id, title, steps FROM manual_sections
        """
    )
    connection.execute("DROP TABLE manual_sections")
    connection.execute("ALTER TABLE manual_sections_next RENAME TO manual_sections")


def _migrate_tester_notes_pk(connection: sqlite3.Connection) -> None:
    if set(_pk_columns(connection, "tester_notes")) == {"shop_id", "member_name"}:
        return
    connection.execute(
        """
        CREATE TABLE tester_notes_next (
            shop_id TEXT NOT NULL,
            member_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            machine TEXT NOT NULL,
            PRIMARY KEY (shop_id, member_name)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO tester_notes_next (shop_id, member_name, created_at, machine)
        SELECT shop_id, member_name, created_at, machine FROM tester_notes
        """
    )
    connection.execute("DROP TABLE tester_notes")
    connection.execute("ALTER TABLE tester_notes_next RENAME TO tester_notes")
