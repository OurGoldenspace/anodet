"""Copy shop memory with SQLite's backup API so a mid-write file is not copied."""

from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def database_path() -> Path:
    override = os.environ.get("ANODET_DB")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "services" / "api" / "audit.db"


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up Anodet SQLite shop memory.")
    parser.add_argument("--dest", default="backups", help="Directory for dated copies.")
    parser.add_argument("--keep", type=int, default=14, help="Dated files to keep.")
    args = parser.parse_args()
    source = database_path()
    if not source.exists():
        raise SystemExit(f"No shop memory at {source}. Save a case first.")
    folder = Path(args.dest)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target = folder / f"anodet-{stamp}.db"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    kept = sorted(folder.glob("anodet-*.db"), reverse=True)
    for extra in kept[args.keep :]:
        extra.unlink()
    print(target)


if __name__ == "__main__":
    main()
