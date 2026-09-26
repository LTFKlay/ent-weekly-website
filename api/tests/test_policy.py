import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ent_weekly.llm import CLASSIFICATION_PROMPT_VERSION
from ent_weekly.policy import SCREENING_POLICY_VERSION, query_rule_version


class ScreeningPolicyVersionTests(unittest.TestCase):
    def test_policy_version_combines_query_and_classifier_versions(self):
        config = json.loads((ROOT / "config" / "topic-queries.json").read_text(encoding="utf-8"))

        self.assertEqual(query_rule_version(), config["version"])
        self.assertEqual(SCREENING_POLICY_VERSION, f"{config['version']}::{CLASSIFICATION_PROMPT_VERSION}")


if __name__ == "__main__":
    unittest.main()
