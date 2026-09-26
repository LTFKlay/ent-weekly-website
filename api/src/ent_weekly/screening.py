import re

from .models import PubMedArticle


TCM_PATTERN = re.compile(r"traditional chinese medicine|chinese herbal|acupuncture|electroacupuncture|moxibustion|tuina|cupping|chinese patent medicine", re.I)
EDITORIAL_PATTERN = re.compile(r"\b(erratum|editorial|correction)\b", re.I)
NEGATED_ENT_CONTEXT_PATTERN = re.compile(
    r"\b(?:without|no|absence of|free from|free of|excluding)\b[^.\n]{0,140}"
    r"\b(?:vestibular|otolog\w*|ear|hearing|laryng\w*|nasal|sinus|rhin\w*|nasopharyn\w*)\b",
    re.I,
)
MUSCULOSKELETAL_PATTERN = re.compile(
    r"\b(?:ankle|knee|hip|lower[ -]limb|lower extremit\w*|gait|locomot\w*|orthop(?:a|e)dic)\b",
    re.I,
)
DIRECT_ENT_TITLE_PATTERN = re.compile(
    r"\b(?:rhinitis|rhinosinusitis|sinusitis|nasal polyp\w*|olfactory|anosmia|hyposmia|"
    r"otitis|hearing loss|deafness|cochlear|cholesteatoma|otosclerosis|tinnitus|vertigo|"
    r"vestibular|m[ée]ni[èe]re|laryng\w*|dysphonia|vocal fold\w*|vocal cord\w*|"
    r"dysphagia|swallowing|sleep apnea|tonsil\w*|adenoid\w*|nasopharyn\w*)\b",
    re.I,
)


def initial_exclusion(article: PubMedArticle) -> str | None:
    text = f"{article.title_en}\n{article.abstract_en}"
    if not article.abstract_en.strip():
        return "Exclude: abstract unavailable for requested card format."
    if TCM_PATTERN.search(text):
        return "Exclude: traditional Chinese medicine-related intervention or framework."
    if EDITORIAL_PATTERN.search(article.title_en):
        return "Exclude: editorial, erratum, or correction record."
    if (
        NEGATED_ENT_CONTEXT_PATTERN.search(text)
        and MUSCULOSKELETAL_PATTERN.search(text)
        and not DIRECT_ENT_TITLE_PATTERN.search(article.title_en)
    ):
        return "Exclude: musculoskeletal study only mentions an ENT term in a negated eligibility or comorbidity context."
    return None
