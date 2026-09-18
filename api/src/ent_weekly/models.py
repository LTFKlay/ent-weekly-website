from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


Specialty = Literal["rhinology", "otology", "laryngology", "nasopharyngeal_carcinoma"]
EvidenceTrack = Literal["clinical", "basic_translational"]
DisplayCategory = Literal["clinical", "ai_ml", "basic", "review_meta", "guideline_consensus"]
Decision = Literal["include", "background_trend", "exclude"]


class JournalQuality(BaseModel):
    journal: str
    issn: str | None = None
    eissn: str | None = None
    jcr_release_year: int
    jcr_quartile: Literal["Q1", "Q2", "Q3", "Q4"]
    five_year_jif: float
    cas_warning_2025: bool = False
    source: str


class PubMedArticle(BaseModel):
    pmid: str
    title_en: str
    abstract_en: str
    journal: str
    publication_date: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    issn: str | None = None
    eissn: str | None = None
    doi: str | None = None
    pubmed_url: str
    topic_matches: list[str] = Field(default_factory=list)
    source_dates: dict[str, str] = Field(default_factory=dict)


class Classification(BaseModel):
    screening_decision: Decision
    primary_specialty: Specialty
    evidence_track: EvidenceTrack
    display_category: DisplayCategory
    classification_reason: str
    title_zh: str
    abstract_zh: str
    provider: str = "DeepSeek"
    model: str
    prompt_version: str
    generated_at: datetime


class ArticleRecord(PubMedArticle):
    quality: JournalQuality
    decision: Decision
    screening_reason: str
    classification: Classification | None = None


class WeeklySection(BaseModel):
    specialty: Specialty
    display_category: DisplayCategory
    markdown: str
    pmids: list[str]


class WeeklySummary(BaseModel):
    week_start: str
    week_end: str
    provider: str = "DeepSeek"
    model: str
    prompt_version: str
    generated_at: datetime
    sections: list[WeeklySection]
    evidence_caveat: str
