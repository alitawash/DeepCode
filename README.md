# DeepCode (Open Agentic Coding Fork)

This repository is a lightweight fork of [HKUDS/DeepCode](https://github.com/HKUDS/DeepCode) that keeps the pieces we actively extend for larger, self-hosted code generation projects. It removes the heavy marketing material from the original README and focuses on the source changes that matter for running the stack locally.

## What changed in this fork
- **Editable multi-agent workflows** live in [`workflows/`](workflows) so you can tune orchestration logic, indexing steps, and code synthesis without closed-source services.
- **Streamlit launcher** `deepcode.py` checks runtime dependencies and boots the web UI served from [`ui/`](ui) on port 8502 for quick visual runs.
- **Fully open CLI pipeline** in [`cli/`](cli) exposes paper-to-code, chat, and file processing flows with segmentation controls for handling larger inputs.
- **Tooling and infrastructure scripts** under [`tools/`](tools) and [`utils/`](utils) provide local document conversion, repository indexing, and command execution helpers required by the workflows.

## Quick start
1. **Prepare the virtual environment**:
   ```bash
   # kill aliases that force /usr/bin/python3 and pip3 (3.9)
   unalias python 2>/dev/null
   unalias pip 2>/dev/null
   hash -r

   # create the Python 3.11 virtual environment if it doesn't exist yet
   python3.11 -m venv ~/.venvs/deepcode311

   # activate the DeepCode Python environment
   source ~/.venvs/deepcode311/bin/activate

   # install dependencies inside the environment
   pip install -r requirements.txt
   ```
2. **Configure providers**: update `mcp_agent.config.yaml` with your API keys or local model endpoints.
3. **Run the UI**: `python deepcode.py` launches the Streamlit dashboard at `http://localhost:8502`.
4. **Run the CLI**: `python -m cli.main_cli --help` lists the flags for direct paper, URL, or chat based code generation pipelines.

## Repository essentials
- Core package metadata lives in [`__init__.py`](__init__.py) and `setup.py`, enabling `pip install -e .` for development.
- Prompts and configuration helpers are exposed in [`prompts/`](prompts) and [`config/`](config) for simple customization.
- Workflow-friendly licenses and contribution defaults remain MIT via [`LICENSE`](LICENSE).

## Orchestrator mode
This fork introduces a chat-only orchestrator that manages step-gated project execution.

- Launch via `python -m src.app.main` and provide a project name through chat input.
- Outputs are stored under `projects/<project_name>/` with `.deepcode` metadata for sessions and file indexing.
- UI tokens live in `ui/design_tokens.json` and are consumed by the frontend scaffold (`src/frontend/src/design-system`).
- Each step exposes Clean/Dirty status chips and cost telemetry following the eight-section output contract.

## License
This project continues under the MIT License.
