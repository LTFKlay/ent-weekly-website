import json
import asyncio
from datetime import datetime, timezone

import httpx

from .models import Classification, PubMedArticle, WeeklySummary
from .settings import Settings


CLASSIFICATION_PROMPT_VERSION = "ent-classify-translate-v1"
WEEKLY_PROMPT_VERSION = "ent-weekly-summary-v1"


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.deepseek_api_key}", "Content-Type": "application/json"}

    async def _json_completion(self, payload: dict) -> dict:
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions", headers=self._headers(), json=payload)
                response.raise_for_status()
            content = response.json()["choices"][0]["message"].get("content") or ""
            if content.strip():
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    if attempt == 2:
                        raise RuntimeError("DeepSeek returned malformed structured JSON after three attempts.")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("DeepSeek returned an empty structured response after three attempts.")

    async def classify_and_translate(self, article: PubMedArticle) -> Classification:
        if not self.settings.deepseek_api_key or not self.settings.deepseek_model:
            raise RuntimeError("DeepSeek credentials/model are not configured.")
        prompt = (
            "You are a medical literature classifier and translator. Return JSON only. "
            "Read the entire supplied PubMed abstract. Do not infer missing methods, outcomes, effects, safety, or causality. "
            "Assign screening_decision as include, background_trend, or exclude. "
            "Assign one primary_specialty from rhinology, otology, laryngology, nasopharyngeal_carcinoma; "
            "one evidence_track from clinical, basic_translational; one display_category from clinical, ai_ml, basic, review_meta, guideline_consensus. "
            "Translate title and entire abstract into precise Chinese, preserving section order. "
            "Your JSON must contain exactly these required keys: screening_decision, primary_specialty, evidence_track, display_category, "
            "classification_reason, title_zh, abstract_zh. Do not use an alternative key named reason. "
            f"PMID: {article.pmid}\nTITLE: {article.title_en}\nABSTRACT: {article.abstract_en}"
        )
        payload = {"model": self.settings.deepseek_model, "temperature": 0.1, "thinking": {"type": "disabled"}, "max_tokens": 4000, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]}
        value = await self._json_completion(payload)
        if "classification_reason" not in value and "reason" in value:
            value["classification_reason"] = value["reason"]
        specialty_aliases = {
            "nose": "rhinology",
            "nasal": "rhinology",
            "ear": "otology",
            "hearing": "otology",
            "otolaryngology": "laryngology",
            "laryngology": "laryngology",
            "throat": "laryngology",
            "npc": "nasopharyngeal_carcinoma",
            "nasopharyngeal cancer": "nasopharyngeal_carcinoma",
        }
        specialty = str(value.get("primary_specialty", "")).strip().lower()
        if specialty in specialty_aliases:
            value["primary_specialty"] = specialty_aliases[specialty]
        elif specialty not in {"rhinology", "otology", "laryngology", "nasopharyngeal_carcinoma"}:
            matched_topics = [topic for topic in article.topic_matches if topic in {"rhinology", "otology", "laryngology", "nasopharyngeal_carcinoma"}]
            value["primary_specialty"] = matched_topics[0] if len(matched_topics) == 1 else "laryngology"
        decision_aliases = {
            "background/trend": "background_trend",
            "background": "background_trend",
            "include": "include",
            "exclude": "exclude",
        }
        value["screening_decision"] = decision_aliases.get(str(value.get("screening_decision", "")).strip().lower(), "exclude")
        evidence_track = str(value.get("evidence_track", "")).strip().lower()
        if evidence_track in {"ai_ml", "review", "guideline", "guideline_consensus", "clinical research", "clinical"}:
            value["evidence_track"] = "clinical"
        if evidence_track in {"basic", "basic_translational_research", "basic/translational", "translational"}:
            value["evidence_track"] = "basic_translational"
        if value.get("evidence_track") not in {"clinical", "basic_translational"}:
            value["evidence_track"] = "clinical"
        category_aliases = {
            "basic_translational": "basic",
            "basic/translational": "basic",
            "review": "review_meta",
            "meta-analysis": "review_meta",
            "meta_analysis": "review_meta",
            "guideline": "guideline_consensus",
            "consensus": "guideline_consensus",
            "clinical research": "clinical",
            "clinical": "clinical",
        }
        category = str(value.get("display_category", "")).strip().lower()
        value["display_category"] = category_aliases.get(category, category)
        if value["display_category"] not in {"clinical", "ai_ml", "basic", "review_meta", "guideline_consensus"}:
            value["display_category"] = "basic" if value["evidence_track"] == "basic_translational" else "clinical"
        value.setdefault("classification_reason", "Exclude: structured classifier did not provide a reason.")
        value.update({"provider": "DeepSeek", "model": self.settings.deepseek_model, "prompt_version": CLASSIFICATION_PROMPT_VERSION, "generated_at": datetime.now(timezone.utc)})
        return Classification.model_validate(value)

    async def summarize_week(self, payload: dict) -> WeeklySummary:
        if not self.settings.deepseek_api_key or not self.settings.deepseek_model:
            raise RuntimeError("DeepSeek credentials/model are not configured.")
        prompt = (
            "Return JSON only. Create a Chinese weekly ENT literature review exclusively from the included PubMed records supplied. "
            "Organize sections by primary specialty and display category. Every paragraph must cite only supplied PMIDs, "
            "and every section must return markdown plus a pmids array. State '摘要未报告' for missing details. "
            "Never make clinical recommendations or claim causality beyond the abstract.\n" + json.dumps(payload, ensure_ascii=False)
        )
        request = {"model": self.settings.deepseek_model, "temperature": 0.15, "thinking": {"type": "disabled"}, "max_tokens": 8000, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]}
        result = await self._json_completion(request)
        result.update({"provider": "DeepSeek", "model": self.settings.deepseek_model, "prompt_version": WEEKLY_PROMPT_VERSION, "generated_at": datetime.now(timezone.utc)})
        return WeeklySummary.model_validate(result)

    async def summarize_section(self, payload: dict) -> dict:
        """Summarize a bounded specialty/category slice to keep long weeks within context limits."""
        if not self.settings.deepseek_api_key or not self.settings.deepseek_model:
            raise RuntimeError("DeepSeek credentials/model are not configured.")
        prompt = (
            "Return JSON only with exactly two keys: markdown and pmids. "
            "Write a polished Chinese weekly-report paragraph based exclusively on the supplied PubMed records. "
            "Do not make recommendations or infer unreported data. State '摘要未报告' where needed. "
            "Use a continuous editorial paragraph rather than bullets. Keep markdown to 180–260 Chinese words. "
            "When citing a record in the paragraph, use exactly the token [[PMID:12345678]] immediately after the relevant statement. "
            "The pmids array must only contain supplied PMIDs that are discussed in markdown. "
            "Use each supplied record at most once and retain the original PMID identifiers.\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        request = {
            "model": self.settings.deepseek_model,
            "temperature": 0.15,
            "thinking": {"type": "disabled"},
            "max_tokens": 1400,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        }
        result = await self._json_completion(request)
        if not isinstance(result.get("markdown"), str):
            raise RuntimeError("DeepSeek weekly section did not return markdown.")
        result["pmids"] = [str(pmid) for pmid in result.get("pmids", [])]
        return result
