from dataclasses import dataclass, asdict
import os
from .io import read_json
@dataclass
class Config:
    name: str = "full"
    mode: str = "multi"
    planning_rounds: int = 1
    reflection_cycles: int = 1
    tools: bool = True
    memory: bool = True
    skills: bool = True
    provider: str = "env"
    model: str = "env"
    temperature: float = 0.0
    max_tokens: int = 1200
    tool_turns: int = 3
    def validate(self):
        if self.mode not in ("multi","single"): raise ValueError("Invalid mode")
        for k in ("planning_rounds","reflection_cycles","tool_turns"):
            if not isinstance(getattr(self,k),int) or getattr(self,k)<0: raise ValueError(k)
        if self.tool_turns<1: raise ValueError("tool_turns must be positive")
        return self
    def to_dict(self): return asdict(self)
def load_config(path): return Config(**read_json(path)).validate()
def resolve_model(provider,model):
    if provider=="env": provider=os.getenv("COACH_PROVIDER","ollama")
    if model=="env": model=os.getenv("GEMINI_MODEL" if provider=="gemini" else "OLLAMA_MODEL","")
    if provider=="mock": model="deterministic-demo"
    if not model or "YOUR_" in model: raise ValueError("Set a valid model in .env")
    if provider=="gemini" and model.startswith("openai:"): model=model[7:]
    if provider not in ("mock","gemini","ollama"): raise ValueError("Unknown provider")
    return provider,model
