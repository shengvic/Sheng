"""Versioned prompt files: prompts/<task>/<version>.md (docs/10 conventions)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


@cache
def load_prompt(task: str, version: str = "v1") -> str:
    return (_DIR / task / f"{version}.md").read_text(encoding="utf-8").strip()
