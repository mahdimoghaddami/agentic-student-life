"""Simulated initial student profiles grounded in real pre-term surveys (`surveys.json`)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..data.store import DataStore

SELECTED_UIDS: tuple[str, ...] = ("u59", "u08", "u19", "u10", "u57", "u16", "u00", "u02")

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.exists() or p.is_absolute():
        return p
    alt = _REPO_ROOT / p
    return alt if alt.parent.exists() else p


def _survey_str(sv: dict) -> str:
    parts = []
    for k, label in (
        ("pss_total", "PSS"),
        ("phq9_total", "PHQ-9"),
        ("loneliness_total", "UCLA Loneliness"),
        ("phq9_item9_selfharm", "PHQ-9 item 9"),
        ("bfi_extraversion", "Extraversion"),
        ("bfi_neuroticism", "Neuroticism"),
        ("bfi_conscientiousness", "Conscientiousness"),
    ):
        if k in sv:
            parts.append(f"{label}={sv[k]}")
    return ", ".join(parts)


def build_profiles(
    cache_dir: str = "cache/features",
    out_path: str | Path = "cases/profiles.json",
) -> dict[str, dict]:
    """Build and save the 8 participant profiles grounded in real pre-term survey data."""
    ds = DataStore(cache_dir)
    surveys = ds.surveys
    academic = ds.academic

    specs: dict[str, dict] = {
        "u59": {
            "goals": [
                "Protect at least 6.5-7 hours of sleep instead of pulling late-night all-nighters before CS and German deadlines",
                "Break up heavy assignment and lab nights into manageable evening blocks",
                "Unwind with calm solo routines (music or tea) when feeling drained",
            ],
            "preferences": {
                "activity_style": "Calm solo wind-downs (listening to music, short tea break, light stretching)",
                "tone": "Warm, encouraging, peer-like, never preachy",
                "preferred_times": ["evening (19:00-22:00)"],
                "dislikes": ["judgmental lectures about late bedtimes", "rigid early-morning schedules"],
            },
            "constraints": [
                "Takes 3 courses (GERM 001, COSC 065, COSC 007) with frequent weekly deadlines",
                "Often works late in the evening and naps in the afternoon",
            ],
        },
        "u08": {
            "goals": [
                "Avoid severe sleep crashes (<5 hours) during CS 65 and CS 89 project weeks",
                "Take 10-minute movement or posture resets during long coding sessions",
                "Keep stress manageable ahead of back-to-back technical deadlines",
            ],
            "preferences": {
                "activity_style": "Short campus walks or quick desk/hallway stretches between coding blocks",
                "tone": "Practical, direct, and concise",
                "preferred_times": ["evening (19:00-21:30)"],
                "dislikes": ["long multi-step checklists", "vague motivational quotes"],
            },
            "constraints": [
                "Heavy computer science courseload (CHIN 062, COSC 089, COSC 065)",
                "Limited free time on Monday/Tuesday/Thursday afternoons due to language and CS classes",
            ],
        },
        "u19": {
            "goals": [
                "Manage overwhelm during clustered CS 50, CS 65, and FILM 51 deadlines by chunking tasks",
                "Stay connected with supportive peers or campus resources when feeling isolated or stressed",
                "Maintain steady ~7.5h sleep routine across midterm and late-term weeks",
            ],
            "preferences": {
                "activity_style": "Gentle walks, Ultimate Frisbee / light outdoor air, or low-pressure 1-on-1 check-ins",
                "tone": "Compassionate, validating, non-clinical, and low-pressure",
                "preferred_times": ["evening (19:00-21:00)"],
                "dislikes": ["high-pressure productivity demands", "clinical or robotic phrasing"],
            },
            "constraints": [
                "Elevated baseline loneliness (UCLA=55.0) and moderate perceived stress (PSS=20.0); pre-term PHQ-9 item 9=1 requires warm resource awareness when stress peaks at 5/5",
                "Enrolled in COSC 050, COSC 065, and FILM 051",
            ],
        },
        "u10": {
            "goals": [
                "Decompress from back-to-back CS 50, CS 65, and BIOL 004 coursework with brief evening breaks",
                "Maintain low-pressure social touchpoints without forced group socializing",
                "Keep a steady sleep and walking rhythm during midterm weeks",
            ],
            "preferences": {
                "activity_style": "Solo campus walks, quiet breathing/stretching breaks, or texting one close contact",
                "tone": "Calm, matter-of-fact, respectful of introversion",
                "preferred_times": ["evening (19:30-21:30)"],
                "dislikes": ["crowded group social events", "overly bubbly cheerleading"],
            },
            "constraints": [
                "High pre-term loneliness score (UCLA=64.0) paired with low extraversion (2.0) and high conscientiousness (4.78)",
                "Taking two intensive CS courses (COSC 050, COSC 065) plus BIOL 004",
            ],
        },
        "u57": {
            "goals": [
                "Balance computer networks (COSC 060) and smartphone programming (COSC 065) homework with recovery",
                "Keep sleep above 7 hours on nights before 10:00 AM classes",
                "Use short study breaks when stress spikes during project deadlines",
            ],
            "preferences": {
                "activity_style": "Active walks, fencing/light movement, or focused 25-minute study blocks with short breaks",
                "tone": "Brief, upbeat, and action-oriented",
                "preferred_times": ["evening (19:00-21:00)"],
                "dislikes": ["unnecessary notifications when habits are already on track"],
            },
            "constraints": [
                "Enrolled in COSC 060 and COSC 065 with Monday/Wednesday/Friday morning classes",
                "Prefers not to be interrupted when sleep and stress are steady",
            ],
        },
        "u16": {
            "goals": [
                "Reduce high stress (PSS=24.0) during COSC 065 and COSC 027 labs with short restorative micro-breaks",
                "Keep a consistent evening wind-down routine without feeling pressured into heavy workouts",
                "Break lab assignments into small, concrete next steps when feeling overwhelmed",
            ],
            "preferences": {
                "activity_style": "Quiet indoor micro-breaks (stretching, deep breathing, warm tea)",
                "tone": "Gentle, concise, low-burden",
                "preferred_times": ["evening (19:30-21:00)"],
                "dislikes": ["high-intensity exercise pushes", "long-winded messages"],
            },
            "constraints": [
                "High baseline perceived stress (PSS=24.0) and neuroticism (4.25) with low extraversion (1.75)",
                "Studies frequently in quiet campus spaces and prefers low-friction resets",
            ],
        },
        "u00": {
            "goals": [
                "Stabilize sleep duration (avoiding <5h nights) and recover consistently across the term",
                "Take brief movement or outdoor walks on low-activity days to manage stress (PSS=24.0)",
                "Maintain steady daily energy and mood",
            ],
            "preferences": {
                "activity_style": "Outdoor walks, light stretching, or early evening wind-downs",
                "tone": "Supportive, conversational, grounded",
                "preferred_times": ["evening (19:00-21:00)"],
                "dislikes": ["generic advice disconnected from recent sleep or activity"],
            },
            "constraints": [
                "High baseline perceived stress (PSS=24.0) with variable night-to-night sleep duration",
                "Occasional multi-day gaps in phone sensing late in the term",
            ],
        },
        "u02": {
            "goals": [
                "Protect sleep (>=7 hours) ahead of COSC 065 and COSC 077 deadlines",
                "Use structured task chunking and brief pauses when pre-deadline stress rises",
                "Avoid notification fatigue on calm, well-rested days",
            ],
            "preferences": {
                "activity_style": "Short walks, quiet study breaks, and structured 30-minute task blocks",
                "tone": "Calm, respectful, non-intrusive",
                "preferred_times": ["evening (19:30-21:00)"],
                "dislikes": ["interruptions when stress is low and sleep is >7.5h"],
            },
            "constraints": [
                "Elevated pre-term PHQ-9 (13.0) and PSS (21.0) with low extraversion (2.12)",
                "Enrolled in COSC 065 and COSC 077",
            ],
        },
    }

    profiles: dict[str, dict] = {}
    for uid in SELECTED_UIDS:
        sv = surveys.get(uid, {})
        courses = [c["course"] for c in academic.get(uid, {}).get("classes", [])]
        course_note = f"; courses: {', '.join(courses)}" if courses else "; no syllabus courses listed"
        spec = specs[uid]
        # The cache is authoritative for measured background scores; older
        # hand-authored profile prose must not contradict rebuilt survey scores.
        constraints = list(spec["constraints"])
        if "loneliness_total" in sv:
            constraints = [re.sub(r"UCLA=\d+(?:\.\d+)?",
                                  f"UCLA={sv['loneliness_total']}", text)
                           for text in constraints]
        profiles[uid] = {
            "participant_id": uid,
            "simulated": True,
            "grounding_note": (
                f"Simulated coaching profile grounded in real StudentLife pre-term surveys "
                f"({_survey_str(sv)}){course_note}."
            ),
            "pre_term_surveys": sv,
            "goals": spec["goals"],
            "preferences": spec["preferences"],
            "constraints": constraints,
            "learned_preferences": [],
        }

    target = _resolve_path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
    return profiles


def load_profiles(path: str | Path = "cases/profiles.json") -> dict[str, dict]:
    """Load participant profiles from `cases/profiles.json` (building if missing)."""
    p = _resolve_path(path)
    if not p.exists():
        return build_profiles(out_path=p)
    return json.loads(p.read_text(encoding="utf-8"))

