import json
from pathlib import Path

from .models import JournalQuality, PubMedArticle


class QualityGate:
    """Strict fail-closed JCR/CAS gate. No verified match means exclusion."""

    def __init__(self, path: Path):
        self.path = path
        self._records = self._load()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def resolve(self, article: PubMedArticle) -> tuple[JournalQuality | None, str | None]:
        keys = {value.lower().strip() for value in (article.issn, article.eissn, article.journal) if value}
        matches = [record for record in self._records if keys & {str(record.get(field, "")).lower().strip() for field in ("issn", "eissn", "journal")}]
        if len(matches) != 1:
            return None, "Exclude: journal-quality metadata unavailable or unverified."
        quality = JournalQuality.model_validate(matches[0])
        if quality.jcr_quartile == "Q4":
            return quality, "Exclude: JCR Q4 journal."
        if quality.cas_warning_2025:
            return quality, "Exclude: listed on the 2025 CAS warning-journal list."
        return quality, None

