"""Restore structured-abstract labels in existing Chinese translations."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api" / "src"))

from ent_weekly.database import Database
from ent_weekly.llm import DeepSeekClient
from ent_weekly.models import PubMedArticle
from ent_weekly.settings import settings


STRUCTURED_LABEL = re.compile(r"(?m)^[A-Z][A-Z /-]{1,48}:\s")


def update_snapshot(path: Path, translations: dict[str, dict[str, str]]) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    updated = 0
    for record in payload.get("articles", []):
        translation = translations.get(str(record.get("pmid")))
        classification = record.get("classification")
        if translation and isinstance(classification, dict):
            classification.update(translation)
            updated += 1
    if updated:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated


async def main(week_start: str | None, limit: int | None, max_concurrent: int | None) -> None:
    database = Database(settings.db_path)
    records = [
        record
        for record in database.list_articles(1000)
        if STRUCTURED_LABEL.search(record["abstract_en"])
        and not re.match(r"^[^\n：]{1,30}：", (record.get("classification") or {}).get("abstract_zh", ""))
    ]
    if limit is not None:
        records = records[:limit]
    llm = DeepSeekClient(settings)
    semaphore = asyncio.Semaphore(max_concurrent or settings.llm_max_concurrent)

    async def translate(record: dict) -> tuple[str, dict[str, str] | None]:
        article = PubMedArticle.model_validate(record)
        try:
            async with semaphore:
                return article.pmid, await llm.translate_title_and_abstract(article)
        except Exception:
            return article.pmid, None

    translations: dict[str, dict[str, str]] = {}
    completed = 0
    for task in asyncio.as_completed([translate(record) for record in records]):
        pmid, translation = await task
        completed += 1
        if translation:
            translations[pmid] = translation
            database.update_translation(pmid, translation["title_zh"], translation["abstract_zh"])
        print(f"Processed {completed}/{len(records)}; translated {len(translations)}.", flush=True)

    snapshot_updates = 0
    for path in settings.snapshot_dir.glob("daily-*.json"):
        snapshot_updates += update_snapshot(path, translations)
    for path in settings.weekly_snapshot_dir.glob("weekly-*.json"):
        if not week_start or path.name == f"weekly-{week_start}.json":
            snapshot_updates += update_snapshot(path, translations)
    print(f"Translated {len(translations)}/{len(records)} structured abstracts; updated {snapshot_updates} snapshot records.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-start", help="Optional weekly snapshot to update (YYYY-MM-DD).")
    parser.add_argument("--limit", type=int, help="Optional maximum records, for a controlled refresh.")
    parser.add_argument("--max-concurrent", type=int, help="Optional concurrent translation requests.")
    args = parser.parse_args()
    asyncio.run(main(args.week_start, args.limit, args.max_concurrent))
