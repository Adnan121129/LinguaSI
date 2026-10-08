"""Centralised prompt templates.

Each prompt lives in this package as two Markdown files:

    <area>/<name>.system.md   - the agent's role, rules and output contract
    <area>/<name>.user.md     - the per-request payload (learner context, task data)

Syntax:
    {{variable}}         substituted with the provided value (missing variables raise KeyError)
    {{> shared/safety}}  includes shared/safety.md (partials may include other partials)
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent
_PARTIAL = re.compile(r"\{\{>\s*([\w/\-]+)\s*\}\}")
_VARIABLE = re.compile(r"\{\{\s*([a-zA-Z_][\w]*)\s*\}\}")


@lru_cache(maxsize=128)
def _load(relative: str) -> str:
    path = (PROMPT_DIR / relative).resolve()
    if PROMPT_DIR not in path.parents:
        raise ValueError(f"Prompt path escapes prompt directory: {relative}")
    return path.read_text(encoding="utf-8")


def _expand_partials(text: str, depth: int = 0) -> str:
    if depth > 5:
        raise ValueError("Prompt partials nested too deeply")

    def replace(match: re.Match) -> str:
        return _expand_partials(_load(f"{match.group(1)}.md"), depth + 1)

    return _PARTIAL.sub(replace, text)


def _format_value(value: object) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        if not value:
            return "(none)"
        if all(isinstance(item, str) for item in value):
            return "\n".join(f"- {item}" for item in value)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def render_template(relative: str, variables: dict) -> str:
    text = _expand_partials(_load(relative))

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in variables:
            raise KeyError(f"Prompt '{relative}' requires variable '{name}'")
        return _format_value(variables[name])

    return _VARIABLE.sub(replace, text).strip()


def render(prompt: str, variables: dict) -> tuple[str, str]:
    """Render the (system, user) pair for a prompt name such as 'writing/evaluate'."""
    return render_template(f"{prompt}.system.md", variables), render_template(f"{prompt}.user.md", variables)


def prompt_exists(prompt: str) -> bool:
    return (PROMPT_DIR / f"{prompt}.system.md").exists() and (PROMPT_DIR / f"{prompt}.user.md").exists()
