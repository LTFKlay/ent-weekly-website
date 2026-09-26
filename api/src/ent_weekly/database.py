import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import ArticleRecord, Classification, JournalQuality, PubMedArticle, WeeklySummary


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS articles (
  pmid TEXT PRIMARY KEY,
  title_en TEXT NOT NULL,
  abstract_en TEXT NOT NULL,
  journal TEXT NOT NULL,
  publication_date TEXT,
  authors_json TEXT NOT NULL,
  affiliations_json TEXT NOT NULL,
  issn TEXT,
  eissn TEXT,
  doi TEXT,
  pubmed_url TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS article_sources (
  pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
  date_type TEXT NOT NULL CHECK(date_type IN ('edat','pdat')),
  source_date TEXT NOT NULL,
  topic_matches_json TEXT NOT NULL,
  PRIMARY KEY (pmid, date_type, source_date)
);
CREATE TABLE IF NOT EXISTS journal_quality (
  pmid TEXT PRIMARY KEY REFERENCES articles(pmid) ON DELETE CASCADE,
  journal TEXT NOT NULL,
  jcr_release_year INTEGER NOT NULL,
  jcr_quartile TEXT NOT NULL,
  five_year_jif REAL NOT NULL,
  cas_warning_2025 INTEGER NOT NULL,
  source TEXT NOT NULL,
  matched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS screening (
  pmid TEXT PRIMARY KEY REFERENCES articles(pmid) ON DELETE CASCADE,
  decision TEXT NOT NULL,
  reason TEXT NOT NULL,
  primary_specialty TEXT,
  evidence_track TEXT,
  display_category TEXT,
  screened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS llm_records (
  pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
  prompt_version TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  output_json TEXT NOT NULL,
  status TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  PRIMARY KEY(pmid, prompt_version)
);
CREATE TABLE IF NOT EXISTS daily_runs (
  run_id TEXT PRIMARY KEY,
  target_edat TEXT NOT NULL,
  query_version TEXT NOT NULL,
  status TEXT NOT NULL,
  audit_json TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS weekly_reports (
  week_start TEXT PRIMARY KEY,
  week_end TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  summary_json TEXT NOT NULL,
  audit_json TEXT NOT NULL,
  status TEXT NOT NULL,
  generated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS weekly_report_articles (
  week_start TEXT NOT NULL REFERENCES weekly_reports(week_start) ON DELETE CASCADE,
  pmid TEXT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
  PRIMARY KEY(week_start, pmid)
);
CREATE TABLE IF NOT EXISTS exclusions (
  run_id TEXT NOT NULL,
  pmid TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(run_id, pmid)
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def health(self) -> dict[str, int]:
        with self.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        return {"articles": count}

    def list_public_pmids(self) -> list[str]:
        """Return every published PMID so source metadata can be refreshed safely."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT a.pmid FROM articles a
                   JOIN screening s ON s.pmid = a.pmid
                   WHERE s.decision IN ('include', 'background_trend')
                   ORDER BY a.pmid"""
            ).fetchall()
        return [str(row["pmid"]) for row in rows]

    def update_translation(self, pmid: str, title_zh: str, abstract_zh: str) -> bool:
        """Replace only translated fields; never alter the screening decision."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT rowid, output_json FROM llm_records WHERE pmid=?", (pmid,)
            ).fetchall()
            for row in rows:
                payload = json.loads(row["output_json"])
                payload["title_zh"] = title_zh
                payload["abstract_zh"] = abstract_zh
                connection.execute(
                    "UPDATE llm_records SET output_json=? WHERE rowid=?",
                    (json.dumps(payload, ensure_ascii=False), row["rowid"]),
                )
        return bool(rows)

    def has_llm_record(self, pmid: str) -> bool:
        with self.connect() as connection:
            return connection.execute("SELECT 1 FROM llm_records WHERE pmid=? LIMIT 1", (pmid,)).fetchone() is not None

    def decision_counts_for_edat(self, target_edat: str) -> dict[str, int]:
        source_date = f"{target_edat}..{target_edat}"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT s.decision, COUNT(1) AS count FROM screening s
                   JOIN article_sources src ON src.pmid=s.pmid
                   WHERE src.date_type='edat' AND src.source_date=? GROUP BY s.decision""",
                (source_date,),
            ).fetchall()
        return {row["decision"]: row["count"] for row in rows}

    def list_articles(self, limit: int = 100) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT a.*, q.jcr_quartile, q.five_year_jif, s.decision, s.primary_specialty,
                   s.evidence_track, s.display_category, l.output_json
                   FROM articles a
                   JOIN journal_quality q ON q.pmid = a.pmid
                   JOIN screening s ON s.pmid = a.pmid
                   LEFT JOIN llm_records l ON l.pmid = a.pmid
                   WHERE s.decision IN ('include', 'background_trend')
                   ORDER BY a.publication_date DESC, a.pmid DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            records = [self._serialize(row) for row in rows]
            if not records:
                return records
            pmids = [record["pmid"] for record in records]
            placeholders = ",".join("?" for _ in pmids)
            source_rows = connection.execute(
                f"SELECT pmid, date_type, source_date FROM article_sources WHERE pmid IN ({placeholders})",
                pmids,
            ).fetchall()
        sources_by_pmid: dict[str, dict[str, str]] = {pmid: {} for pmid in pmids}
        for source in source_rows:
            sources_by_pmid[source["pmid"]][source["date_type"]] = source["source_date"]
        for record in records:
            record["source_dates"] = sources_by_pmid[record["pmid"]]
        return records

    def get_article(self, pmid: str) -> dict | None:
        records = [row for row in self.list_articles(500) if row["pmid"] == pmid]
        return records[0] if records else None

    def list_articles_for_edat_week(self, week_start: str, week_end: str) -> list[dict]:
        """Return the public records whose EDAT source date falls within a natural week."""
        start_key = f"{week_start}..{week_start}"
        end_key = f"{week_end}..{week_end}"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT DISTINCT a.*, q.jcr_quartile, q.five_year_jif, s.decision,
                          s.primary_specialty, s.evidence_track, s.display_category, l.output_json
                   FROM articles a
                   JOIN article_sources src ON src.pmid = a.pmid
                   JOIN journal_quality q ON q.pmid = a.pmid
                   JOIN screening s ON s.pmid = a.pmid
                   LEFT JOIN llm_records l ON l.pmid = a.pmid
                   WHERE src.date_type = 'edat' AND src.source_date >= ? AND src.source_date <= ?
                     AND s.decision IN ('include', 'background_trend')
                   ORDER BY a.publication_date DESC, a.pmid DESC""",
                (start_key, end_key),
            ).fetchall()
            records = [self._serialize(row) for row in rows]
            if not records:
                return records
            pmids = [record["pmid"] for record in records]
            placeholders = ",".join("?" for _ in pmids)
            source_rows = connection.execute(
                f"SELECT pmid, date_type, source_date FROM article_sources WHERE pmid IN ({placeholders})",
                pmids,
            ).fetchall()
        sources_by_pmid: dict[str, dict[str, str]] = {pmid: {} for pmid in pmids}
        for source in source_rows:
            sources_by_pmid[source["pmid"]][source["date_type"]] = source["source_date"]
        for record in records:
            record["source_dates"] = sources_by_pmid[record["pmid"]]
        return records

    def list_articles_for_report_week(self, week_start: str, week_end: str) -> list[dict]:
        """Return public records from the EDAT monitoring set plus PDAT backfill."""
        start_key = f"{week_start}..{week_start}"
        end_key = f"{week_end}..{week_end}"
        pdat_key = f"{week_start}..{week_end}"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT DISTINCT a.*, q.jcr_quartile, q.five_year_jif, s.decision,
                          s.primary_specialty, s.evidence_track, s.display_category, l.output_json
                   FROM articles a
                   JOIN article_sources src ON src.pmid = a.pmid
                   JOIN journal_quality q ON q.pmid = a.pmid
                   JOIN screening s ON s.pmid = a.pmid
                   LEFT JOIN llm_records l ON l.pmid = a.pmid
                   WHERE ((src.date_type = 'edat' AND src.source_date >= ? AND src.source_date <= ?)
                      OR (src.date_type = 'pdat' AND src.source_date = ?))
                     AND s.decision IN ('include', 'background_trend')
                   ORDER BY a.publication_date DESC, a.pmid DESC""",
                (start_key, end_key, pdat_key),
            ).fetchall()
            records = [self._serialize(row) for row in rows]
            if not records:
                return records
            pmids = [record["pmid"] for record in records]
            placeholders = ",".join("?" for _ in pmids)
            source_rows = connection.execute(
                f"SELECT pmid, date_type, source_date FROM article_sources WHERE pmid IN ({placeholders})",
                pmids,
            ).fetchall()
        sources_by_pmid: dict[str, dict[str, str]] = {pmid: {} for pmid in pmids}
        for source in source_rows:
            sources_by_pmid[source["pmid"]][source["date_type"]] = source["source_date"]
        for record in records:
            record["source_dates"] = sources_by_pmid[record["pmid"]]
        return records

    def save_weekly_report(self, summary: WeeklySummary, audit: dict, pmids: list[str]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO weekly_reports(week_start, week_end, revision, summary_json, audit_json, status, generated_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(week_start) DO UPDATE SET week_end=excluded.week_end,
                     revision=weekly_reports.revision + 1, summary_json=excluded.summary_json,
                     audit_json=excluded.audit_json, status=excluded.status, generated_at=excluded.generated_at""",
                (
                    summary.week_start,
                    summary.week_end,
                    1,
                    summary.model_dump_json(),
                    json.dumps(audit, ensure_ascii=False),
                    "success",
                    summary.generated_at.isoformat(),
                ),
            )
            connection.execute("DELETE FROM weekly_report_articles WHERE week_start=?", (summary.week_start,))
            connection.executemany(
                "INSERT OR IGNORE INTO weekly_report_articles(week_start, pmid) VALUES(?, ?)",
                [(summary.week_start, pmid) for pmid in pmids],
            )

    def upsert_candidate(self, article: PubMedArticle) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO articles(pmid,title_en,abstract_en,journal,publication_date,authors_json,affiliations_json,issn,eissn,doi,pubmed_url)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(pmid) DO UPDATE SET title_en=excluded.title_en,abstract_en=excluded.abstract_en,
                   journal=excluded.journal,publication_date=excluded.publication_date,authors_json=excluded.authors_json,
                   affiliations_json=excluded.affiliations_json,issn=excluded.issn,eissn=excluded.eissn,doi=excluded.doi,
                   pubmed_url=excluded.pubmed_url,updated_at=CURRENT_TIMESTAMP""",
                (article.pmid, article.title_en, article.abstract_en, article.journal, article.publication_date,
                 json.dumps(article.authors, ensure_ascii=False), json.dumps(article.affiliations, ensure_ascii=False),
                 article.issn, article.eissn, article.doi, article.pubmed_url),
            )
            for date_type, source_date in article.source_dates.items():
                connection.execute(
                    """INSERT INTO article_sources(pmid,date_type,source_date,topic_matches_json) VALUES(?,?,?,?)
                    ON CONFLICT(pmid,date_type,source_date) DO UPDATE SET topic_matches_json=excluded.topic_matches_json""",
                    (article.pmid, date_type, source_date, json.dumps(article.topic_matches)),
                )

    def record_exclusion(self, run_id: str, article: PubMedArticle, reason: str) -> None:
        self.upsert_candidate(article)
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO exclusions(run_id,pmid,reason) VALUES(?,?,?)", (run_id, article.pmid, reason))
            connection.execute("INSERT OR REPLACE INTO screening(pmid,decision,reason) VALUES(?,?,?)", (article.pmid, "exclude", reason))

    def record_included(self, record: ArticleRecord) -> None:
        if not record.classification:
            raise ValueError("Included record requires an LLM classification.")
        self.upsert_candidate(record)
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO journal_quality(pmid,journal,jcr_release_year,jcr_quartile,five_year_jif,cas_warning_2025,source)
                   VALUES(?,?,?,?,?,?,?)""",
                (record.pmid, record.quality.journal, record.quality.jcr_release_year, record.quality.jcr_quartile,
                 record.quality.five_year_jif, int(record.quality.cas_warning_2025), record.quality.source),
            )
            classification = record.classification
            connection.execute(
                """INSERT OR REPLACE INTO screening(pmid,decision,reason,primary_specialty,evidence_track,display_category)
                   VALUES(?,?,?,?,?,?)""",
                (record.pmid, record.decision, record.screening_reason, classification.primary_specialty,
                 classification.evidence_track, classification.display_category),
            )
            connection.execute(
                """INSERT OR REPLACE INTO llm_records(pmid,prompt_version,provider,model,output_json,status,generated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (record.pmid, classification.prompt_version, classification.provider, classification.model,
                 classification.model_dump_json(), "success", classification.generated_at.isoformat()),
            )

    def record_processed(
        self,
        run_id: str,
        article: PubMedArticle,
        classification: Classification,
        decision: str,
        reason: str,
        quality: JournalQuality | None,
    ) -> None:
        """Persist a completed LLM pass, including records later excluded by quality rules."""
        self.upsert_candidate(article)
        with self.connect() as connection:
            if quality:
                connection.execute(
                    """INSERT OR REPLACE INTO journal_quality(pmid,journal,jcr_release_year,jcr_quartile,five_year_jif,cas_warning_2025,source)
                       VALUES(?,?,?,?,?,?,?)""",
                    (article.pmid, quality.journal, quality.jcr_release_year, quality.jcr_quartile,
                     quality.five_year_jif, int(quality.cas_warning_2025), quality.source),
                )
            connection.execute(
                """INSERT OR REPLACE INTO screening(pmid,decision,reason,primary_specialty,evidence_track,display_category)
                   VALUES(?,?,?,?,?,?)""",
                (article.pmid, decision, reason, classification.primary_specialty,
                 classification.evidence_track, classification.display_category),
            )
            connection.execute(
                """INSERT OR REPLACE INTO llm_records(pmid,prompt_version,provider,model,output_json,status,generated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (article.pmid, classification.prompt_version, classification.provider, classification.model,
                 classification.model_dump_json(), "success", classification.generated_at.isoformat()),
            )
            if decision == "exclude":
                connection.execute(
                    "INSERT OR REPLACE INTO exclusions(run_id,pmid,reason) VALUES(?,?,?)",
                    (run_id, article.pmid, reason),
                )

    def start_run(self, run_id: str, target_edat: str, query_version: str, audit: dict) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO daily_runs(run_id,target_edat,query_version,status,audit_json,started_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)", (run_id, target_edat, query_version, "running", json.dumps(audit, ensure_ascii=False)))

    def finish_run(self, run_id: str, status: str, audit: dict) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE daily_runs SET status=?,audit_json=?,finished_at=CURRENT_TIMESTAMP WHERE run_id=?", (status, json.dumps(audit, ensure_ascii=False), run_id))

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict:
        result = dict(row)
        result["authors"] = json.loads(result.pop("authors_json"))
        result["affiliations"] = json.loads(result.pop("affiliations_json"))
        if result.get("output_json"):
            result["classification"] = json.loads(result.pop("output_json"))
        else:
            result.pop("output_json", None)
        return result
