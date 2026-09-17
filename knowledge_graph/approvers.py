"""Resolve capture validators from explicit requirements or source ownership."""

from knowledge_graph import config
from knowledge_graph.models import Unit


def canonical_name(name: str) -> str:
    return name.strip().casefold() if isinstance(name, str) else ""


def principal_is_required(principal: str, required: list[str] | None) -> bool:
    return bool(canonical_name(principal)) and canonical_name(principal) in {
        canonical_name(name) for name in required or []
    }


def _source_owner(unit: Unit) -> tuple[str | None, str]:
    from knowledge_graph.loader import load

    ref = unit.source.get("reference")
    try:
        index = load("meeting-notes-index")
    except FileNotFoundError:
        return None, "unresolved"
    notes = index.value.get("notes", []) if isinstance(index.value, dict) else []
    entry = next((n for n in notes if isinstance(n, dict) and n.get("path") == ref), None)
    if entry:
        if entry.get("owner"):
            return str(entry["owner"]), "explicit"
        participants = {canonical_name(p) for p in entry.get("participants", [])}
        for name in config.approval_settings()["owner_priority"]:
            if canonical_name(name) in participants:
                return name, "participants"
    return None, "unresolved"


def compute_required_approvers(unit: Unit) -> list[str] | None:
    """None means exempt; [] means unresolved and must never auto-promote."""
    if unit.legibility_ceiling:
        return None
    if unit.requires_approval_from is not None:
        return list(unit.requires_approval_from)
    owner, _ = _source_owner(unit)
    owner = owner or config.approval_settings()["fallback_owner"]
    return [owner] if owner else []


def owner_source(unit: Unit) -> str:
    if unit.legibility_ceiling:
        return "ceiling"
    if unit.requires_approval_from is not None:
        return "override"
    owner, resolution = _source_owner(unit)
    if owner:
        return resolution
    return "fallback" if config.approval_settings()["fallback_owner"] else "unresolved"


def compute_pending_approvers(unit: Unit, required: list[str] | None) -> list[str] | None:
    if required is None:
        return None
    approved = {canonical_name(record.get("by")) for record in unit.approvals}
    return [name for name in required if canonical_name(name) not in approved]
