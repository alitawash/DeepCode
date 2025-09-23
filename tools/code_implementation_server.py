#!/usr/bin/env python3
"""
Code Implementation MCP Server (hardened)

- Atomic file writes (no 0-byte placeholders)
- Reject empty/None content unless allow_empty=True
- Helpers to list/delete zero-byte files
"""

import os
import subprocess
import json
import sys
import io
from pathlib import Path
import re
from typing import Dict, Any, List, Optional
import tempfile
import shutil
import logging
from datetime import datetime
from contextlib import suppress

# Ensure UTF-8 stdout/stderr
if sys.stdout.encoding != "utf-8":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
            sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding="utf-8")
    except Exception as e:
        print(f"Warning: Could not set UTF-8 encoding: {e}")

# MCP
from mcp.server.fastmcp import FastMCP

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Server
mcp = FastMCP("code-implementation-server")

# Globals
WORKSPACE_DIR: Optional[Path] = None
OPERATION_HISTORY: List[Dict[str, Any]] = []
CURRENT_FILES: Dict[str, Dict[str, Any]] = {}


# ---------- Utilities ----------

def log_operation(action: str, details: Dict[str, Any]):
    OPERATION_HISTORY.append(
        {"timestamp": datetime.now().isoformat(), "action": action, "details": details}
    )

def initialize_workspace(workspace_dir: str = None):
    global WORKSPACE_DIR
    if workspace_dir is None:
        WORKSPACE_DIR = Path.cwd() / "generate_code"
    else:
        WORKSPACE_DIR = Path(workspace_dir).resolve()
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Workspace initialized: {WORKSPACE_DIR}")

def ensure_workspace_exists():
    global WORKSPACE_DIR
    if WORKSPACE_DIR is None:
        initialize_workspace()
    if not WORKSPACE_DIR.exists():
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Workspace directory created: {WORKSPACE_DIR}")

def validate_path(path: str) -> Path:
    if WORKSPACE_DIR is None:
        initialize_workspace()
    full_path = (WORKSPACE_DIR / path).resolve()
    if not str(full_path).startswith(str(WORKSPACE_DIR)):
        raise ValueError(f"Path {path} is outside workspace scope")
    return full_path

