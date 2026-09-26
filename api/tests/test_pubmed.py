import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ent_weekly.pubmed import PubMedClient


class PubMedAbstractParsingTests(unittest.TestCase):
    def test_structured_abstract_labels_are_preserved_in_order(self):
        xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345678</PMID><Article>
          <ArticleTitle>Structured abstract</ArticleTitle><Journal><Title>Test Journal</Title></Journal>
          <Abstract><AbstractText Label="Background">First sentence.</AbstractText>
          <AbstractText Label="Methods">Second sentence.</AbstractText>
          <AbstractText>Unlabelled sentence.</AbstractText></Abstract>
        </Article></MedlineCitation><PubmedData><ArticleIdList /></PubmedData></PubmedArticle></PubmedArticleSet>"""

        article = PubMedClient._parse(PubMedClient, xml)[0]

        self.assertEqual(
            article.abstract_en,
            "Background: First sentence.\nMethods: Second sentence.\nUnlabelled sentence.",
        )


if __name__ == "__main__":
    unittest.main()
