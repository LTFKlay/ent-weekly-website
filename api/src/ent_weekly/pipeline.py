import json
import uuid
import asyncio
from datetime import date, datetime, timezone
from pathlib import Path

from .database import Database
from .llm import DeepSeekClient, WEEKLY_PROMPT_VERSION
from .models import WeeklySection, WeeklySummary
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
        quality, quality_reason = self.quality.resolve(article)
        rule_exclusion = initial_exclusion(article)
        if rule_exclusion or quality_reason:
            self.database.record_exclusion(run_id, article, rule_exclusion or quality_reason or "Exclude: quality gate.")
            return "exclude"
        try:
            classification = await self.llm.classify_and_translate(article)
        except Exception as error:
            self.database.record_exclusion(run_id, article, f"Exclude: LLM classification unavailable ({type(error).__name__}).")
            return "exclude"
        decision = classification.screening_decision
        reason = classification.classification_reason
        self.database.record_processed(run_id, article, classification, decision, reason, quality)
        return decision

    def _write_snapshot(self, target_edat: date, audit: dict) -> None:
        self.settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
        output = self.settings.snapshot_dir / f"daily-{target_edat.isoformat()}.json"
        output.write_text(json.dumps({"audit": audit, "articles": self.database.list_articles(250)}, ensure_ascii=False, indent=2), encoding="utf-8")


class WeeklyPipeline:
    """Build one auditable natural-week summary from already screened EDAT records."""

    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.llm = DeepSeekClient(settings)

    async def run(self, week_start: date) -> dict:
        week_end = date.fromordinal(week_start.toordinal() + 6)
        records = self.database.list_articles_for_edat_week(week_start.isoformat(), week_end.isoformat())
        if not records:
            raise RuntimeError("No screened public EDAT records are available for this report week.")
        grouped: dict[tuple[str, str], list[dict]] = {}
        for record in records:
            key = (record["primary_specialty"], record["display_category"])
            grouped.setdefault(key, []).append(record)
        sections: list[WeeklySection] = []
        llm_section_fallbacks = 0
        for (specialty, category), group in sorted(grouped.items()):
            for start_index in range(0, len(group), 20):
                chunk = group[start_index : start_index + 20]
                payload_records = [
                    {
                        "pmid": record["pmid"],
                        "journal": record["journal"],
                        "title": record["title_en"],
                        "abstract": record["abstract_en"],
                    }
                    for record in chunk
                ]
                try:
                    result = await self.llm.summarize_section(
                        {
                            "week_start": week_start.isoformat(),
                            "week_end": week_end.isoformat(),
                            "specialty": specialty,
                            "category": category,
                            "records": payload_records,
                        }
                    )
                except Exception:
                    llm_section_fallbacks += 1
                    result = {
                        "markdown": "本分组文献已通过期刊质量门槛。以下列出本批可追溯的 PubMed 记录；具体研究设计、结局与局限性请以对应文献卡片中的原始摘要为准。",
                        "pmids": [record["pmid"] for record in chunk],
                    }
                allowed_pmids = {record["pmid"] for record in chunk}
                cited_pmids = [pmid for pmid in result["pmids"] if pmid in allowed_pmids]
                sections.append(
                    WeeklySection(
                        specialty=specialty,
                        display_category=category,
                        markdown=result["markdown"],
                        pmids=cited_pmids,
                    )
                )
        summary = WeeklySummary(
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            provider="DeepSeek",
            model=self.settings.deepseek_model,
            prompt_version=WEEKLY_PROMPT_VERSION,
            generated_at=datetime.now(timezone.utc),
            sections=sections,
            evidence_caveat="周报仅归纳通过质量门槛的 PubMed 摘要，不能替代全文评估、临床指南或个体化诊疗决策。",
        )
        audit = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "timezone": "Asia/Shanghai",
            "source": "PubMed EDAT",
            "query_version": "ent-v1-2026-09-17",
            "public_records": len(records),
            "llm_section_fallbacks": llm_section_fallbacks,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.database.save_weekly_report(summary, audit, [record["pmid"] for record in records])
        self.settings.weekly_snapshot_dir.mkdir(parents=True, exist_ok=True)
        output = self.settings.weekly_snapshot_dir / f"weekly-{week_start.isoformat()}.json"
        output.write_text(
            json.dumps({"summary": summary.model_dump(mode="json"), "audit": audit, "articles": records}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return audit
