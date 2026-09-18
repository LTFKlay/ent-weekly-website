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
                return json.loads(content)
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
        if value.get("evidence_track") in {"ai_ml", "review", "guideline", "guideline_consensus"}:
            value["evidence_track"] = "clinical"
        if value.get("evidence_track") in {"basic", "basic_translational_research"}:
            value["evidence_track"] = "basic_translational"
        category_aliases = {"basic_translational": "basic", "review": "review_meta", "guideline": "guideline_consensus"}
        value["display_category"] = category_aliases.get(value.get("display_category"), value.get("display_category"))
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
