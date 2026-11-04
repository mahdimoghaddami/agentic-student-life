"""Persistent per-run memory store for simulated profiles, past episodes, and learned preferences."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import threading
from typing import Any, Callable


class MemoryStore:
    """Manages `runs/<run_id>/memory/<uid>.json` so each run/ablation has isolated memory."""

    def __init__(self, run_dir: str | Path, profiles: dict[str, Any]):
        self.mem_dir = Path(run_dir) / "memory"
        self.mem_dir.mkdir(parents=True, exist_ok=True)
        self.profiles = profiles
        self._lock = threading.Lock()

    def _path(self, uid: str) -> Path:
        return self.mem_dir / f"{uid}.json"

    def reset(self, uid: str | None = None) -> None:
        """Delete stored memory (all participants or one participant)."""
        with self._lock:
            if uid is not None:
                p = self._path(uid)
                if p.exists():
                    p.unlink()
            else:
                if self.mem_dir.exists():
                    shutil.rmtree(self.mem_dir)
                self.mem_dir.mkdir(parents=True, exist_ok=True)

    def load(self, uid: str) -> dict[str, Any]:
        with self._lock:
            p = self._path(uid)
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    return json.load(f)
            prof = self.profiles.get(
                uid,
                {
                    "participant_id": uid,
                    "simulated": True,
                    "goals": ["Manage academic stress", "Maintain healthy sleep"],
                    "preferences": {"tone": "warm and concise"},
                    "constraints": [],
                },
            )
            init_state = {
                "participant_id": uid,
                "simulated": True,
                "profile": prof,
                "episodes": [],
                "learned_preferences": [],
            }
            with p.open("w", encoding="utf-8") as f:
                json.dump(init_state, f, indent=2)
            return init_state

    def save(self, uid: str, state: dict[str, Any]) -> None:
        with self._lock:
            p = self._path(uid)
            with p.open("w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

    def get_snapshot(self, uid: str, enabled: bool = True, history_k: int = 5) -> dict[str, Any]:
        state = self.load(uid)
        if not enabled:
            return {
                "participant_id": uid,
                "simulated_profile": state.get("profile", {}),
                "learned_preferences": [],
                "recent_episodes": [],
                "memory_enabled": False,
            }
        return {
            "participant_id": uid,
            "simulated_profile": state.get("profile", {}),
            "learned_preferences": state.get("learned_preferences", []),
            "recent_episodes": state.get("episodes", [])[-history_k:],
            "memory_enabled": True,
        }

    def format_for_prompt(self, uid: str, enabled: bool = True, history_k: int = 5) -> str:
        snap = self.get_snapshot(uid, enabled=enabled, history_k=history_k)
        prof = snap["simulated_profile"]
        lines = [
            f"### Student Profile (Participant {uid}, SIMULATED=true)",
            f"- Goals: {json.dumps(prof.get('goals', []))}",
            f"- Baseline Preferences: {json.dumps(prof.get('preferences', {}))}",
            f"- Constraints: {json.dumps(prof.get('constraints', []))}",
        ]
        if enabled:
            lprefs = snap["learned_preferences"]
            if lprefs:
                lines.append("\n### CRITICAL LEARNED PREFERENCES FROM PAST FEEDBACK (SIMULATED=true, MUST OBEY):")
                for lp in lprefs:
                    lines.append(
                        f"- [{lp.get('learned_at', '')}] {lp.get('preference', '')} "
                        f"(from {lp.get('from_case_id', '')})"
                    )
            else:
                lines.append("\n### Learned Preferences from Past Interactions: None yet.")

            eps = snap["recent_episodes"]
            if eps:
                lines.append(f"\n### Recent Interaction History (last {len(eps)} episodes):")
                for ep in eps:
                    fb = ep.get("simulated_feedback") or {}
                    fb_txt = fb.get("feedback_text", "no feedback") if isinstance(fb, dict) else str(fb)
                    acc = fb.get("accepted") if isinstance(fb, dict) else None
                    lines.append(
                        f"- [{ep.get('decision_time')}] decision={ep.get('decision')} "
                        f"skill={ep.get('skill_used')} | message={ep.get('final_message')!r} "
                        f"| student_accepted={acc} | student_feedback={fb_txt!r}"
                    )
            else:
                lines.append("\n### Recent Interaction History: No prior episodes.")
        return "\n".join(lines)

    def record_episode(
        self,
        *,
        uid: str,
        case_id: str,
        decision_time: str,
        decision: str,
        skill_used: str | None,
        final_message: str | None,
        feedback: dict[str, Any] | None,
        new_preferences: list[str],
    ) -> list[str]:
        state = self.load(uid)
        # Avoid duplicate entries if a case is re-run
        state["episodes"] = [e for e in state.get("episodes", []) if e.get("case_id") != case_id]
        state["episodes"].append(
            {
                "case_id": case_id,
                "decision_time": decision_time,
                "decision": decision,
                "skill_used": skill_used,
                "final_message": final_message,
                "simulated_feedback": feedback,
                "simulated": True,
            }
        )
        recorded_updates: list[str] = []
        existing_texts = {lp.get("preference", "") for lp in state.get("learned_preferences", [])}
        for pref in new_preferences:
            pref_clean = pref.strip()
            if pref_clean and pref_clean not in existing_texts:
                state.setdefault("learned_preferences", []).append(
                    {
                        "preference": pref_clean,
                        "learned_at": decision_time,
                        "from_case_id": case_id,
                        "simulated": True,
                    }
                )
                existing_texts.add(pref_clean)
                recorded_updates.append(pref_clean)
        self.save(uid, state)
        return recorded_updates

    def make_recall_tool(self, uid: str, enabled: bool = True, history_k: int = 5) -> Callable:
        def recall_memory(query: str = "all") -> dict[str, Any]:
            """Recall the student's simulated profile, learned preferences from feedback, and recent interaction history.

            Args:
                query: Topic to recall ('all', 'preferences', 'history', or 'goals').
            """
            snap = self.get_snapshot(uid, enabled=enabled, history_k=history_k)
            snap["source"] = "memory.store"
            snap["query"] = query
            return snap

        return recall_memory

