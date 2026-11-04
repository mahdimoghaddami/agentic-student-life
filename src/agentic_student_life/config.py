"""Configuration loading (TOML via standard library tomllib) and ablation definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import tomllib
from typing import Any


@dataclass
class PlanningConfig:
    enabled: bool = True
    max_rounds: int = 2


@dataclass
class ReflectionConfig:
    enabled: bool = True
    max_rounds: int = 2


@dataclass
class MemoryConfig:
    enabled: bool = True
    history_k: int = 5


@dataclass
class SkillsConfig:
    enabled: bool = True


@dataclass
class ToolsConfig:
    enabled: bool = True
    max_turns: int = 5


@dataclass
class RunConfig:
    config_id: str = "full"
    description: str = "Full multi-agent system (planning=2, reflection=2, memory+skills+tools)"
    mode: str = "multi_agent"  # "multi_agent" | "single_agent"
    model: str = "gemini:gemini-3-flash-preview"
    temperature: float = 0.3
    max_workers: int = 4
    case_ids: list[str] | None = None  # None = all cases in cases/cases.jsonl
    planning: PlanningConfig = field(default_factory=PlanningConfig)
    reflection: ReflectionConfig = field(default_factory=ReflectionConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any], default_id: str = "full") -> "RunConfig":
        sys_blk = data.get("system", data)
        return cls(
            config_id=str(sys_blk.get("config_id", data.get("config_id", default_id))),
            description=str(sys_blk.get("description", data.get("description", ""))),
            mode=str(sys_blk.get("mode", "multi_agent")),
            model=str(sys_blk.get("model", "gemini:gemini-3.5-flash")),
            temperature=float(sys_blk.get("temperature", 0.3)),
            max_workers=int(sys_blk.get("max_workers", 4)),
            case_ids=sys_blk.get("case_ids", data.get("case_ids", None)),
            planning=PlanningConfig(**data["planning"]) if "planning" in data else PlanningConfig(),
            reflection=ReflectionConfig(**data["reflection"]) if "reflection" in data else ReflectionConfig(),
            memory=MemoryConfig(**data["memory"]) if "memory" in data else MemoryConfig(),
            skills=SkillsConfig(**data["skills"]) if "skills" in data else SkillsConfig(),
            tools=ToolsConfig(**data["tools"]) if "tools" in data else ToolsConfig(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_toml(self) -> str:
        lines = [
            "[system]",
            f'config_id = "{self.config_id}"',
            f'description = "{self.description}"',
            f'mode = "{self.mode}"',
            f'model = "{self.model}"',
            f"temperature = {self.temperature}",
            f"max_workers = {self.max_workers}",
        ]
        if self.case_ids is not None:
            ids_str = ", ".join(f'"{c}"' for c in self.case_ids)
            lines.append(f"case_ids = [{ids_str}]")
        lines.extend([
            "",
            "[planning]",
            f"enabled = {str(self.planning.enabled).lower()}",
            f"max_rounds = {self.planning.max_rounds}",
            "",
            "[reflection]",
            f"enabled = {str(self.reflection.enabled).lower()}",
            f"max_rounds = {self.reflection.max_rounds}",
            "",
            "[memory]",
            f"enabled = {str(self.memory.enabled).lower()}",
            f"history_k = {self.memory.history_k}",
            "",
            "[skills]",
            f"enabled = {str(self.skills.enabled).lower()}",
            "",
            "[tools]",
            f"enabled = {str(self.tools.enabled).lower()}",
            f"max_turns = {self.tools.max_turns}",
            "",
        ])
        return "\n".join(lines)


@dataclass
class JudgeConfig:
    model: str = "gemini:gemini-3-flash-preview"
    temperature: float = 0.0
    max_workers: int = 4

    @classmethod
    def from_toml(cls, path: str | Path = "configs/judge.toml") -> "JudgeConfig":
        p = Path(path)
        if not p.exists():
            return cls()
        with p.open("rb") as f:
            data = tomllib.load(f)
        blk = data.get("judge", data)
        return cls(
            model=str(blk.get("model", "gemini:gemini-3-flash-preview")),
            temperature=float(blk.get("temperature", 0.0)),
            max_workers=int(blk.get("max_workers", 4)),
        )


def load_run_config(path: str | Path = "configs/full.toml") -> RunConfig:
    p = Path(path)
    with p.open("rb") as f:
        data = tomllib.load(f)
    return RunConfig.from_dict(data, default_id=p.stem)


def load_ablation_configs(path: str | Path = "configs/ablations.toml") -> dict[str, RunConfig]:
    p = Path(path)
    with p.open("rb") as f:
        data = tomllib.load(f)
    defaults = data.get("defaults", {})
    configs_raw = data.get("configs", {})
    out: dict[str, RunConfig] = {}
    for cid, cdata in configs_raw.items():
        merged: dict[str, Any] = {}
        for section in ("system", "planning", "reflection", "memory", "skills", "tools"):
            base_sec = dict(defaults.get(section, {}))
            base_sec.update(cdata.get(section, {}))
            if base_sec:
                merged[section] = base_sec
        merged.setdefault("system", {})["config_id"] = cid
        if "description" in cdata:
            merged["system"]["description"] = cdata["description"]
        if "case_ids" in cdata:
            merged["system"]["case_ids"] = cdata["case_ids"]
        out[cid] = RunConfig.from_dict(merged, default_id=cid)
    return out

