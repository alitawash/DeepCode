"""Chat-only orchestrator entrypoint implementing the gated workflow."""
from __future__ import annotations

import asyncio
import math
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.agents.ui_designer import generate_ui_foundations
from src.orchestrator.session import (
    check_lock,
    compute_sha1,
    ensure_project_root,
    index_set,
    load_index,
    load_session,
    normalize_name,
    prefetch_index_and_hash_sample,
    probe_existing_project,
    project_root,
    save_index,
    save_session,
)
from src.orchestrator.steps import StepDefinition, get_step, next_step
from src.orchestrator.validators import AgentValidationState, detect_step_state


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_directories(root: Path) -> None:
    for folder in [
        "docs",
        "src",
        "src/backend",
        "src/frontend",
        "src/frontend/src",
        "src/frontend/src/design-system",
        "src/frontend/public",
        "tests",
        "ui",
        "ui/wireframes",
        "ui/checklists",
        ".github",
        ".github/workflows",
    ]:
        (root / folder).mkdir(parents=True, exist_ok=True)


def _record_file(index: Dict[str, Dict[str, Dict[str, str]]], relative_path: str, sha1: str, step_name: str) -> None:
    metadata = {
        "sha1": sha1,
        "last_step": step_name,
        "updated_at": _timestamp(),
    }
    index_set(index, Path(relative_path), metadata)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_if_different(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    _write(path, content)


def _generate_step0(project_name: str) -> None:
    root = ensure_project_root(project_name)
    _ensure_directories(root)
    session = load_session(project_name)
    session.update(
        {
            "project_name": project_name,
            "current_step": "step_0",
            "last_updated": _timestamp(),
            "history": session.get("history", []),
        }
    )
    save_session(project_name, session)

    index: Dict[str, Dict[str, Dict[str, str]]] = {"files": {}, "folders": []}
    folders = [
        "docs",
        "src",
        "src/backend",
        "src/frontend",
        "src/frontend/src",
        "src/frontend/src/design-system",
        "src/frontend/public",
        "tests",
        "ui",
        "ui/wireframes",
        "ui/checklists",
    ]
    index["folders"] = folders
    session_path = Path(".deepcode/session.json")
    session_hash = compute_sha1(root / session_path)
    _record_file(index, str(session_path), session_hash, "step_0")
    save_index(project_name, index)
    index_hash = compute_sha1(root / ".deepcode/file_index.json")
    _record_file(index, ".deepcode/file_index.json", index_hash, "step_0")
    save_index(project_name, index)
    final_index_hash = compute_sha1(root / ".deepcode/file_index.json")
    if final_index_hash != index_hash:
        _record_file(index, ".deepcode/file_index.json", final_index_hash, "step_0")
        save_index(project_name, index)


def _generate_step1(project_name: str) -> None:
    root = ensure_project_root(project_name)
    charter = """# Solution Charter\n\n## Vision\nDeliver a deterministic, step-gated orchestrator for project aware code generation.\n\n## Goals\n- Enforce chat-only interactions with explicit approvals.\n- Maintain project persistence under `projects/<name>/`.\n- Provide agent-level validation with Clean/Dirty surfacing.\n\n## Non-Goals\n- Building full production deployment scripts.\n- Integrating proprietary APIs without explicit configuration.\n\n## Success Metrics\n- 100% of required artifacts exist per step.\n- Locks prevent concurrent mutation for active sessions.\n- UI header always reflects project + step context.\n"""
    path = root / "docs/charter.md"
    _write_if_different(path, charter)
    index = load_index(project_name)
    _record_file(index, "docs/charter.md", compute_sha1(path), "step_1")
    save_index(project_name, index)


def _generate_step2_orchestrator(project_name: str) -> None:
    root = ensure_project_root(project_name)
    architecture = """# System Architecture\n\n## Overview\nThe system orchestrates gated project workflows across chat-only interactions.\n\n## Components\n- **Chat Application** mediates prompts, approvals, and cost accounting.\n- **Orchestrator Core** manages project sessions, indexing, and lock handling.\n- **UI Designer Agent** maintains tokens, components, and wireframes.\n- **Backend/Frontend Scaffold** exposes validated starting points for features.\n\n## Data Flow\n1. User submits chat input.\n2. Orchestrator probes project state, lock, and index.\n3. Dirty agents regenerate artifacts before approval gating.\n4. Responses include cost metrics and step prompts.\n\n## Risks\n- Lock contention between parallel sessions.\n- Token estimation drift when responses vary widely.\n- Missing filesystem permissions causing index divergence.\n"""
    workplan = """# Workplan\n\n## Milestones\n1. Handshake & charter creation.\n2. Architecture + UI foundations.\n3. Scaffold delivery with design token integration.\n\n## Deliverables\n- Persistent session + index metadata.\n- Architecture/workplan documentation.\n- UI tokens, component library, checklists, and wireframes.\n\n## Timeline\n- Each step gated by explicit Yes/No approval with validation.\n"""
    architecture_path = root / "docs/architecture.md"
    workplan_path = root / "docs/workplan.md"
    _write_if_different(architecture_path, architecture)
    _write_if_different(workplan_path, workplan)
    index = load_index(project_name)
    _record_file(index, "docs/architecture.md", compute_sha1(architecture_path), "step_2")
    _record_file(index, "docs/workplan.md", compute_sha1(workplan_path), "step_2")
    save_index(project_name, index)


def _generate_step2_ui(project_name: str) -> None:
    artifacts = generate_ui_foundations(project_name)
    index = load_index(project_name)
    root = project_root(project_name)
    for _, path in artifacts.items():
        relative = str(path.relative_to(root))
        _record_file(index, relative, compute_sha1(path), "step_2")
    save_index(project_name, index)


def _generate_step3(project_name: str) -> None:
    root = ensure_project_root(project_name)
    backend_path = root / "src/backend/main.py"
    backend_content = """from fastapi import FastAPI\n\napp = FastAPI(title=\"DeepCode Orchestrator API\")\n\n\n@app.get(\"/health\")\ndef health() -> dict[str, str]:\n    \"\"\"Simple readiness probe for deployment automation.\"\"\"\n    return {\"status\": \"ok\"}\n"""
    _write_if_different(backend_path, backend_content)

    frontend_main_path = root / "src/frontend/src/main.tsx"
    frontend_main_content = """import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport { BaseButton } from './design-system/BaseButton';\nimport { useDesignTokens } from './design-system/tokens';\n\nconst App: React.FC = () => {\n  const tokens = useDesignTokens();\n\n  return (\n    <div\n      style={{\n        fontFamily: tokens.typography.font_family,\n        background: tokens.color.background,\n        minHeight: '100vh',\n        padding: tokens.spacing.lg,\n      }}\n    >\n      <header\n        style={{\n          background: tokens.color.surface,\n          borderRadius: tokens.radius.lg,\n          padding: tokens.spacing.lg,\n          boxShadow: tokens.shadow.soft,\n          border: `1px solid ${tokens.color.border}`,\n        }}\n      >\n        <h1 style={{ margin: 0, color: tokens.color.secondary_text }}>DeepCode Orchestrator</h1>\n        <p style={{ color: tokens.color.secondary }}>Async chat-only workflow controller.</p>\n        <div style={{ display: 'flex', gap: tokens.spacing.sm }}>\n          <BaseButton intent=\"primary\">Approve</BaseButton>\n          <BaseButton intent=\"secondary\">Decline</BaseButton>\n        </div>\n      </header>\n    </div>\n  );\n};\n\nconst root = document.getElementById('root');\n\nif (root) {\n  ReactDOM.createRoot(root).render(<App />);\n}\n"""
    _write_if_different(frontend_main_path, frontend_main_content)

    tokens_ts_path = root / "src/frontend/src/design-system/tokens.ts"
    tokens_ts_content = """import { useEffect, useState } from 'react';\nimport designTokens from '../../../../ui/design_tokens.json';\n\nexport type DesignTokens = typeof designTokens;\n\nexport const tokens: DesignTokens = designTokens;\n\nexport function useDesignTokens(): DesignTokens {\n  const [state, setState] = useState<DesignTokens>(tokens);\n\n  useEffect(() => {\n    setState(tokens);\n  }, []);\n\n  return state;\n}\n\nexport function cssVariables(): Record<string, string> {\n  const vars: Record<string, string> = {};\n\n  for (const [groupName, groupValues] of Object.entries(tokens)) {\n    for (const [tokenName, tokenValue] of Object.entries(groupValues)) {\n      vars[`--dc-${groupName}-${tokenName}`] = tokenValue;\n    }\n  }\n\n  return vars;\n}\n"""
    _write_if_different(tokens_ts_path, tokens_ts_content)

    base_button_path = root / "src/frontend/src/design-system/BaseButton.tsx"
    base_button_content = """import React from 'react';\nimport { tokens } from './tokens';\n\ntype Intent = 'primary' | 'secondary' | 'danger';\n\nconst intentToColor: Record<Intent, { background: string; color: string }> = {\n  primary: {\n    background: tokens.color.primary,\n    color: tokens.color.primary_text,\n  },\n  secondary: {\n    background: tokens.color.surface,\n    color: tokens.color.secondary_text,\n  },\n  danger: {\n    background: tokens.color.danger,\n    color: tokens.color.primary_text,\n  },\n};\n\nexport interface BaseButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {\n  intent?: Intent;\n}\n\nexport const BaseButton: React.FC<BaseButtonProps> = ({ intent = 'primary', style, children, ...rest }) => {\n  const palette = intentToColor[intent];\n\n  return (\n    <button\n      {...rest}\n      style={{\n        background: palette.background,\n        color: palette.color,\n        borderRadius: tokens.radius.md,\n        border: `1px solid ${tokens.color.border}`,\n        padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,\n        fontFamily: tokens.typography.font_family,\n        fontSize: tokens.typography.font_size_md,\n        fontWeight: parseInt(tokens.typography.font_weight_semibold, 10),\n        boxShadow: tokens.shadow.soft,\n        cursor: 'pointer',\n        transition: 'transform 0.2s ease, box-shadow 0.2s ease',\n        ...style,\n      }}\n      onMouseEnter={(event) => {\n        event.currentTarget.style.transform = 'translateY(-1px)';\n      }}\n      onMouseLeave={(event) => {\n        event.currentTarget.style.transform = 'translateY(0)';\n      }}\n    >\n      {children}\n    </button>\n  );\n};\n"""
    _write_if_different(base_button_path, base_button_content)

    readme_path = root / "README.md"
    readme_appendix = """\n## Orchestrator Mode\n\nThis fork now includes a chat-only orchestrator with gated steps. Use `python -m src.app.main` to launch the orchestration runtime.\n"""
    existing_readme = readme_path.read_text(encoding="utf-8") if readme_path.exists() else "# DeepCode Orchestrator\n"
    if "## Orchestrator Mode" not in existing_readme:
        _write(readme_path, existing_readme.rstrip() + "\n" + readme_appendix)

    env_example_path = root / ".env.example"
    env_example_content = """# Environment configuration for the DeepCode orchestrator\nPROJECT_NAME=your_project_name_here\nOPENAI_API_KEY=your_openai_api_key_here\n"""
    _write_if_different(env_example_path, env_example_content)

    workflow_path = root / ".github/workflows/ci.yml"
    workflow_content = textwrap.dedent(
        """\
        name: CI

        on: [push, pull_request]

        jobs:
          lint:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v3
              - name: Set up Python
                uses: actions/setup-python@v4
                with:
                  python-version: '3.11'
              - name: Install dependencies
                run: pip install -r requirements.txt
              - name: Static checks
                run: python -m compileall src
        """
    ).strip() + "\n"
    _write_if_different(workflow_path, workflow_content)

    index = load_index(project_name)
    for relative in [
        "src/backend/main.py",
        "src/frontend/src/main.tsx",
        "src/frontend/src/design-system/tokens.ts",
        "src/frontend/src/design-system/BaseButton.tsx",
        "README.md",
        ".env.example",
        ".github/workflows/ci.yml",
    ]:
        file_path = root / relative
        _record_file(index, relative, compute_sha1(file_path), "step_3")
    save_index(project_name, index)


STEP_GENERATORS = {
    "step_0": {"orchestrator": _generate_step0},
    "step_1": {"orchestrator": _generate_step1},
    "step_2": {
        "orchestrator": _generate_step2_orchestrator,
        "ui_designer": _generate_step2_ui,
    },
    "step_3": {"orchestrator": _generate_step3},
}


@dataclass
class ConversationState:
    project_name: Optional[str] = None
    display_name: Optional[str] = None
    current_step: str = "step_0"
    awaiting_reuse_confirmation: bool = False
    awaiting_step_confirmation: bool = False
    summary: Dict[str, str] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0


class ChatOrchestrator:
    """Simplified orchestrator to format responses following the output contract."""

    def __init__(self) -> None:
        self.state = ConversationState()

    async def handle(self, user_text: str) -> str:
        tokens_in = math.ceil(len(user_text) / 4) if user_text else 0
        self.state.input_tokens += tokens_in

        if not self.state.project_name:
            return await self._handle_project_name(user_text, tokens_in)

        if self.state.awaiting_reuse_confirmation:
            return await self._handle_reuse_confirmation(user_text, tokens_in)

        return await self._handle_step_flow(user_text, tokens_in)

    async def _handle_project_name(self, user_text: str, tokens_in: int) -> str:
        project_candidate = user_text.strip()
        if not project_candidate:
            return self._render_response(
                status=["⚠️ Project name required before proceeding."],
                step=get_step("step_0"),
                clean_dirty_summary=["DIRTY: session", "DIRTY: index"],
                artifacts=[],
                diffs=[],
                checks=["Missing project name prevents session initialisation — FAIL"],
                prompt="Provide a project name to begin?",
                tokens_in=tokens_in,
            )

        normalised = normalize_name(project_candidate)
        self.state.project_name = normalised
        self.state.display_name = project_candidate

        probe_task = probe_existing_project(normalised)
        index_task = prefetch_index_and_hash_sample(normalised)
        lock_task = check_lock(normalised)
        summary, prefetch, lock = await asyncio.gather(
            probe_task, index_task, lock_task
        )
        sample_hashes = prefetch.get("sample_hashes", []) if prefetch else []
        sample_preview = (
            ", ".join(
                f"{path} ({hash_value if hash_value else 'missing'})"
                for path, hash_value in sample_hashes
            )
            if sample_hashes
            else "no tracked files yet"
        )

        if summary.get("exists"):
            self.state.awaiting_reuse_confirmation = True
            self.state.summary = {
                "last_step": str(summary.get("last_step", "step_0")),
                "last_updated": str(summary.get("last_updated", "unknown")),
                "file_count": str(summary.get("file_count", 0)),
                "lock_status": lock.status,
                "hash_sample": sample_preview,
            }
            status = [
                "ℹ️ Existing project detected.",
                f"Last step: {self.state.summary['last_step']}",
                f"Lock status: {lock.status}",
                f"Sample hashes: {sample_preview}",
            ]
            clean_dirty = ["CLEAN: pending review" if lock.status != "active" else "DIRTY: locked"]
            prompt = f"Reuse existing project '{self.state.display_name}' and resume from the last saved step?"
            artifacts = [
                (path, f"hash {hash_value if hash_value else 'missing'}")
                for path, hash_value in sample_hashes
            ]
            return self._render_response(
                status=status,
                step=get_step("step_0"),
                clean_dirty_summary=clean_dirty,
                artifacts=artifacts,
                diffs=[],
                checks=[
                    "Probe existing project metadata — PASS",
                    f"Prefetch index sample — {sample_preview}",
                    f"Lock status: {lock.status.upper()} — PASS" if lock.status != "active" else "Active lock detected — FAIL",
                ],
                prompt=prompt,
                tokens_in=tokens_in,
            )

        _generate_step0(normalised)
        self.state.awaiting_step_confirmation = True
        status = [
            "✅ Project scaffolding created.",
            "Session + index initialised.",
        ]
        clean_dirty = ["CLEAN: session", "CLEAN: index"]
        prompt = get_step("step_0").gate_prompt.format(name=self.state.display_name)
        return self._render_response(
            status=status,
            step=get_step("step_0"),
            clean_dirty_summary=clean_dirty,
            artifacts=[
                (".deepcode/session.json", "Project session metadata"),
                (".deepcode/file_index.json", "Tracked files & folders"),
            ],
            diffs=["Initial session and index files created."],
            checks=[
                "Session file written — PASS",
                "File index seeded with base folders — PASS",
            ],
            prompt=prompt,
            tokens_in=tokens_in,
        )

    async def _handle_reuse_confirmation(self, user_text: str, tokens_in: int) -> str:
        decision = user_text.strip().lower()
        if decision not in {"yes", "no"}:
            prompt = f"Reuse existing project '{self.state.display_name}' and resume from the last saved step?"
            return self._render_response(
                status=["⚠️ Please reply Yes or No to confirm project reuse."],
                step=get_step("step_0"),
                clean_dirty_summary=["PENDING: awaiting confirmation"],
                artifacts=[],
                diffs=[],
                checks=["Confirmation required before proceeding — FAIL"],
                prompt=prompt,
                tokens_in=tokens_in,
            )

        if decision == "no":
            suggestion = f"Consider using '{self.state.project_name}-v2' or '{self.state.project_name}-{datetime.now().strftime('%Y%m%d-%H%M')}'."
            self.state.awaiting_reuse_confirmation = False
            self.state.project_name = None
            self.state.display_name = None
            self.state.current_step = "step_0"
            return self._render_response(
                status=["ℹ️ Reuse declined.", suggestion],
                step=get_step("step_0"),
                clean_dirty_summary=["DIRTY: awaiting new project name"],
                artifacts=[],
                diffs=[],
                checks=["Existing project left untouched — PASS"],
                prompt="Provide a new project name to begin?",
                tokens_in=tokens_in,
            )

        self.state.awaiting_reuse_confirmation = False
        session = load_session(self.state.project_name)
        self.state.current_step = session.get("current_step", "step_0")
        self.state.awaiting_step_confirmation = True
        return await self._render_step(self.state.current_step, tokens_in, resume=True)

    async def _handle_step_flow(self, user_text: str, tokens_in: int) -> str:
        if self.state.awaiting_step_confirmation:
            decision = user_text.strip().lower()
            if decision not in {"yes", "no"}:
                prompt = get_step(self.state.current_step).gate_prompt
                if "{name}" in prompt:
                    prompt = prompt.format(name=self.state.display_name)
                return self._render_response(
                    status=["⚠️ Please respond with Yes or No to advance."],
                    step=get_step(self.state.current_step),
                    clean_dirty_summary=["PENDING: awaiting confirmation"],
                    artifacts=[],
                    diffs=[],
                    checks=["Approval required to continue — FAIL"],
                    prompt=prompt,
                    tokens_in=tokens_in,
                )

            if decision == "no":
                return self._render_response(
                    status=["ℹ️ Step approval denied. Provide guidance to adjust outputs."],
                    step=get_step(self.state.current_step),
                    clean_dirty_summary=["DIRTY: awaiting revisions"],
                    artifacts=[],
                    diffs=[],
                    checks=["Awaiting user feedback — FAIL"],
                    prompt="Would you like to re-run validations after adjustments?",
                    tokens_in=tokens_in,
                )

            # Approval granted; advance to next step
            next_definition = next_step(self.state.current_step)
            if not next_definition:
                self.state.awaiting_step_confirmation = False
                return self._render_response(
                    status=["🎉 Workflow complete."],
                    step=get_step(self.state.current_step),
                    clean_dirty_summary=["CLEAN: all steps"],
                    artifacts=[],
                    diffs=[],
                    checks=["No further steps remaining — PASS"],
                    prompt="Would you like to restart?",
                    tokens_in=tokens_in,
                )

            self.state.current_step = next_definition.name
            session = load_session(self.state.project_name)
            session["current_step"] = self.state.current_step
            session["last_updated"] = _timestamp()
            save_session(self.state.project_name, session)
            return await self._render_step(self.state.current_step, tokens_in)

        # When not awaiting confirmation, regenerate outputs for current step
        return await self._render_step(self.state.current_step, tokens_in)

    async def _render_step(self, step_name: str, tokens_in: int, resume: bool = False) -> str:
        definition = get_step(step_name)
        agent_states = self._ensure_outputs(step_name)
        clean_dirty = [
            f"{state.agent.upper()}: {'CLEAN' if state.is_clean else 'DIRTY'}"
            for state in agent_states
        ]

        artifacts: List[Tuple[str, str]] = []
        diffs: List[str] = []
        for state in agent_states:
            issues = state.issues()
            if issues:
                diffs.append(f"{state.agent}: {', '.join(issues)}")
            for result in state.required_files:
                artifacts.append(
                    (
                        result.path,
                        "exists" if result.exists else "missing",
                    )
                )

        if not diffs:
            diffs.append(f"Validated {len(agent_states)} agent(s) for {definition.title}.")

        checks: List[str] = []
        for state in agent_states:
            for result in state.required_files:
                parts = ["exists" if result.exists else "missing"]
                parts.append("hash ok" if result.hash_matches else "hash mismatch")
                parts.append("sections ok" if result.sections_valid else "sections missing")
                check_status = (
                    "PASS"
                    if result.exists and result.hash_matches and result.sections_valid
                    else "FAIL"
                )
                checks.append(f"{result.path} — {', '.join(parts)} — {check_status}")

        prompt = definition.gate_prompt
        if "{name}" in prompt:
            prompt = prompt.format(name=self.state.display_name)
        self.state.awaiting_step_confirmation = True
        all_clean = all(state.is_clean for state in agent_states)
        status = [
            "✅ Existing outputs validated." if all_clean else "⚠️ Rebuilt or flagged dirty artifacts.",
            f"Step: {definition.title}",
        ]
        return self._render_response(
            status=status,
            step=definition,
            clean_dirty_summary=clean_dirty,
            artifacts=artifacts,
            diffs=diffs,
            checks=checks,
            prompt=prompt,
            tokens_in=tokens_in,
        )

    def _ensure_outputs(self, step_name: str) -> List[AgentValidationState]:
        agent_states = detect_step_state(self.state.project_name, step_name)
        for agent_state in agent_states:
            if not agent_state.is_clean:
                generator = STEP_GENERATORS.get(step_name, {}).get(agent_state.agent)
                if generator:
                    generator(self.state.project_name)
        return detect_step_state(self.state.project_name, step_name)

    def _render_response(
        self,
        *,
        status: List[str],
        step: StepDefinition,
        clean_dirty_summary: List[str],
        artifacts: List[Tuple[str, str]],
        diffs: List[str],
        checks: List[str],
        prompt: str,
        tokens_in: int,
    ) -> str:
        project_banner = self.state.project_name or "pending_project"
        ui_header = f"【{project_banner}】 — {step.title} — {' | '.join(clean_dirty_summary) if clean_dirty_summary else 'No agents'}"
        artifacts_section = "\n".join(
            f"- {path}: {purpose}" for path, purpose in artifacts
        ) or "No file changes this step."
        diffs_section = "\n".join(f"- {entry}" for entry in diffs) or "(none)"
        checks_section = "\n".join(f"- {entry}" for entry in checks) or "No checks executed."

        next_step_projection = "40k-80k tokens (~$0.80-$1.60)" if step.name in {"step_2", "step_3"} else "10k-20k tokens (~$0.20-$0.40)"

        sections = [
            "STATUS",
            "\n".join(f"- {line}" for line in status),
            "UI HEADER",
            ui_header,
            "ARTIFACTS (proposed)",
            artifacts_section,
            "DIFF PREVIEW",
            diffs_section,
            "CHECKS",
            checks_section,
            "COST",
            "",
            "NEXT STEP",
            f"Awaiting response to: {prompt}",
            "PROMPT",
            "Yes",
        ]
        response = "\n".join(sections)

        # Recompute cost metrics based on the rendered response length for a more accurate estimate.
        tokens_out_estimate = math.ceil(len(response) / 4)
        self.state.output_tokens += tokens_out_estimate
        total_tokens = tokens_in + tokens_out_estimate
        cumulative_tokens = self.state.input_tokens + self.state.output_tokens
        cost_in = tokens_in / 1_000_000 * 5.0
        cost_out = tokens_out_estimate / 1_000_000 * 15.0
        cost_total = cost_in + cost_out
        est_cost_cumulative = (
            self.state.input_tokens / 1_000_000 * 5.0
            + self.state.output_tokens / 1_000_000 * 15.0
        )

        cost_section = (
            "Token & Cost Report\n"
            f"tokens_in: {tokens_in}\n"
            f"tokens_out: {tokens_out_estimate}\n"
            f"tokens_total_this_turn: {total_tokens}\n"
            f"cumulative_tokens: {cumulative_tokens}\n"
            f"est_cost_this_turn (USD): ${cost_total:.4f}\n"
            f"est_cost_cumulative (USD): ${est_cost_cumulative:.4f}\n"
            f"next_step_cost_projection: {next_step_projection}"
        )

        sections[11] = cost_section
        response = "\n".join(sections)

        # Second pass to stabilise the estimate after embedding the cost section itself.
        recalculated_tokens_out = math.ceil(len(response) / 4)
        if recalculated_tokens_out != tokens_out_estimate:
            adjustment = recalculated_tokens_out - tokens_out_estimate
            self.state.output_tokens += adjustment
            tokens_out_estimate = recalculated_tokens_out
            total_tokens = tokens_in + tokens_out_estimate
            cumulative_tokens = self.state.input_tokens + self.state.output_tokens
            cost_out = tokens_out_estimate / 1_000_000 * 15.0
            cost_total = cost_in + cost_out
            est_cost_cumulative = (
                self.state.input_tokens / 1_000_000 * 5.0
                + self.state.output_tokens / 1_000_000 * 15.0
            )
            cost_section = (
                "Token & Cost Report\n"
                f"tokens_in: {tokens_in}\n"
                f"tokens_out: {tokens_out_estimate}\n"
                f"tokens_total_this_turn: {total_tokens}\n"
                f"cumulative_tokens: {cumulative_tokens}\n"
                f"est_cost_this_turn (USD): ${cost_total:.4f}\n"
                f"est_cost_cumulative (USD): ${est_cost_cumulative:.4f}\n"
                f"next_step_cost_projection: {next_step_projection}"
            )
            sections[11] = cost_section
            response = "\n".join(sections)

        return response


def main() -> None:
    orchestrator = ChatOrchestrator()
    print("Chat orchestrator ready. Provide a project name to begin.")
    loop = asyncio.get_event_loop()
    while True:
        try:
            user_text = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        response = loop.run_until_complete(orchestrator.handle(user_text))
        print(response)


if __name__ == "__main__":
    main()
