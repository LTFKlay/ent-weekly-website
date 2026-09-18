"""Run a bounded EDAT backfill and create the matching natural-week report.

Usage:
    .venv\\Scripts\\python.exe scripts\\backfill_week.py --start 2026-09-07 --days 7
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api" / "src"))

from ent_weekly.database import Database
from ent_weekly.pipeline import DailyPipeline, WeeklyPipeline
from ent_weekly.settings import settings


async def main(start: date, days: int, weekly_only: bool) -> None:
    database = Database(settings.db_path)
    database.initialize()
    if not weekly_only:
        daily = DailyPipeline(settings, database)
        for offset in range(days):
            target = start + timedelta(days=offset)
            print(f"START {target}", flush=True)
            audit = await daily.run(target)
            print(
                f"DONE {target} candidates={audit['candidates']} included={audit['included']} "
                f"background={audit['background_trend']} excluded={audit['excluded']}",
                flush=True,
            )

    if days == 7 and start.weekday() == 0:
        print(f"WEEKLY START {start}", flush=True)
        weekly_audit = await WeeklyPipeline(settings, database).run(start)
        print(f"WEEKLY DONE public_records={weekly_audit['public_records']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill ENT PubMed EDAT dates and optionally generate a weekly report.")
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="First EDAT date (YYYY-MM-DD).")
    parser.add_argument("--days", type=int, default=7, help="Number of consecutive dates to run.")
    parser.add_argument("--weekly-only", action="store_true", help="Generate the natural-week report without rerunning daily retrieval.")
    args = parser.parse_args()
    if args.days < 1 or args.days > 14:
        parser.error("--days must be between 1 and 14")
    asyncio.run(main(args.start, args.days, args.weekly_only))
