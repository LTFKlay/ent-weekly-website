import asyncio
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import httpx

from .models import PubMedArticle
from .settings import Settings


class PubMedClient:
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, settings: Settings, query_path: Path):
        self.settings = settings
        self.query_config = json.loads(query_path.read_text(encoding="utf-8"))
        self.delay = 0.1 if settings.ncbi_api_key else 1 / 3

    def _params(self) -> dict[str, str]:
        params = {"tool": self.settings.pubmed_tool, "email": self.settings.pubmed_email}
        if self.settings.ncbi_api_key:
            params["api_key"] = self.settings.ncbi_api_key
        return params

    async def search_topic(self, topic: dict, date_type: str, start: str, end: str) -> list[str]:
        term = f"({topic['query']}) NOT ({self.query_config['global_exclusion']})"
        params = {**self._params(), "db": "pubmed", "term": term, "datetype": date_type, "mindate": start, "maxdate": end, "retmode": "json", "retmax": "500"}
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.get(f"{self.base_url}/esearch.fcgi", params=params)
            response.raise_for_status()
        await asyncio.sleep(self.delay)
        return response.json()["esearchresult"].get("idlist", [])

    async def fetch_articles(self, pmids: list[str]) -> list[PubMedArticle]:
        if not pmids:
            return []
        parsed: list[PubMedArticle] = []
        for index in range(0, len(pmids), 200):
            batch = pmids[index : index + 200]
            params = {**self._params(), "db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(f"{self.base_url}/efetch.fcgi", params=params)
                response.raise_for_status()
            parsed.extend(self._parse(response.text))
            if index + 200 < len(pmids):
                await asyncio.sleep(self.delay)
        return parsed

    async def retrieve(self, date_type: str, start: str, end: str) -> tuple[list[PubMedArticle], dict]:
        matches: dict[str, list[str]] = defaultdict(list)
        audit = {"query_version": self.query_config["version"], "date_type": date_type, "start": start, "end": end, "topic_counts": {}}
        for topic in self.query_config["topics"]:
            pmids = await self.search_topic(topic, date_type, start, end)
            audit["topic_counts"][topic["key"]] = len(pmids)
            for pmid in pmids:
                matches[pmid].append(topic["key"])
        articles = await self.fetch_articles(list(matches))
        for article in articles:
            article.topic_matches = matches[article.pmid]
            article.source_dates[date_type] = f"{start}..{end}"
        audit["unique_pmids"] = len(matches)
        return articles, audit

    @staticmethod
    def _text(element: ET.Element | None) -> str:
        return "".join(element.itertext()).strip() if element is not None else ""

    @classmethod
    def _abstract_section_text(cls, element: ET.Element) -> str:
        """Preserve PubMed's optional structured-abstract label verbatim."""
        content = cls._text(element)
        if not content:
            return ""
        label = element.attrib.get("Label", "").strip().rstrip(":")
        return f"{label}: {content}" if label else content

    def _parse(self, xml: str) -> list[PubMedArticle]:
        root = ET.fromstring(xml)
        parsed: list[PubMedArticle] = []
        for node in root.findall(".//PubmedArticle"):
            citation = node.find("MedlineCitation")
            article = citation.find("Article") if citation is not None else None
            pmid = self._text(citation.find("PMID") if citation is not None else None)
            title = self._text(article.find("ArticleTitle") if article is not None else None)
            abstract_parts = [
                self._abstract_section_text(item)
                for item in (article.findall("Abstract/AbstractText") if article is not None else [])
            ]
            abstract = "\n".join(part for part in abstract_parts if part)
            journal = self._text(article.find("Journal/Title") if article is not None else None)
            publication_date = self._text(article.find("Journal/JournalIssue/PubDate/Year") if article is not None else None)
            identifiers = {item.attrib.get("IdType", "").lower(): self._text(item) for item in node.findall("PubmedData/ArticleIdList/ArticleId")}
            authors, affiliations = [], []
            for author in article.findall("AuthorList/Author") if article is not None else []:
                name = " ".join(filter(None, [self._text(author.find("ForeName")), self._text(author.find("LastName"))]))
                if name:
                    authors.append(name)
                affiliations.extend(self._text(item) for item in author.findall("AffiliationInfo/Affiliation") if self._text(item))
            issn = self._text(article.find("Journal/ISSN") if article is not None else None)
            if pmid and title and journal:
                parsed.append(PubMedArticle(pmid=pmid, title_en=title, abstract_en=abstract, journal=journal, publication_date=publication_date or None, authors=authors, affiliations=list(dict.fromkeys(affiliations)), issn=issn or None, doi=identifiers.get("doi"), pubmed_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"))
        return parsed
