"""Retrieve an EDAT candidate count without invoking the LLM or writing data."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path

from ent_weekly.pubmed import PubMedClient
from ent_weekly.settings import Settings


async def inspect(target: date) -> dict:
    client = PubMedClient(Settings(), Path("api/config/topic-queries.json"))
    articles, audit = await client.retrieve("edat", target.isoformat(), target.isoformat())
    return {"target_edat": target.isoformat(), "candidates": len(articles), "topic_counts": audit["topic_counts"], "query_version": audit["query_version"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edat", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    print(asyncio.run(inspect(args.edat)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
