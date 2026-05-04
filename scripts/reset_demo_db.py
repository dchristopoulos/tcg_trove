"""Reset the local TCG Trove SQLite database to the seeded demo state.

This is intended for university demos only. It refuses to touch non-SQLite
database URLs and creates a timestamped backup before replacing the file.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import PROJECT_ROOT, settings
from app.db.init_db import init_db


def _sqlite_path(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise SystemExit("Refusing to reset: DATABASE_URL is not SQLite.")
    if parsed.netloc not in {"", "."}:
        raise SystemExit("Refusing to reset: unsupported SQLite URL format.")

    raw_path = unquote(parsed.path)
    if raw_path.startswith("/") and len(raw_path) > 3 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def main() -> None:
    db_path = _sqlite_path(settings.database_url)
    project_root = PROJECT_ROOT.resolve()
    if project_root not in db_path.parents and db_path != project_root / "tcg_trove.db":
        raise SystemExit(f"Refusing to reset database outside project folder: {db_path}")

    backup_dir = project_root / "backups"
    backup_dir.mkdir(exist_ok=True)
    if db_path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"{db_path.stem}-{stamp}{db_path.suffix}.bak"
        shutil.copy2(db_path, backup_path)
        try:
            db_path.unlink()
        except PermissionError as exc:
            raise SystemExit(
                "Could not reset the database because it is currently open. "
                "Stop the local server, then run this script again."
            ) from exc
        print(f"Backed up existing database to {backup_path}")

    init_db()
    print(f"Seeded demo database at {db_path}")
    print("Demo accounts: buyer/buyer123, seller/seller123, supervisor/supervisor123, admin/admin")


if __name__ == "__main__":
    main()
