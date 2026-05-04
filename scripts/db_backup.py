from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings


def _sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("db_backup currently supports sqlite URLs only")
    raw = database_url.replace("sqlite:///", "", 1)
    return Path(raw)


def main() -> None:
    source = _sqlite_path_from_url(settings.database_url)
    if not source.exists():
        raise RuntimeError(f"Database file not found: {source}")
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"tcg_trove-{stamp}.db"
    shutil.copy2(source, target)
    print(f"Backup created: {target}")


if __name__ == "__main__":
    main()

