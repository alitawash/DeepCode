"""Required output declarations for each orchestrator step and agent."""
from __future__ import annotations

from typing import Dict, List

REQUIRED_OUTPUTS: Dict[str, Dict[str, List[str]]] = {
    "step_0": {
        "orchestrator": [
            ".deepcode/session.json",
            ".deepcode/file_index.json",
        ]
    },
    "step_1": {
        "orchestrator": ["docs/charter.md"],
    },
    "step_2": {
        "orchestrator": [
            "docs/architecture.md",
            "docs/workplan.md",
        ],
        "ui_designer": [
            "ui/design_tokens.json",
            "ui/component_library.md",
            "ui/wireframes/main.md",
            "ui/checklists/accessibility.md",
            "ui/checklists/responsiveness.md",
        ],
    },
    "step_3": {
        "orchestrator": [
            "src/backend/main.py",
            "src/frontend/src/main.tsx",
            "src/frontend/src/design-system/tokens.ts",
            "src/frontend/src/design-system/BaseButton.tsx",
            "README.md",
            ".env.example",
            ".github/workflows/ci.yml",
        ]
    },
}


def required_for(step_name: str) -> Dict[str, List[str]]:
    """Return the required outputs for the given *step_name*."""

    return REQUIRED_OUTPUTS.get(step_name, {})
