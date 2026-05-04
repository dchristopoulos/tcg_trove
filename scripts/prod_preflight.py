import argparse
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.production_preflight import evaluate_production_env


def _load_env(env_file: str) -> dict[str, str]:
    values: dict[str, str] = {}
    file_path = Path(env_file)
    if file_path.exists():
        parsed = dotenv_values(file_path)
        for key, value in parsed.items():
            if value is None:
                continue
            values[key] = value

    # Environment variables override .env file values.
    for key, value in os.environ.items():
        values[key] = value

    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Run production configuration preflight checks.")
    parser.add_argument("--env-file", default=".env", help="Path to .env file (default: .env)")
    args = parser.parse_args()

    env = _load_env(args.env_file)
    errors, warnings = evaluate_production_env(env)

    print("Production preflight report")
    print("==========================")

    if errors:
        print("FAIL")
        for item in errors:
            print(f"- ERROR: {item}")
    else:
        print("PASS")

    for item in warnings:
        print(f"- WARN: {item}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
