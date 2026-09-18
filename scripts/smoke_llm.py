"""Validate one real PubMed-to-DeepSeek structured response without persistence."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path

from ent_weekly.llm import DeepSeekClient
from ent_weekly.pubmed import PubMedClient
from ent_weekly.settings import Settings


async def smoke(target: date) -> dict:
    settings = Settings()
    client = PubMedClient(settings, Path("api/config/topic-queries.json"))
    print("retrieving PubMed candidate", flush=True)
    articles, _ = await client.retrieve("edat", target.isoformat(), target.isoformat())
    if not articles:
        raise RuntimeError("No PubMed candidates for smoke test.")
    print("requesting DeepSeek classification", flush=True)
    result = await DeepSeekClient(settings).classify_and_translate(articles[0])
    return {"pmid": articles[0].pmid, "specialty": result.primary_specialty, "category": result.display_category}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edat", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    print(asyncio.run(smoke(args.edat)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
