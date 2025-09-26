"""Session and project management utilities for the DeepCode orchestrator."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple

PROJECTS_ROOT = Path("projects")
SESSION_RELATIVE_PATH = Path(".deepcode/session.json")
INDEX_RELATIVE_PATH = Path(".deepcode/file_index.json")
LOCK_RELATIVE_PATH = Path(".deepcode/lock.json")
LOGS_DIR_RELATIVE_PATH = Path(".deepcode/logs")


@dataclass
class LockStatus:
    """Represents the lock state for a project."""

    owner: Optional[str]
    started_at: Optional[datetime]
    status: str
    is_stale: bool


def normalize_name(name: str) -> str:
    """Normalise a user provided project name to snake_case."""

    if not name:
        raise ValueError("Project name must be provided")

    normalised = "".join(ch if ch.isalnum() else "_" for ch in name.strip().lower())
    while "__" in normalised:
        normalised = normalised.replace("__", "_")
    return normalised.strip("_")


def project_root(name: str) -> Path:
    """Return the root directory for a project."""

    return PROJECTS_ROOT / normalize_name(name)


def ensure_project_root(name: str) -> Path:
    """Ensure the project root and metadata directories exist."""

    root = project_root(name)
    root.mkdir(parents=True, exist_ok=True)
    meta_root = root / ".deepcode"
    meta_root.mkdir(exist_ok=True)
    (meta_root / "logs").mkdir(exist_ok=True)
    return root


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return default


def load_session(name: str) -> Dict[str, Any]:
    """Load the project session metadata."""

    ensure_project_root(name)
    path = project_root(name) / SESSION_RELATIVE_PATH
    return _load_json(path, {})


def save_session(name: str, payload: Mapping[str, Any]) -> None:
    """Persist the session metadata."""

    root = ensure_project_root(name)
    path = root / SESSION_RELATIVE_PATH
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def load_index(name: str) -> Dict[str, Any]:
    """Load the file index for a project."""

    ensure_project_root(name)
    path = project_root(name) / INDEX_RELATIVE_PATH
    return _load_json(path, {"files": {}})


def save_index(name: str, index: Mapping[str, Any]) -> None:
    """Persist the file index for a project."""

    root = ensure_project_root(name)
    path = root / INDEX_RELATIVE_PATH
    with path.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, sort_keys=True)


def compute_sha1(path: Path) -> str:
    """Compute the SHA1 hash of a file."""

    sha1 = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            sha1.update(chunk)
    return sha1.hexdigest()


def index_set(index: MutableMapping[str, Any], path: Path, metadata: Mapping[str, Any]) -> None:
    """Update the file index entry for *path*."""

    files: MutableMapping[str, Any] = index.setdefault("files", {})  # type: ignore
    files[str(path)] = dict(metadata)


async def project_exists(name: str) -> bool:
    """Return *True* if the project root exists."""

    return project_root(name).exists()


async def probe_existing_project(name: str) -> Dict[str, Any]:
    """Collect a high level summary about a project if it exists."""

    root = project_root(name)
    if not root.exists():
        return {"exists": False}

    session = load_session(name)
    index = load_index(name)
    files = index.get("files", {})
    last_step = session.get("current_step")
    last_updated = session.get("last_updated")
    summary = {
        "exists": True,
        "last_step": last_step,
        "last_updated": last_updated,
        "file_count": len(files),
    }
    return summary


async def prefetch_index_and_hash_sample(name: str, sample_size: int = 3) -> Dict[str, Any]:
    """Load the index and compute hashes for a small sample of files."""

    index = load_index(name)
    files: Mapping[str, Any] = index.get("files", {})
    sample: List[Tuple[str, Optional[str]]] = []
    for path_str in list(files.keys())[:sample_size]:
        path = project_root(name) / path_str
        if path.exists():
            try:
                file_hash = compute_sha1(path)
            except OSError:
                file_hash = None
        else:
            file_hash = None
        sample.append((path_str, file_hash))
    return {"index": index, "sample_hashes": sample}


def lock_path(name: str) -> Path:
    """Return the lock file path for the project."""

    return project_root(name) / LOCK_RELATIVE_PATH


def _parse_lock_payload(payload: Mapping[str, Any], ttl_minutes: int) -> LockStatus:
    owner = payload.get("owner")
    started_at_raw = payload.get("started_at")
    status = payload.get("status", "unknown")
    started_at = None
    is_stale = True
    if isinstance(started_at_raw, str):
        try:
            started_at = datetime.fromisoformat(started_at_raw)
            age = datetime.now(timezone.utc) - started_at
            is_stale = age > timedelta(minutes=ttl_minutes)
        except ValueError:
            started_at = None
            is_stale = True
    return LockStatus(owner=owner, started_at=started_at, status=status, is_stale=is_stale)


async def check_lock(name: str, ttl_minutes: int = 30) -> LockStatus:
    """Inspect the existing lock file for a project."""

    path = lock_path(name)
    if not path.exists():
        return LockStatus(owner=None, started_at=None, status="missing", is_stale=True)

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return LockStatus(owner=None, started_at=None, status="corrupt", is_stale=True)

    lock = _parse_lock_payload(payload, ttl_minutes)
    if lock.status == "active" and lock.is_stale:
        payload["status"] = "stale"
        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError:
            pass
        lock.status = "stale"
    return lock


async def acquire_lock(name: str, owner: str = "orchestrator") -> LockStatus:
    """Acquire or refresh the lock for a project."""

    root = ensure_project_root(name)
    path = root / LOCK_RELATIVE_PATH
    payload = {
        "owner": owner,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return _parse_lock_payload(payload, ttl_minutes=0)


async def release_lock(name: str) -> None:
    """Release the project lock."""

    path = lock_path(name)
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        payload = {}

    payload.update(
        {
            "status": "released",
            "released_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except OSError:
        path.unlink(missing_ok=True)
