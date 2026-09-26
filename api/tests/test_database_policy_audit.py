import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ent_weekly.database import Database
from ent_weekly.models import Classification, JournalQuality, PubMedArticle
from ent_weekly.rescreen import run as run_rescreen


class ScreeningPolicyAuditTests(unittest.TestCase):
    def _article_and_classification(self):
        article = PubMedArticle(
            pmid="99900001",
            title_en="Direct otology study",
            abstract_en="Otology content.",
            journal="Test Journal",
            pubmed_url="https://pubmed.ncbi.nlm.nih.gov/99900001/",
        )
        classification = Classification(
            screening_decision="include",
            primary_specialty="otology",
            evidence_track="clinical",
            display_category="clinical",
            classification_reason="Direct otology relevance.",
            title_zh="耳科研究",
            abstract_zh="耳科内容。",
            model="test-model",
            prompt_version="classifier-v1",
            generated_at=datetime.now(timezone.utc),
        )
        return article, classification

    def test_new_policy_retains_prior_llm_audit_record(self):
        database_path = ROOT / ".test-policy-audit.db"
        database_path.unlink(missing_ok=True)
        try:
            database = Database(database_path)
            database.initialize()
            article, classification = self._article_and_classification()

            database.record_processed("run-old", article, classification, "include", "old", None, "query-v1::classifier-v1")
            database.record_processed("run-new", article, classification, "include", "new", None, "query-v2::classifier-v1")

            with database.connect() as connection:
                rows = connection.execute(
                    "SELECT screening_policy_version FROM llm_records WHERE pmid=? ORDER BY screening_policy_version",
                    (article.pmid,),
                ).fetchall()
                current = connection.execute(
                    "SELECT screening_policy_version FROM screening WHERE pmid=?",
                    (article.pmid,),
                ).fetchone()

            self.assertEqual([row["screening_policy_version"] for row in rows], [
                "query-v1::classifier-v1", "query-v2::classifier-v1",
            ])
            self.assertEqual(current["screening_policy_version"], "query-v2::classifier-v1")
        finally:
            database_path.unlink(missing_ok=True)

    def test_rescreen_preview_does_not_write_database(self):
        database_path = ROOT / ".test-rescreen-preview.db"
        database_path.unlink(missing_ok=True)
        try:
            database = Database(database_path)
            database.initialize()
            article, classification = self._article_and_classification()
            quality = JournalQuality(
                journal="Test Journal", jcr_release_year=2025, jcr_quartile="Q1",
                five_year_jif=5.0, source="test",
            )
            database.record_processed("seed", article, classification, "include", "seed", quality, "legacy-policy")
            before = database.get_article(article.pmid)

            with patch.dict(os.environ, {"DB_PATH": str(database_path)}, clear=False):
                result = asyncio.run(run_rescreen(
                    apply=False, reclassify=False, refresh_weekly=False, limit=None, max_concurrent=None,
                ))

            after = database.get_article(article.pmid)
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(before["screening_policy_version"], after["screening_policy_version"])
            self.assertEqual(before["decision"], after["decision"])
        finally:
            database_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
