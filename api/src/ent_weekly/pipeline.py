import json
import uuid
import asyncio
from datetime import date
from pathlib import Path

from .database import Database
from .llm import DeepSeekClient
from .pubmed import PubMedClient
from .quality import QualityGate
from .screening import initial_exclusion
from .settings import Settings


class DailyPipeline:
    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.pubmed = PubMedClient(settings, Path(__file__).parents[2] / "config" / "topic-queries.json")
        self.quality = QualityGate(settings.journal_quality_path)
        self.llm = DeepSeekClient(settings)

    async def run(self, target_edat: date) -> dict:
        run_id = str(uuid.uuid4())
        articles, retrieval = await self.pubmed.retrieve("edat", target_edat.isoformat(), target_edat.isoformat())
        pending = [article for article in articles if not self.database.has_llm_record(article.pmid)]
        audit = {"run_id": run_id, "target_edat": target_edat.isoformat(), "retrieval": retrieval, "candidates": len(articles), "pending": len(pending), "included": 0, "background_trend": 0, "excluded": 0}
        self.database.start_run(run_id, target_edat.isoformat(), retrieval["query_version"], audit)
        try:
            semaphore = asyncio.Semaphore(self.settings.llm_max_concurrent)

            async def process(article):
                async with semaphore:
                    return await self._process_article(run_id, article)

            for decision in await asyncio.gather(*(process(article) for article in pending)):
                if decision == "exclude":
                    audit["excluded"] += 1
                elif decision == "include":
                    audit["included"] += 1
                else:
                    audit[decision] += 1
            totals = self.database.decision_counts_for_edat(target_edat.isoformat())
            audit["included"] = totals.get("include", 0)
            audit["background_trend"] = totals.get("background_trend", 0)
            audit["excluded"] = totals.get("exclude", 0)
            self._write_snapshot(target_edat, audit)
            self.database.finish_run(run_id, "success", audit)
            return audit
        except Exception:
            self.database.finish_run(run_id, "failed", audit)
            raise

    async def _process_article(self, run_id: str, article) -> str:
        classification = await self.llm.classify_and_translate(article)
        quality, quality_reason = self.quality.resolve(article)
        rule_exclusion = initial_exclusion(article)
        decision = classification.screening_decision
        reason = classification.classification_reason
        if rule_exclusion:
            decision, reason = "exclude", rule_exclusion
        elif quality_reason:
            decision, reason = "exclude", quality_reason
        self.database.record_processed(run_id, article, classification, decision, reason, quality)
        return decision

    def _write_snapshot(self, target_edat: date, audit: dict) -> None:
        self.settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
        output = self.settings.snapshot_dir / f"daily-{target_edat.isoformat()}.json"
        output.write_text(json.dumps({"audit": audit, "articles": self.database.list_articles(250)}, ensure_ascii=False, indent=2), encoding="utf-8")
