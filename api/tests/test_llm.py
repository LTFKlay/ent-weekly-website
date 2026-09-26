import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ent_weekly.llm import DeepSeekClient
from ent_weekly.models import PubMedArticle
from ent_weekly.screening import initial_exclusion


class CapturingDeepSeekClient(DeepSeekClient):
    def __init__(self):
        super().__init__(SimpleNamespace(deepseek_api_key="key", deepseek_model="test-model"))
        self.payload = None

    async def _json_completion(self, payload):
        self.payload = payload
        return {
            "screening_decision": "include",
            "primary_specialty": "otology",
            "evidence_track": "clinical",
            "display_category": "clinical",
            "classification_reason": "Relevant study.",
            "title_zh": "标题",
            "abstract_zh": "背景：内容",
        }


class StructuredAbstractTranslationPromptTests(unittest.TestCase):
    def test_routine_classification_translation_requires_labels(self):
        article = PubMedArticle(
            pmid="12345678",
            title_en="Test title",
            abstract_en="BACKGROUND: Context.\nMETHODS: Study design.",
            journal="Test Journal",
            pubmed_url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
        )
        client = CapturingDeepSeekClient()

        asyncio.run(client.classify_and_translate(article))

        prompt = client.payload["messages"][0]["content"]
        self.assertIn("AbstractText@Label", prompt)
        self.assertIn("BACKGROUND: as 背景：", prompt)
        self.assertIn("each labeled section on its own line", prompt)

    def test_classification_prompt_requires_direct_ent_relevance(self):
        article = PubMedArticle(
            pmid="12345679",
            title_en="Test title",
            abstract_en="BACKGROUND: Context.",
            journal="Test Journal",
            pubmed_url="https://pubmed.ncbi.nlm.nih.gov/12345679/",
        )
        client = CapturingDeepSeekClient()

        asyncio.run(client.classify_and_translate(article))

        prompt = client.payload["messages"][0]["content"]
        self.assertIn("directly within rhinology, otology, laryngology, or nasopharyngeal carcinoma", prompt)
        self.assertIn("without vestibular disorders", prompt)

    def test_negated_vestibular_context_in_ankle_study_is_excluded(self):
        article = PubMedArticle(
            pmid="42789776",
            title_en="Balance Wood, a Bilateral Ankle-Controlled Serious Game for Healthy Adults.",
            abstract_en="Healthy adults without lower-limb injury or balance-affecting neurological or vestibular disorders completed the study.",
            journal="JMIR Serious Games",
            pubmed_url="https://pubmed.ncbi.nlm.nih.gov/42789776/",
        )

        self.assertEqual(
            initial_exclusion(article),
            "Exclude: musculoskeletal study only mentions an ENT term in a negated eligibility or comorbidity context.",
        )


if __name__ == "__main__":
    unittest.main()
