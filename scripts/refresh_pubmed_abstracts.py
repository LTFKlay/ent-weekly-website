"""Refresh stored PubMed abstracts without changing screening or classifications.

Use after parser changes that affect source-format fidelity, such as structured
abstract labels. Existing screening decisions and Chinese translations remain
unchanged; only the source English abstract is replaced from PubMed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api" / "src"))

from ent_weekly.database import Database
from ent_weekly.pubmed import PubMedClient
from ent_weekly.settings import settings


def update_snapshot(path: Path, abstracts: dict[str, str]) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    updated = 0
    for record in payload.get("articles", []):
        abstract = abstracts.get(str(record.get("pmid")))
        if abstract and record.get("abstract_en") != abstract:
            record["abstract_en"] = abstract
            updated += 1
    if updated:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated


async def main(week_start: str | None) -> None:
    database = Database(settings.db_path)
    database.initialize()
    pmids = database.list_public_pmids()
    if not pmids:
        raise RuntimeError("No published records found.")
    client = PubMedClient(settings, ROOT / "api" / "config" / "topic-queries.json")
    refreshed = await client.fetch_articles(pmids)
    abstracts = {article.pmid: article.abstract_en for article in refreshed}
    for article in refreshed:
        database.upsert_candidate(article)

    updated_snapshots = 0
    for path in settings.snapshot_dir.glob("daily-*.json"):
        updated_snapshots += update_snapshot(path, abstracts)
    for path in settings.weekly_snapshot_dir.glob("weekly-*.json"):
        if week_start and path.name != f"weekly-{week_start}.json":
            continue
        updated_snapshots += update_snapshot(path, abstracts)
    print(f"Refreshed {len(refreshed)} PubMed abstracts; updated {updated_snapshots} snapshot records.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-start", help="Optional weekly snapshot to update (YYYY-MM-DD).")
    args = parser.parse_args()
    asyncio.run(main(args.week_start))
