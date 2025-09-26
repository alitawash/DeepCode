"""UI Designer agent responsible for foundational UI artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from src.orchestrator.session import project_root

DESIGN_TOKENS: Dict[str, Dict[str, str]] = {
    "color": {
        "background": "#f4f6fb",
        "surface": "#ffffff",
        "primary": "#1f6feb",
        "primary_text": "#ffffff",
        "secondary": "#6e7781",
        "secondary_text": "#0a0c10",
        "border": "#d0d7de",
        "highlight": "#ffd33d",
        "danger": "#d1242f",
        "success": "#2da44e",
    },
    "spacing": {
        "xs": "4px",
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "xl": "32px",
    },
    "radius": {
        "sm": "6px",
        "md": "12px",
        "lg": "18px",
    },
    "shadow": {
        "soft": "0 10px 25px rgba(15, 23, 42, 0.1)",
    },
    "typography": {
        "font_family": "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "font_size_sm": "0.875rem",
        "font_size_md": "1rem",
        "font_size_lg": "1.125rem",
        "font_weight_regular": "400",
        "font_weight_semibold": "600",
    },
}

COMPONENT_LIBRARY_MD = """# UI Component Library\n\n## Component Inventory\n- **BaseButton** — primary action button with prominence and hover states.\n- **SurfaceCard** — elevated container for key summaries.\n- **StatusChip** — compact status indicator for Clean/Dirty states.\n\n## Usage Guidelines\n- Use **BaseButton** for the primary call-to-action per screen.\n- Combine **SurfaceCard** and **StatusChip** to emphasise gated approvals.\n- Respect spacing tokens (`spacing.md`) between stacked components.\n"""

ACCESSIBILITY_CHECKLIST = """# Accessibility Checklist\n- [ ] Provide descriptive labels for all chat input prompts.\n- [ ] Ensure sufficient color contrast (> 4.5:1) for text on colored backgrounds.\n- [ ] Support keyboard navigation for approval buttons (Yes/No).\n- [ ] Announce gate transitions to assistive technologies.\n"""

RESPONSIVENESS_CHECKLIST = """# Responsiveness Checklist\n- [ ] Maintain padding using spacing tokens across viewports.\n- [ ] Collapse the summary sidebar beneath the main content below 768px.\n- [ ] Use fluid typography scaling between `font_size_sm` and `font_size_lg`.\n- [ ] Ensure BaseButton spans full width on screens < 480px.\n"""

WIREFRAME_MAIN = """# Wireframe — Project Orchestrator\n\n## Layout\n- **Header Banner**: displays project name, step title, and Clean/Dirty chips.\n- **Chat Stream**: conversational updates with highlighted action items.\n- **Artifact Drawer**: expandable panel listing generated documents and code paths.\n- **Approval Footer**: sticky footer with Yes/No options and cost recap.\n\n## Highlights\n- Tokens apply to background gradients in header and chip accents.\n- BaseButton emphasises primary action with drop shadow (`shadow.soft`).\n- StatusChip variants reflect Clean (success) vs Dirty (danger).\n"""


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def generate_ui_foundations(project_name: str) -> Dict[str, Path]:
    """Create or refresh the UI foundation artifacts for *project_name*."""

    root = project_root(project_name)
    artifact_paths = {
        "tokens": root / "ui/design_tokens.json",
        "component_library": root / "ui/component_library.md",
        "wireframe_main": root / "ui/wireframes/main.md",
        "accessibility_checklist": root / "ui/checklists/accessibility.md",
        "responsiveness_checklist": root / "ui/checklists/responsiveness.md",
    }

    _write_json(artifact_paths["tokens"], DESIGN_TOKENS)
    _write_text(artifact_paths["component_library"], COMPONENT_LIBRARY_MD)
    _write_text(artifact_paths["wireframe_main"], WIREFRAME_MAIN)
    _write_text(artifact_paths["accessibility_checklist"], ACCESSIBILITY_CHECKLIST)
    _write_text(artifact_paths["responsiveness_checklist"], RESPONSIVENESS_CHECKLIST)

    return artifact_paths
