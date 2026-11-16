"""Skill library loader and tool wrapper for Markdown coaching skills (`skills/*.md`)."""

from __future__ import annotations

import difflib
import re
import tomllib
from pathlib import Path
from typing import Callable

SKILL_NAMES: tuple[str, ...] = (
    "micro_study_break",
    "sleep_hygiene_nudge",
    "gentle_movement",
    "social_reconnection",
    "deadline_chunking",
    "campus_resource_referral",
    "clarifying_question",
    "positive_reinforcement",
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_dir(skills_dir: str | Path = "skills") -> Path:
    p = Path(skills_dir)
    if p.exists():
        return p
    alt = _REPO_ROOT / p
    return alt if alt.exists() else p


def _parse_skill_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    meta: dict = {}
    body = text
    if text.startswith("+++"):
        parts = text.split("+++", 2)
        if len(parts) >= 3:
            meta = tomllib.loads(parts[1].strip())
            body = parts[2].strip()
    name = str(meta.get("name") or path.stem)
    description = str(meta.get("description") or "")
    when_to_use = str(meta.get("when_to_use") or "")
    contraindications = str(meta.get("contraindications") or "")
    return {
        "name": name,
        "description": description,
        "when_to_use": when_to_use,
        "contraindications": contraindications,
        "body": body,
        "source": f"skill.{name}",
        "summary": f"Loaded skill '{name}': {description}",
    }


def list_skills(skills_dir: str | Path = "skills") -> list[dict]:
    """List metadata (`name`, `description`, `when_to_use`, `contraindications`) for all skills."""
    d = _resolve_dir(skills_dir)
    out: list[dict] = []
    seen: set[str] = set()
    for name in SKILL_NAMES:
        p = d / f"{name}.md"
        if p.exists():
            parsed = _parse_skill_file(p)
            out.append({k: parsed[k] for k in ("name", "description", "when_to_use", "contraindications")})
            seen.add(name)
    if d.exists():
        for p in sorted(d.glob("*.md")):
            if p.stem not in seen:
                parsed = _parse_skill_file(p)
                out.append({k: parsed[k] for k in ("name", "description", "when_to_use", "contraindications")})
    return out


def skill_index_text(skills_dir: str | Path = "skills") -> str:
    """Return a concise formatted text index of all skills for agent prompts."""
    lines = []
    for s in list_skills(skills_dir):
        lines.append(
            f"- **{s['name']}**: {s['description']}\n"
            f"  - When to use: {s['when_to_use']}\n"
            f"  - Contraindications: {s['contraindications']}"
        )
    return "\n".join(lines)


def _match_skill_name(name: str, available: list[str]) -> str | None:
    if not name:
        return None
    norm = re.sub(r"[\s\-]+", "_", name.strip().lower())
    norm = re.sub(r"\.md$", "", norm)
    if norm in available:
        return norm
    for cand in available:
        if norm in cand or cand in norm:
            return cand
    matches = difflib.get_close_matches(norm, available, n=1, cutoff=0.55)
    return matches[0] if matches else None


def load_skill(name: str, skills_dir: str | Path = "skills") -> dict:
    """Load the full procedure, constraints, and examples for a skill by name."""
    d = _resolve_dir(skills_dir)
    avail = [p.stem for p in sorted(d.glob("*.md"))] if d.exists() else list(SKILL_NAMES)
    ordered_avail = [s for s in SKILL_NAMES if s in avail] + [s for s in avail if s not in SKILL_NAMES]
    matched = _match_skill_name(name, ordered_avail)
    if matched and (d / f"{matched}.md").exists():
        return _parse_skill_file(d / f"{matched}.md")
    return {
        "source": f"skill.{name}",
        "status": "not_found",
        "available": ordered_avail or list(SKILL_NAMES),
        "summary": f"Skill '{name}' not found; available: {', '.join(ordered_avail or SKILL_NAMES)}",
    }


def make_load_skill_tool(skills_dir: str | Path = "skills") -> Callable:
    """Return an aisuite-compatible tool callable `load_skill(name: str) -> dict`."""
    _dir = skills_dir

    def load_skill(name: str) -> dict:
        """Load the full coaching procedure, constraints, and examples for a named skill.

        Args:
            name: Skill identifier, one of micro_study_break, sleep_hygiene_nudge,
                gentle_movement, social_reconnection, deadline_chunking,
                campus_resource_referral, clarifying_question, positive_reinforcement.

        Returns:
            dict: Full skill metadata and Markdown body (procedure, constraints, examples).
        """
        return globals()["load_skill"](name, skills_dir=_dir)

    return load_skill

