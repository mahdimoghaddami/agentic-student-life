"""Coaching skills index and on-demand loader."""

from .library import (
    SKILL_NAMES,
    list_skills,
    load_skill,
    make_load_skill_tool,
    skill_index_text,
)

__all__ = [
    "SKILL_NAMES",
    "list_skills",
    "skill_index_text",
    "load_skill",
    "make_load_skill_tool",
]