def atomic_write_text(path: Path, text: str, encoding: str = "utf-8"):
    """Write text atomically to avoid 0-byte or torn writes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with io.open(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        with suppress(FileNotFoundError):
            os.remove(tmp)
        raise

def _json_ok(**kwargs) -> str:
    return json.dumps({"status": "success", **kwargs}, ensure_ascii=False, indent=2)

def _json_err(message: str, **kwargs) -> str:
    return json.dumps({"status": "error", "message": message, **kwargs}, ensure_ascii=False, indent=2)


# ==================== File Operation Tools ====================

@mcp.tool()
async def read_file(file_path: str, start_line: int = None, end_line: int = None) -> str:
    try:
        full_path = validate_path(file_path)
        if not full_path.exists():
            log_operation("read_file_error", {"file_path": file_path, "error": "file_not_found"})
            return _json_err(f"File does not exist: {file_path}", file_path=file_path)

        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if start_line is not None or end_line is not None:
            start_idx = (start_line - 1) if start_line else 0
            end_idx = end_line if end_line else len(lines)
            lines = lines[start_idx:end_idx]

        content = "".join(lines)
        log_operation("read_file", {"file_path": file_path, "start_line": start_line, "end_line": end_line, "lines_read": len(lines)})

        return _json_ok(
            content=content,
            file_path=file_path,
            total_lines=len(lines),
            size_bytes=len(content.encode("utf-8")),
        )
    except Exception as e:
        log_operation("read_file_error", {"file_path": file_path, "error": str(e)})
        return _json_err(f"Failed to read file: {str(e)}", file_path=file_path)


@mcp.tool()
async def read_multiple_files(file_requests: str, max_files: int = 5) -> str:
    try:
        try:
            requests_data = json.loads(file_requests)
        except json.JSONDecodeError as e:
            return _json_err(f"Invalid JSON format for file_requests: {str(e)}", operation_type="multi_file", timestamp=datetime.now().isoformat())

        if isinstance(requests_data, list):
            normalized = {fp: {} for fp in requests_data}
        elif isinstance(requests_data, dict):
            normalized = requests_data
        else:
            return _json_err("file_requests must be a JSON object or array", operation_type="multi_file", timestamp=datetime.now().isoformat())

        if len(normalized) == 0:
            return _json_err("No files provided for reading", operation_type="multi_file", timestamp=datetime.now().isoformat())
        if len(normalized) > max_files:
            return _json_err(f"Too many files provided ({len(normalized)}), maximum is {max_files}", operation_type="multi_file", timestamp=datetime.now().isoformat())

        results = {
            "status": "success",
            "message": f"Successfully processed {len(normalized)} files",
            "operation_type": "multi_file",
            "timestamp": datetime.now().isoformat(),
            "files_processed": len(normalized),
            "files": {},
            "summary": {"successful": 0, "failed": 0, "total_size_bytes": 0, "total_lines": 0, "files_not_found": 0},
        }

        for file_path, options in normalized.items():
            try:
                full_path = validate_path(file_path)
                start_line = options.get("start_line")
                end_line = options.get("end_line")

                if not full_path.exists():
                    results["files"][file_path] = {"status": "error", "message": f"File does not exist: {file_path}", "file_path": file_path, "content": "", "total_lines": 0, "size_bytes": 0, "start_line": start_line, "end_line": end_line}
                    results["summary"]["failed"] += 1
                    results["summary"]["files_not_found"] += 1
                    continue

                with open(full_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                original_lines = len(lines)
                if start_line is not None or end_line is not None:
                    start_idx = (start_line - 1) if start_line else 0
                    end_idx = end_line if end_line else len(lines)
                    lines = lines[start_idx:end_idx]

                content = "".join(lines)
                size_bytes = len(content.encode("utf-8"))
                lines_count = len(lines)

                results["files"][file_path] = {"status": "success", "message": f"File read successfully: {file_path}", "file_path": file_path, "content": content, "total_lines": lines_count, "original_total_lines": original_lines, "size_bytes": size_bytes, "start_line": start_line, "end_line": end_line, "line_range_applied": start_line is not None or end_line is not None}

                results["summary"]["successful"] += 1
                results["summary"]["total_size_bytes"] += size_bytes
                results["summary"]["total_lines"] += lines_count

                log_operation("read_file_multi", {"file_path": file_path, "start_line": start_line, "end_line": end_line, "lines_read": lines_count, "size_bytes": size_bytes, "batch_operation": True})

            except Exception as file_error:
                results["files"][file_path] = {"status": "error", "message": f"Failed to read file: {str(file_error)}", "file_path": file_path, "content": "", "total_lines": 0, "size_bytes": 0}
                results["summary"]["failed"] += 1
                log_operation("read_file_multi_error", {"file_path": file_path, "error": str(file_error), "batch_operation": True})

        if results["summary"]["failed"] > 0:
            results["status"] = "partial_success" if results["summary"]["successful"] > 0 else "failed"
            s = results["summary"]
            results["message"] = f"Read {s['successful']} files successfully, {s['failed']} failed"

        log_operation("read_multiple_files", {"files_count": len(normalized), "successful": results["summary"]["successful"], "failed": results["summary"]["failed"], "total_size_bytes": results["summary"]["total_size_bytes"], "status": results["status"]})
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        log_operation("read_multiple_files_error", {"error": str(e)})
        return _json_err(f"Failed to read multiple files: {str(e)}", operation_type="multi_file", timestamp=datetime.now().isoformat(), files_processed=0)


@mcp.tool()
async def write_file(
    file_path: str,
    content: Optional[str],
    create_dirs: bool = True,
    create_backup: bool = False,
    allow_empty: bool = False,
) -> str:
    """
    Write content to file (atomic). Rejects None/empty unless allow_empty=True.
    """
    try:
        if file_path is None:
            log_operation("write_file_error", {"error": "missing file_path"})
            return _json_err("Missing file path")

        full_path = validate_path(file_path)

        # Validate content
        if content is None:
            log_operation("write_file_error", {"file_path": file_path, "error": "content is None"})
            return _json_err("Content is None", file_path=file_path)
        if (content == "" or len(content.encode("utf-8")) == 0) and not allow_empty:
            log_operation("write_file_error", {"file_path": file_path, "error": "empty content rejected"})
            return _json_err("Empty content rejected (set allow_empty=True to permit)", file_path=file_path)

        # Create dirs
        if create_dirs:
            full_path.parent.mkdir(parents=True, exist_ok=True)

        # Backup if requested
        backup_created = False
        if full_path.exists() and create_backup:
            backup_path = full_path.with_suffix(full_path.suffix + ".backup")
            shutil.copy2(full_path, backup_path)
            backup_created = True

        # Atomic write
        atomic_write_text(full_path, content)

        # Track
        CURRENT_FILES[file_path] = {
            "last_modified": datetime.now().isoformat(),
            "size_bytes": len(content.encode("utf-8")),
            "lines": content.count("\n") + 1 if content else 0,
        }

        log_operation("write_file", {"file_path": file_path, "size_bytes": len(content.encode("utf-8")), "lines": CURRENT_FILES[file_path]["lines"], "backup_created": backup_created})
        return _json_ok(message=f"File written successfully: {file_path}", file_path=file_path, size_bytes=len(content.encode("utf-8")), lines_written=CURRENT_FILES[file_path]["lines"], backup_created=backup_created)

    except Exception as e:
        log_operation("write_file_error", {"file_path": file_path, "error": str(e)})
        return _json_err(f"Failed to write file: {str(e)}", file_path=file_path)


@mcp.tool()
async def write_multiple_files(
    file_implementations: str,
    create_dirs: bool = True,
    create_backup: bool = False,
    max_files: int = 5,
    allow_empty: bool = False,
) -> str:
    """
    Batch write (atomic). Rejects empty/None entries unless allow_empty=True.
    """
    try:
        try:
            files_dict = json.loads(file_implementations)
        except json.JSONDecodeError as e:
            return _json_err(f"Invalid JSON format for file_implementations: {str(e)}", operation_type="multi_file", timestamp=datetime.now().isoformat())

        if not isinstance(files_dict, dict):
            return _json_err("file_implementations must be a JSON object mapping file paths to content", operation_type="multi_file", timestamp=datetime.now().isoformat())
        if len(files_dict) == 0:
            return _json_err("No files provided for writing", operation_type="multi_file", timestamp=datetime.now().isoformat())
        if len(files_dict) > max_files:
            return _json_err(f"Too many files provided ({len(files_dict)}), maximum is {max_files}", operation_type="multi_file", timestamp=datetime.now().isoformat())

        results = {
            "status": "success",
            "message": f"Successfully processed {len(files_dict)} files",
            "operation_type": "multi_file",
            "timestamp": datetime.now().isoformat(),
            "files_processed": len(files_dict),
            "files": {},
            "summary": {"successful": 0, "failed": 0, "total_size_bytes": 0, "total_lines": 0, "backups_created": 0},
        }

        for file_path, content in files_dict.items():
            try:
                full_path = validate_path(file_path)

                if content is None:
                    raise ValueError("content is None")
                if (content == "" or len(content.encode("utf-8")) == 0) and not allow_empty:
                    raise ValueError("empty content rejected (set allow_empty=True to permit)")

                if create_dirs:
                    full_path.parent.mkdir(parents=True, exist_ok=True)

                backup_created = False
                if full_path.exists() and create_backup:
                    backup_path = full_path.with_suffix(full_path.suffix + ".backup")
                    shutil.copy2(full_path, backup_path)
                    backup_created = True
                    results["summary"]["backups_created"] += 1

                atomic_write_text(full_path, content)

                size_bytes = len(content.encode("utf-8"))
                lines_count = content.count("\n") + 1 if content else 0

                CURRENT_FILES[file_path] = {"last_modified": datetime.now().isoformat(), "size_bytes": size_bytes, "lines": lines_count}
                results["files"][file_path] = {"status": "success", "message": f"File written successfully: {file_path}", "size_bytes": size_bytes, "lines_written": lines_count, "backup_created": backup_created}

                results["summary"]["successful"] += 1
                results["summary"]["total_size_bytes"] += size_bytes
                results["summary"]["total_lines"] += lines_count

                log_operation("write_file_multi", {"file_path": file_path, "size_bytes": size_bytes, "lines": lines_count, "backup_created": backup_created, "batch_operation": True})

            except Exception as file_error:
                results["files"][file_path] = {"status": "error", "message": f"Failed to write file: {str(file_error)}", "size_bytes": 0, "lines_written": 0, "backup_created": False}
                results["summary"]["failed"] += 1
                log_operation("write_file_multi_error", {"file_path": file_path, "error": str(file_error), "batch_operation": True})

        if results["summary"]["failed"] > 0:
            results["status"] = "partial_success" if results["summary"]["successful"] > 0 else "failed"
            s = results["summary"]
            results["message"] = f"Processed {s['successful']} files successfully, {s['failed']} failed"

        log_operation("write_multiple_files", {"files_count": len(files_dict), "successful": results["summary"]["successful"], "failed": results["summary"]["failed"], "total_size_bytes": results["summary"]["total_size_bytes"], "status": results["status"]})
        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        log_operation("write_multiple_files_error", {"error": str(e)})
        return _json_err(f"Failed to write multiple files: {str(e)}", operation_type="multi_file", timestamp=datetime.now().isoformat(), files_processed=0)


# ==================== Code Execution Tools ====================

@mcp.tool()
async def execute_python(code: str, timeout: int = 30) -> str:
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_file = f.name
        try:
            ensure_workspace_exists()
            result = subprocess.run(
                [sys.executable, temp_file],
                cwd=WORKSPACE_DIR,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
            )
            log_operation("execute_python", {"return_code": result.returncode, "stdout_length": len(result.stdout), "stderr_length": len(result.stderr)})
            return json.dumps(
                {
                    "status": "success" if result.returncode == 0 else "error",
                    "message": "Python code execution successful" if result.returncode == 0 else "Python code execution failed",
                    "return_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timeout": timeout,
                },
                ensure_ascii=False,
                indent=2,
            )
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temp_file)
    except subprocess.TimeoutExpired:
        log_operation("execute_python_timeout", {"timeout": timeout})
        return _json_err(f"Python code execution timeout ({timeout} seconds)", timeout=timeout)
    except Exception as e:
        log_operation("execute_python_error", {"error": str(e)})
        return _json_err(f"Python code execution failed: {str(e)}")


@mcp.tool()
async def execute_bash(command: str, timeout: int = 30) -> str:
    try:
        dangerous_commands = ["rm -rf", "sudo", "chmod 777", "mkfs", "dd if="]
        if any(d in command.lower() for d in dangerous_commands):
            log_operation("execute_bash_blocked", {"command": command, "reason": "dangerous_command"})
            return _json_err(f"Dangerous command execution prohibited: {command}", command=command)

        ensure_workspace_exists()
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
        log_operation("execute_bash", {"command": command, "return_code": result.returncode, "stdout_length": len(result.stdout), "stderr_length": len(result.stderr)})
        return json.dumps(
            {
                "status": "success" if result.returncode == 0 else "error",
                "message": "Bash command execution successful" if result.returncode == 0 else "Bash command execution failed",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command,
                "timeout": timeout,
            },
            ensure_ascii=False,
            indent=2,
        )
    except subprocess.TimeoutExpired:
        log_operation("execute_bash_timeout", {"command": command, "timeout": timeout})
        return _json_err(f"Bash command execution timeout ({timeout} seconds)", command=command, timeout=timeout)
    except Exception as e:
        log_operation("execute_bash_error", {"command": command, "error": str(e)})
        return _json_err(f"Failed to execute bash command: {str(e)}", command=command)


# ==================== Code Memory ====================

@mcp.tool()
async def read_code_mem(file_paths: List[str]) -> str:
    try:
        if not file_paths or not isinstance(file_paths, list):
            log_operation("read_code_mem_error", {"error": "missing_or_invalid_file_paths"})
            return _json_err("file_paths parameter is required and must be a list")

        unique_file_paths = list(dict.fromkeys(file_paths))
        ensure_workspace_exists()
        current_path = Path(WORKSPACE_DIR)
        summary_file_path = current_path.parent / "implement_code_summary.md"

        if not summary_file_path.exists():
            log_operation("read_code_mem", {"file_paths": unique_file_paths, "status": "no_summary_file"})
            return json.dumps(
                {"status": "no_summary", "file_paths": unique_file_paths, "message": "No summary file found.", "results": []},
                ensure_ascii=False,
                indent=2,
            )

        with open(summary_file_path, "r", encoding="utf-8") as f:
            summary_content = f.read()

        if not summary_content.strip():
            log_operation("read_code_mem", {"file_paths": unique_file_paths, "status": "empty_summary"})
            return json.dumps(
                {"status": "no_summary", "file_paths": unique_file_paths, "message": "Summary file is empty.", "results": []},
                ensure_ascii=False,
                indent=2,
            )

        results = []
        summaries_found = 0
        for fp in unique_file_paths:
            section = _extract_file_section_from_summary(summary_content, fp)
            if section:
                results.append({"file_path": fp, "status": "summary_found", "summary_content": section, "message": f"Summary information found for {fp}"})
                summaries_found += 1
            else:
                results.append({"file_path": fp, "status": "no_summary", "summary_content": None, "message": f"No summary found for {fp}"})

        overall = "all_summaries_found" if summaries_found == len(unique_file_paths) else ("partial_summaries_found" if summaries_found > 0 else "no_summaries_found")
        log_operation("read_code_mem", {"file_paths": unique_file_paths, "status": overall, "total_requested": len(unique_file_paths), "summaries_found": summaries_found})
        return json.dumps(
            {"status": overall, "file_paths": unique_file_paths, "total_requested": len(unique_file_paths), "summaries_found": summaries_found, "message": f"Found summaries for {summaries_found}/{len(unique_file_paths)} files", "results": results},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        log_operation("read_code_mem_error", {"file_paths": file_paths, "error": str(e)})
        return _json_err(f"Failed to check code memory: {str(e)}", file_paths=file_paths if isinstance(file_paths, list) else [str(file_paths)], results=[])


def _extract_file_section_from_summary(summary_content: str, target_file_path: str) -> Optional[str]:
    normalized_target = _normalize_file_path(target_file_path)
    section_pattern = r"={80}\s*\n## IMPLEMENTATION File ([^;]+); ROUND \d+\s*\n={80}(.*?)(?=\n={80}|\Z)"
    matches = re.findall(section_pattern, summary_content, re.DOTALL)

    for file_path_in_summary, section_content in matches:
        file_path_in_summary = file_path_in_summary.strip()
        section_content = section_content.strip()
        normalized_summary_path = _normalize_file_path(file_path_in_summary)
        if _paths_match(normalized_target, normalized_summary_path, target_file_path, file_path_in_summary):
            return (
                "================================================================================\n"
                f"## IMPLEMENTATION File {file_path_in_summary}; ROUND [X]\n"
                "================================================================================\n\n"
                f"{section_content}\n\n---\n*Extracted from implement_code_summary.md*"
            )
    return _extract_file_section_alternative(summary_content, target_file_path)

def _normalize_file_path(file_path: str) -> str:
    normalized = file_path.strip("/").lower().replace("\\", "/")
    for prefix in ["src/", "./src/", "./", "core/", "lib/", "main/"]:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    return normalized

def _paths_match(normalized_target: str, normalized_summary: str, original_target: str, original_summary: str) -> bool:
    if normalized_target == normalized_summary:
        return True
    if os.path.basename(original_target) == os.path.basename(original_summary) and len(os.path.basename(original_target)) > 4:
        return True
    def _rm_pref(p: str) -> str:
        for pf in ["src/", "core/", "./", "lib/", "main/"]:
            if p.startswith(pf): p = p[len(pf):]
        return p
    if _rm_pref(normalized_target) == _rm_pref(normalized_summary):
        return True
    if normalized_target.endswith(normalized_summary) or normalized_summary.endswith(normalized_target):
        return True
    if (len(normalized_target) > 10 and normalized_target in normalized_summary) or (len(normalized_summary) > 10 and normalized_summary in normalized_target):
        return True
    return False

def _extract_file_section_alternative(summary_content: str, target_file_path: str) -> Optional[str]:
    target_basename = os.path.basename(target_file_path)
    sections = summary_content.split("=" * 80)
    for i, section in enumerate(sections):
        if "## IMPLEMENTATION File" in section:
            lines = section.strip().split("\n")
            for line in lines:
                if "## IMPLEMENTATION File" in line:
                    try:
                        file_part = line.split("File ")[1].split("; ROUND")[0].strip()
                        if (_normalize_file_path(target_file_path) == _normalize_file_path(file_part)
                            or target_basename == os.path.basename(file_part)
                            or target_file_path in file_part
                            or file_part.endswith(target_file_path)):
                            content_section = sections[i + 1].strip() if i + 1 < len(sections) else ""
                            return (
                                "================================================================================\n"
                                f"## IMPLEMENTATION File {file_part}\n"
                                "================================================================================\n\n"
                                f"{content_section}\n\n---\n*Extracted from implement_code_summary.md using alternative method*"
                            )
                    except (IndexError, AttributeError):
                        continue
    return None


# ==================== Code Search ====================

@mcp.tool()
async def search_code(pattern: str, file_pattern: str = "*.json", use_regex: bool = False, search_directory: str = None) -> str:
    try:
        if search_directory:
            search_path = Path(search_directory) if os.path.isabs(search_directory) else (Path.cwd() / search_directory)
        else:
            ensure_workspace_exists()
            search_path = WORKSPACE_DIR

        if not search_path.exists():
            return _json_err(f"Search directory does not exist: {search_path}", pattern=pattern)

        import glob
        file_paths = glob.glob(str(search_path / "**" / file_pattern), recursive=True)

        matches = []
        total_files_searched = 0
        for file_path in file_paths:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                total_files_searched += 1
                relative_path = os.path.relpath(file_path, search_path)
                for line_num, line in enumerate(lines, 1):
                    if use_regex:
                        if re.search(pattern, line):
                            matches.append({"file": relative_path, "line_number": line_num, "line_content": line.strip(), "match_type": "regex"})
                    else:
                        if pattern.lower() in line.lower():
                            matches.append({"file": relative_path, "line_number": line_num, "line_content": line.strip(), "match_type": "substring"})
            except Exception as e:
                logger.warning(f"Error searching file {file_path}: {e}")
                continue

        result = {
            "status": "success",
            "pattern": pattern,
            "file_pattern": file_pattern,
            "use_regex": use_regex,
            "search_directory": str(search_path),
            "total_matches": len(matches),
            "total_files_searched": total_files_searched,
            "matches": matches[:50],
        }
        if len(matches) > 50:
            result["note"] = f"Showing first 50 matches, total {len(matches)}"
        log_operation("search_code", {"pattern": pattern, "file_pattern": file_pattern, "use_regex": use_regex, "search_directory": str(search_path), "total_matches": len(matches), "files_searched": total_files_searched})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        log_operation("search_code_error", {"pattern": pattern, "error": str(e)})
        return _json_err(f"Code search failed: {str(e)}", pattern=pattern)


# ==================== File Structure ====================

@mcp.tool()
async def get_file_structure(directory: str = ".", max_depth: int = 5) -> str:
    try:
        ensure_workspace_exists()
        target_dir = WORKSPACE_DIR if directory == "." else validate_path(directory)
        if not target_dir.exists():
            return _json_err(f"Directory does not exist: {directory}")

        def scan_directory(path: Path, current_depth: int = 0) -> Dict[str, Any]:
            if current_depth >= max_depth:
                return {"type": "directory", "name": path.name, "truncated": True}
            items = []
            try:
                for item in sorted(path.iterdir()):
                    relative_path = os.path.relpath(item, WORKSPACE_DIR)
                    if item.is_file():
                        items.append({"type": "file", "name": item.name, "path": relative_path, "size_bytes": item.stat().st_size, "extension": item.suffix})
                    elif item.is_dir() and not item.name.startswith("."):
                        dir_info = scan_directory(item, current_depth + 1)
                        dir_info["path"] = relative_path
                        items.append(dir_info)
            except PermissionError:
                pass
            return {"type": "directory", "name": path.name, "items": items, "item_count": len(items)}

        structure = scan_directory(target_dir)

        def count_items(node):
            if node["type"] == "file":
                return {"files": 1, "directories": 0}
            counts = {"files": 0, "directories": 1}
            for item in node.get("items", []):
                c = count_items(item)
                counts["files"] += c["files"]
                counts["directories"] += c["directories"]
            return counts

        counts = count_items(structure)
        log_operation("get_file_structure", {"directory": directory, "max_depth": max_depth, "total_files": counts["files"], "total_directories": counts["directories"] - 1})
        return _json_ok(directory=directory, max_depth=max_depth, structure=structure, summary={"total_files": counts["files"], "total_directories": counts["directories"] - 1})
    except Exception as e:
        log_operation("get_file_structure_error", {"directory": directory, "error": str(e)})
        return _json_err(f"Failed to get file structure: {str(e)}", directory=directory)


# ==================== Workspace Management ====================

@mcp.tool()
async def set_workspace(workspace_path: str) -> str:
    try:
        global WORKSPACE_DIR
        new_workspace = Path(workspace_path).resolve()
        new_workspace.mkdir(parents=True, exist_ok=True)
        old_workspace = WORKSPACE_DIR
        WORKSPACE_DIR = new_workspace
        logger.info(f"New Workspace: {WORKSPACE_DIR}")
        log_operation("set_workspace", {"old_workspace": str(old_workspace) if old_workspace else None, "new_workspace": str(WORKSPACE_DIR), "workspace_alignment": "plan_file_parent/generate_code"})
        return _json_ok(message=f"Workspace setup successful: {workspace_path}", new_workspace=str(WORKSPACE_DIR))
    except Exception as e:
        log_operation("set_workspace_error", {"workspace_path": workspace_path, "error": str(e)})
        return _json_err(f"Failed to set workspace: {str(e)}", workspace_path=workspace_path)


@mcp.tool()
async def get_operation_history(last_n: int = 10) -> str:
    try:
        recent_history = OPERATION_HISTORY[-last_n:] if last_n > 0 else OPERATION_HISTORY
        return _json_ok(total_operations=len(OPERATION_HISTORY), returned_operations=len(recent_history), workspace=str(WORKSPACE_DIR) if WORKSPACE_DIR else None, history=recent_history)
    except Exception as e:
        return _json_err(f"Failed to get operation history: {str(e)}")


# ==================== New: Zero-byte Helpers ====================

@mcp.tool()
async def list_empty_files(root: str = ".") -> str:
    """List zero-byte files under root (relative to workspace)."""
    try:
        ensure_workspace_exists()
        base = WORKSPACE_DIR if root == "." else validate_path(root)
        empties = []
        for p in base.rglob("*"):
            if p.is_file() and p.stat().st_size == 0:
                empties.append(str(p.relative_to(WORKSPACE_DIR)))
        log_operation("list_empty_files", {"root": str(base), "count": len(empties)})
        return _json_ok(root=str(base), count=len(empties), files=empties)
    except Exception as e:
        log_operation("list_empty_files_error", {"root": root, "error": str(e)})
        return _json_err(f"Failed to list empty files: {str(e)}", root=root)

@mcp.tool()
async def delete_empty_files(root: str = ".", confirm: bool = False) -> str:
    """Delete zero-byte files (safe cleanup)."""
    try:
        if not confirm:
            return _json_err("Set confirm=True to actually delete empty files")
        ensure_workspace_exists()
        base = WORKSPACE_DIR if root == "." else validate_path(root)
        deleted = []
        for p in base.rglob("*"):
            if p.is_file() and p.stat().st_size == 0:
                rel = str(p.relative_to(WORKSPACE_DIR))
                with suppress(Exception):
                    p.unlink()
                    deleted.append(rel)
        log_operation("delete_empty_files", {"root": str(base), "deleted": len(deleted)})
        return _json_ok(root=str(base), deleted_count=len(deleted), files=deleted)
    except Exception as e:
        log_operation("delete_empty_files_error", {"root": root, "error": str(e)})
        return _json_err(f"Failed to delete empty files: {str(e)}", root=root)


# ==================== Server Initialization ====================

def main():
    print("🚀 Code Implementation MCP Server (hardened)")
    print("Available tools:")
    print("  • read_code_mem")
    print("  • read_file / read_multiple_files")
    print("  • write_file / write_multiple_files")
    print("  • list_empty_files / delete_empty_files")
    print("  • execute_python / execute_bash")
    print("  • search_code")
    print("  • get_file_structure")
    print("  • set_workspace")
    print("  • get_operation_history")
    print("🔧 Server starting...")

    initialize_workspace()
    mcp.run()

if __name__ == "__main__":
    main()
