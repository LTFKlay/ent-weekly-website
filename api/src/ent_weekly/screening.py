import re

from .models import PubMedArticle


TCM_PATTERN = re.compile(r"traditional chinese medicine|chinese herbal|acupuncture|electroacupuncture|moxibustion|tuina|cupping|chinese patent medicine", re.I)
EDITORIAL_PATTERN = re.compile(r"\b(erratum|editorial|correction)\b", re.I)


def initial_exclusion(article: PubMedArticle) -> str | None:
    text = f"{article.title_en}\n{article.abstract_en}"
    if not article.abstract_en.strip():
        return "Exclude: abstract unavailable for requested card format."
    if TCM_PATTERN.search(text):
        return "Exclude: traditional Chinese medicine-related intervention or framework."
    if EDITORIAL_PATTERN.search(article.title_en):
        return "Exclude: editorial, erratum, or correction record."
    return None

