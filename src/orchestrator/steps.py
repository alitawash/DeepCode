"""Step metadata and helper routines for the orchestrator pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .required_outputs import REQUIRED_OUTPUTS


@dataclass(frozen=True)
class StepDefinition:
    name: str
    title: str
    description: str
    gate_prompt: str
    next_step: Optional[str]

    @property
    def required_outputs(self) -> Dict[str, List[str]]:
        return REQUIRED_OUTPUTS.get(self.name, {})


STEP_SEQUENCE: List[StepDefinition] = [
    StepDefinition(
        name="step_0",
        title="Project Handshake",
        description="Capture initial project metadata and ensure persistence folders exist.",
        gate_prompt="Proceed to Step 1 (Discovery & Intent) with project '{name}'?",
        next_step="step_1",
    ),
    StepDefinition(
        name="step_1",
        title="Discovery & Intent",
        description="Draft the solution charter capturing vision, goals, non-goals, and metrics.",
        gate_prompt="Approve the Solution Charter and proceed to Step 2 (Architecture & UI Foundations)?",
        next_step="step_2",
    ),
    StepDefinition(
        name="step_2",
        title="Architecture & UI Foundations",
        description="Outline architecture, workplan, and establish UI design artifacts.",
        gate_prompt="Approve the architecture and UI foundations to proceed to Step 3 (Scaffold)?",
        next_step="step_3",
    ),
    StepDefinition(
        name="step_3",
        title="Scaffold",
        description="Provide backend/frontend scaffolding, design-system primitives, and CI plumbing.",
        gate_prompt="Scaffold validated. Proceed to Step 4 (Feature Iteration 1)?",
        next_step="step_4",
    ),
    StepDefinition(
        name="step_4",
        title="Feature Iteration 1",
        description="Stub for future feature delivery iterations.",
        gate_prompt="Continue to Step 5 (Feature Iteration 2)?",
        next_step="step_5",
    ),
    StepDefinition(
        name="step_5",
        title="Feature Iteration 2",
        description="Stub for continued feature iteration.",
        gate_prompt="Continue to Step 6 (Integration & E2E)?",
        next_step="step_6",
    ),
    StepDefinition(
        name="step_6",
        title="Integration & E2E",
        description="Stub for integration and end-to-end validation.",
        gate_prompt="Continue to Step 7 (Release Prep)?",
        next_step="step_7",
    ),
    StepDefinition(
        name="step_7",
        title="Release Prep",
        description="Stub for release preparation and summary.",
        gate_prompt="Mark project as ready for release?",
        next_step=None,
    ),
]


STEP_INDEX = {step.name: step for step in STEP_SEQUENCE}


def get_step(step_name: str) -> StepDefinition:
    """Return the step definition for *step_name*."""

    if step_name not in STEP_INDEX:
        raise KeyError(f"Unknown step '{step_name}'")
    return STEP_INDEX[step_name]


def first_step() -> StepDefinition:
    return STEP_SEQUENCE[0]


def next_step(step_name: str) -> Optional[StepDefinition]:
    step = get_step(step_name)
    if not step.next_step:
        return None
    return get_step(step.next_step)
