"""Locate a graph explicitly, without discovering any parent workspace."""

import os
import re
from pathlib import Path

import yaml

KNOWLEDGE_ROOT = Path(os.environ.get("KG_ROOT", "knowledge")).expanduser().resolve()
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*")


def safe_path(root: Path, atom_id: str) -> Path:
    """Resolve an ID inside its store, rejecting traversal and escaping symlinks."""
    if not isinstance(atom_id, str) or not _ID.fullmatch(atom_id):
        raise ValueError(f"Invalid atom id: {atom_id!r}")
    base = root.resolve()
    path = (base / f"{atom_id}.md").resolve()
    if not path.is_relative_to(base):
        raise ValueError("Atom path escapes its knowledge store")
    return path


def approval_settings() -> dict:
    """Optional owner precedence and fallback; neither is assumed by default."""
    path = KNOWLEDGE_ROOT / "_config.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    data = data or {}
    if not isinstance(data, dict):
        raise ValueError("_config.yaml must be a mapping")
    priority = data.get("owner_priority", [])
    fallback = data.get("fallback_owner")
    if not isinstance(priority, list) or not all(
        isinstance(n, str) and n.strip() for n in priority
    ):
        raise ValueError("owner_priority must be a list of nonempty names")
    if fallback is not None and (not isinstance(fallback, str) or not fallback.strip()):
        raise ValueError("fallback_owner must be a nonempty name or null")
    return {"owner_priority": priority, "fallback_owner": fallback}
