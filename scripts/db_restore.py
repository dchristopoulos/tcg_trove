from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from app.core.config import settings


def _sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("db_restore currently supports sqlite URLs only")
    raw = database_url.replace("sqlite:///", "", 1)
    return Path(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore sqlite DB from backup file.")
    parser.add_argument("--from", dest="source_file", required=True, help="Path to backup .db file")
    args = parser.parse_args()

    source = Path(args.source_file).resolve()
    if not source.exists():
        raise RuntimeError(f"Backup file does not exist: {source}")

    destination = _sqlite_path_from_url(settings.database_url).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(f"Database restored from {source} to {destination}")


if __name__ == "__main__":
    main()

