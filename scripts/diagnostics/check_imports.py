"""
Fast fail import check for backend/worker modules.
Exits non-zero if critical imports fail.
"""
import importlib
import sys
from typing import List


MODULES: List[str] = [
    "config",
    "services.ai_service",
    "services.pdf_service",
    "services.db_service",
    "services.cache_service",
    "workers.tasks",
    "api.health",
]


def main() -> int:
    failed = []
    for mod in MODULES:
        try:
            importlib.import_module(mod)
            print(f"[OK] {mod}")
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {mod}: {exc}", file=sys.stderr)
            failed.append(mod)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())


