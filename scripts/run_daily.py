"""Run one real EDAT processing batch from the project root."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date

from ent_weekly.database import Database
from ent_weekly.pipeline import DailyPipeline
from ent_weekly.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edat", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings.db_path)
    database.initialize()
    audit = asyncio.run(DailyPipeline(settings, database).run(args.edat))
    print({key: audit[key] for key in ("target_edat", "candidates", "included", "background_trend", "excluded")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
