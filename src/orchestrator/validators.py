"""Validation helpers for orchestrator steps and agent outputs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

from .required_outputs import required_for
from .session import compute_sha1, load_index, project_root

EXPECTED_SECTIONS: Dict[str, List[str]] = {
    "docs/charter.md": [
        "## Vision",
        "## Goals",
        "## Non-Goals",
        "## Success Metrics",
    ],
    "docs/architecture.md": [
        "## Overview",
        "## Components",
        "## Data Flow",
        "## Risks",
    ],
    "docs/workplan.md": [
        "## Milestones",
        "## Deliverables",
        "## Timeline",
    ],
    "ui/component_library.md": [
        "## Component Inventory",
        "## Usage Guidelines",
    ],
    "ui/checklists/accessibility.md": [
        "# Accessibility Checklist",
    ],
    "ui/checklists/responsiveness.md": [
        "# Responsiveness Checklist",
    ],
}


@dataclass
class FileValidationResult:
    path: str
    exists: bool
    hash_matches: bool
    sections_valid: bool


@dataclass
class AgentValidationState:
    agent: str
    required_files: List[FileValidationResult]

    @property
    def is_clean(self) -> bool:
        return all(
            result.exists and result.hash_matches and result.sections_valid
            for result in self.required_files
        )


def _validate_sections(path: Path, expected_sections: Iterable[str]) -> bool:
    if not expected_sections:
        return True
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return all(section in content for section in expected_sections)


def validate_agent_outputs(project_name: str, step_name: str, agent: str) -> AgentValidationState:
    """Validate the outputs for a given agent within a step."""

    root = project_root(project_name)
    index = load_index(project_name)
    required_files = []
    indexed_files: Mapping[str, Mapping[str, str]] = index.get("files", {})
    for relative_path in required_for(step_name).get(agent, []):
        file_path = root / relative_path
        exists = file_path.exists()
        current_hash = compute_sha1(file_path) if exists else None
        indexed_entry = indexed_files.get(relative_path, {})
        expected_hash = indexed_entry.get("sha1") if isinstance(indexed_entry, Mapping) else None
        hash_matches = exists and expected_hash == current_hash
        sections_expected = EXPECTED_SECTIONS.get(relative_path, [])
        sections_valid = _validate_sections(file_path, sections_expected)
        required_files.append(
            FileValidationResult(
                path=relative_path,
                exists=exists,
                hash_matches=bool(hash_matches),
                sections_valid=sections_valid,
            )
        )
    return AgentValidationState(agent=agent, required_files=required_files)


def detect_step_state(project_name: str, step_name: str) -> List[AgentValidationState]:
    """Return the validation state for all agents required for *step_name*."""

    outputs = required_for(step_name)
    return [
        validate_agent_outputs(project_name, step_name, agent)
        for agent in outputs.keys()
    ]
