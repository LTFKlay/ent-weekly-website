"""集中定义可审计的文献筛选策略版本。"""

from __future__ import annotations

import json
from pathlib import Path

from .llm import CLASSIFICATION_PROMPT_VERSION


_QUERY_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "topic-queries.json"


def query_rule_version() -> str:
    """返回随镜像发布的检索规则版本。"""
    config = json.loads(_QUERY_CONFIG_PATH.read_text(encoding="utf-8"))
    return str(config["version"])


def screening_policy_version() -> str:
    """检索与分类任一变更都会生成新的筛选策略版本。"""
    return f"{query_rule_version()}::{CLASSIFICATION_PROMPT_VERSION}"


SCREENING_POLICY_VERSION = screening_policy_version()
