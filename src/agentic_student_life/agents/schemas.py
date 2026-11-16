"""Pydantic schemas for structured communication between agents."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    source: str = Field(description="Data source tag, e.g. sensing.sleep, ema.stress, education.deadlines, simulated_profile, memory.feedback")
    detail: str = Field(description="Concise factual finding from that source")
    simulated: bool = Field(default=False, description="True if derived from simulated profile or simulated feedback")


class PlannerOutput(BaseModel):
    status: Literal["gather_more", "finalize"] = Field(
        description="Use 'gather_more' if additional tool checks are needed and allowed; 'finalize' once ready to decide."
    )
    hypotheses: list[str] = Field(default_factory=list, description="1-3 brief hypotheses about the student's state")
    plan_steps: list[str] = Field(default_factory=list, description="Specific data checks for the Context Analyst")
    decision: Literal["suggest", "ask", "none"] = Field(
        description="Final coaching action: 'suggest' (send supportive tip/resource), 'ask' (clarifying question when key data is missing), or 'none' (doing fine or recent message already sent)"
    )
    skill_to_use: str | None = Field(
        default=None,
        description="Name of the coaching skill to load when decision is 'suggest' or 'ask', or null when decision is 'none'",
    )
    target_goal: str = Field(default="", description="Which student goal this action supports")
    writer_guidance: str = Field(
        default="",
        description="Concrete instructions and preference/feedback constraints for the Message Writer",
    )
    rationale: str = Field(default="", description="Brief justification for the decision")


class AnalystOutput(BaseModel):
    findings: list[EvidenceItem] = Field(default_factory=list, description="Structured evidence items from tools")
    missing_modalities: list[str] = Field(default_factory=list, description="List of modalities that returned status='missing'")
    stress_level_assessment: Literal["low", "moderate", "high", "severe", "unknown_missing_data"] = Field(
        description="Overall assessment of student stress/risk or missing data"
    )
    summary: str = Field(description="Concise synthesis of the student's current behavioral and emotional state")


class WriterOutput(BaseModel):
    decision: Literal["suggest", "ask", "none"] = Field(description="'suggest', 'ask', or 'none'")
    skill_used: str | None = Field(default=None, description="Skill used to write the message, or null if decision=='none'")
    final_message: str | None = Field(
        default=None,
        description="The supportive coaching message or clarifying question sent to the student, or null if decision=='none'",
    )
    rationale: str = Field(default="", description="Why this message fits the evidence and preferences")


class CriticOutput(BaseModel):
    verdict: Literal["pass", "revise"] = Field(description="'pass' if all checks succeed, 'revise' if any issue is found")
    critique: str = Field(description="Evaluation of context awareness, goal alignment, preference compliance, clarity, and safety")
    revision_instructions: str = Field(default="", description="Specific changes the Writer must make if verdict=='revise'")


class MemoryUpdateOutput(BaseModel):
    new_preferences: list[str] = Field(
        default_factory=list,
        description="Crisp, actionable preference rules extracted from the student's feedback on this episode",
    )


class SingleAgentOutput(BaseModel):
    decision: Literal["suggest", "ask", "none"] = Field(description="Final decision: 'suggest', 'ask', or 'none'")
    skill_used: str | None = Field(default=None, description="Skill name used, or null if decision=='none'")
    plan: list[str] = Field(default_factory=list, description="Steps taken to inspect student context")
    evidence: list[EvidenceItem] = Field(default_factory=list, description="Key evidence items supporting the decision")
    final_message: str | None = Field(default=None, description="Final coaching message or question, or null if decision=='none'")
    rationale: str = Field(default="", description="Brief justification")

