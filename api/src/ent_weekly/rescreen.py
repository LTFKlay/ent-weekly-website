"""按当前规则重筛已公开文献，并同步更新静态站点读取的快照。"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .database import Database
from .llm import CLASSIFICATION_PROMPT_VERSION, DeepSeekClient
from .models import PubMedArticle
from .screening import initial_exclusion
from .settings import Settings


def _rewrite_snapshot(path: Path, public_records: dict[str, dict], audit: dict) -> int:
    """保留快照原有的日期范围，只替换仍公开记录的最新分类结果。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    original = payload.get("articles", [])
    refreshed = [public_records[str(record.get("pmid"))] for record in original if str(record.get("pmid")) in public_records]
    payload["articles"] = refreshed
    payload.setdefault("audit", {})["rescreen"] = audit
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(original) - len(refreshed)


def _rewrite_snapshots(settings: Settings, database: Database, audit: dict) -> dict[str, int]:
    public_records = {record["pmid"]: record for record in database.list_articles(10_000)}
    daily_removed = sum(_rewrite_snapshot(path, public_records, audit) for path in settings.snapshot_dir.glob("daily-*.json"))
    weekly_removed = sum(_rewrite_snapshot(path, public_records, audit) for path in settings.weekly_snapshot_dir.glob("weekly-*.json"))
    return {"daily_removed": daily_removed, "weekly_removed": weekly_removed, "public_records": len(public_records)}


async def run(*, apply: bool, reclassify: bool, limit: int | None, max_concurrent: int | None) -> dict:
    settings = Settings()
    database = Database(settings.db_path)
    database.initialize()
    records = database.list_articles(10_000)
    if limit is not None:
        records = records[:limit]

    rule_exclusions = sum(bool(initial_exclusion(PubMedArticle.model_validate(record))) for record in records)
    audit = {
        "run_id": f"rescreen-{uuid.uuid4()}",
        "prompt_version": CLASSIFICATION_PROMPT_VERSION,
        "reclassify": reclassify,
        "selected": len(records),
        "rule_exclusions": rule_exclusions,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    if not apply:
        return {**audit, "status": "dry_run"}

    llm = DeepSeekClient(settings) if reclassify else None
    semaphore = asyncio.Semaphore(max_concurrent or settings.llm_max_concurrent)

    async def process(record: dict) -> str:
        article = PubMedArticle.model_validate(record)
        rule_reason = initial_exclusion(article)
        if rule_reason:
            database.record_exclusion(audit["run_id"], article, rule_reason)
            return "exclude"
        if not llm:
            return "unchanged"
        try:
            async with semaphore:
                classification = await llm.classify_and_translate(article)
        except Exception:
            return "error"
        database.record_processed(
            audit["run_id"], article, classification, classification.screening_decision,
            classification.classification_reason, None,
        )
        return classification.screening_decision

    decisions = await asyncio.gather(*(process(record) for record in records))
    audit["included"] = decisions.count("include")
    audit["background_trend"] = decisions.count("background_trend")
    audit["excluded"] = decisions.count("exclude")
    audit["unchanged"] = decisions.count("unchanged")
    audit["errors"] = decisions.count("error")
    audit["completed_at"] = datetime.now(timezone.utc).isoformat()
    audit["snapshots"] = _rewrite_snapshots(settings, database, audit)
    return {**audit, "status": "success"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="执行写入；省略时仅输出预计受影响的记录数。")
    parser.add_argument("--reclassify", action="store_true", help="使用当前 LLM 提示词重判所有选中的公开文献。")
    parser.add_argument("--limit", type=int, help="最多处理的公开文献数，可用于先小批验证。")
    parser.add_argument("--max-concurrent", type=int, help="覆盖 LLM 并发数。")
    args = parser.parse_args()
    result = asyncio.run(run(
        apply=args.apply,
        reclassify=args.reclassify,
        limit=args.limit,
        max_concurrent=args.max_concurrent,
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
