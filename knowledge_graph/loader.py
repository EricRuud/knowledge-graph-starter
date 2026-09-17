"""Load, filter, and traverse Markdown commitments. See docs/schema.md for the format."""

from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Any
import frontmatter
from knowledge_graph.expiry import apply_expiry
from knowledge_graph.models import Entitlement, InferenceEdge, Kind, Lifecycle, Unit
from knowledge_graph.config import KNOWLEDGE_ROOT as _ROOT, safe_path

KNOWLEDGE_ROOT = _ROOT


def _path_for_id(unit_id: str) -> Path:
    if unit_id.startswith("knowledge/"):
        rel = unit_id[len("knowledge/") :]
    else:
        rel = unit_id
    return safe_path(KNOWLEDGE_ROOT, rel)


def _id_for_path(path: Path) -> str:
    rel = path.relative_to(KNOWLEDGE_ROOT)
    no_ext = rel.with_suffix("")
    return no_ext.as_posix()


_SUBSTORES = {
    "questions",
    "projections",
    "uncodified",
    "ideas",
    "charters",
    "standing",
    "challenges",
}


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date) and (not isinstance(val, datetime)):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val)
    raise ValueError(f"Cannot parse date from {val!r}")


def _parse_edges(raw: Any) -> list[InferenceEdge]:
    if not raw or not isinstance(raw, list):
        return []
    edges = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        edges.append(
            InferenceEdge(
                target=item["target"],
                reason=item["reason"],
                proposed_by=item["proposed_by"],
                validated=_parse_date(item.get("validated")),
            )
        )
    return edges


def _unit_from_frontmatter(post: frontmatter.Post, unit_id: str) -> Unit:
    md = post.metadata
    atom_type = md.get("atom_type") or "commitment"
    lifecycle_raw = md.get("lifecycle")
    if lifecycle_raw == "load-bearing":
        lifecycle_raw = "entitled"
    lifecycle = Lifecycle(lifecycle_raw) if lifecycle_raw is not None else None
    ent_raw = md.get("entitlement")
    ent_obj: Entitlement | None = None
    if isinstance(ent_raw, dict):
        ent_obj = Entitlement(
            measurability=ent_raw.get("measurability"), consequence=ent_raw.get("consequence")
        )
    ctype = md.get("commitment_type")
    if ctype == "FACT":
        derived_kind = Kind.FACT
    elif ctype in ("POLICY", "BOTH"):
        derived_kind = Kind.DECISION
    elif "kind" in md:
        derived_kind = Kind(md["kind"])
    elif atom_type != "commitment":
        derived_kind = Kind.FACT
    else:
        raise ValueError(f"Unit {unit_id} is missing commitment_type (and has no legacy kind)")
    return Unit(
        id=md.get("id", unit_id),
        kind=derived_kind,
        subject=md["subject"],
        value=md["value"],
        source=md["source"],
        recorded_at=_parse_date(md["recorded_at"]) or date.today(),
        lifecycle=lifecycle,
        authored_by=md.get("authored_by"),
        valid_from=_parse_date(md.get("valid_from")),
        valid_until=_parse_date(md.get("valid_until")),
        confidence=md.get("confidence"),
        supersedes=md.get("supersedes"),
        superseded_by=md.get("superseded_by"),
        references=md.get("references", []) or [],
        tags=md.get("tags", []) or [],
        entitlement=ent_obj,
        accountable=md.get("accountable"),
        authority=md.get("authority"),
        incompatible_with=md.get("incompatible_with", []) or [],
        licenses=_parse_edges(md.get("licenses")),
        precludes=_parse_edges(md.get("precludes")),
        reaffirmed=md.get("reaffirmed", []) or [],
        revisions=md.get("revisions", []) or [],
        review_scores=md.get("review_scores"),
        commitment_ease=md.get("commitment_ease"),
        commitment_type=md.get("commitment_type"),
        atom_type=atom_type,
        review_summary=md.get("review_summary"),
        cowork_summary=md.get("cowork_summary"),
        legibility_ceiling=md.get("legibility_ceiling", False),
        is_projection=md.get("is_projection", False),
        projection_source=md.get("projection_source"),
        projection_query=md.get("projection_query"),
        requires_approval_from=md.get("requires_approval_from"),
        approvals=md.get("approvals", []) or [],
        review_hold=md.get("review_hold", False),
        rejected_at=_parse_date(md.get("rejected_at")),
        rejected_by=md.get("rejected_by"),
        rejection_note=md.get("rejection_note"),
        rejection_source=md.get("rejection_source"),
        body=post.content,
    )


def load(unit_id: str) -> Unit:
    first_segment = unit_id.removeprefix("knowledge/").split("/", 1)[0]
    if first_segment in _SUBSTORES:
        raise ValueError(
            f"Cannot load {unit_id!r} as a Unit: {first_segment} substore has its own schema. Use the {first_segment} API instead."
        )
    path = _path_for_id(unit_id)
    if not path.exists():
        raise FileNotFoundError(f"Unit not found: {unit_id} (looked at {path})")
    post = frontmatter.load(_path_for_id(unit_id))
    unit = _unit_from_frontmatter(post, unit_id)
    return apply_expiry(unit)


def list_units(
    *,
    kind: Kind | None = None,
    tag: str | None = None,
    lifecycle: str = "entitled",
    include: str | None = None,
    needs_approval_from: str | None = None,
    atom_type: str = "commitment",
) -> list[Unit]:
    if include is not None:
        lifecycle = {"active": "entitled", "load-bearing": "entitled"}.get(include, include)
    units: list[Unit] = []
    for path in sorted(KNOWLEDGE_ROOT.rglob("*.md")):
        if path.name.startswith("."):
            continue
        rel_parts = path.relative_to(KNOWLEDGE_ROOT).parts
        if rel_parts and rel_parts[0] in _SUBSTORES:
            continue
        try:
            unit_id = _id_for_path(path)
            post = frontmatter.load(_path_for_id(unit_id))
            file_atom_type = post.metadata.get("atom_type") or "commitment"
            if file_atom_type != atom_type:
                continue
            if (
                atom_type == "commitment"
                and "commitment_type" not in post.metadata
                and ("kind" not in post.metadata)
            ):
                continue
            unit = _unit_from_frontmatter(post, unit_id)
            unit = apply_expiry(unit)
        except Exception:
            continue
        if lifecycle != "all":
            allowed = {s.strip() for s in lifecycle.split(",")}
            if "load-bearing" in allowed:
                allowed.discard("load-bearing")
                allowed.add("entitled")
            if unit.lifecycle is None or unit.lifecycle.value not in allowed:
                continue
        if kind is not None and unit.kind != kind:
            continue
        if tag is not None and tag not in unit.tags:
            continue
        if needs_approval_from is not None:
            from knowledge_graph.approvers import (
                compute_pending_approvers,
                compute_required_approvers,
            )

            required = compute_required_approvers(unit)
            if required is None:
                continue
            pending = compute_pending_approvers(unit, required)
            if pending is None or needs_approval_from.lower() not in {p.lower() for p in pending}:
                continue
        units.append(unit)
    return units


def value(unit_id: str) -> Any:
    return load(unit_id).value


def resolve_references(unit: Unit) -> list[Unit]:
    resolved: list[Unit] = []
    for ref_id in unit.references:
        try:
            resolved.append(load(ref_id))
        except FileNotFoundError:
            continue
    return resolved


def find_unentitled() -> list[Unit]:
    """Find entitled commitments missing their required capture validation."""
    from knowledge_graph.approvers import compute_required_approvers, compute_pending_approvers

    violations = []
    for unit in list_units(lifecycle="entitled"):
        required = compute_required_approvers(unit)
        if required is not None and (not required or compute_pending_approvers(unit, required)):
            violations.append(unit)
    return violations


def find_edges(unit_id: str) -> dict:
    target_unit = load(unit_id)
    result: dict = {
        "outgoing_licenses": list(target_unit.licenses),
        "outgoing_precludes": list(target_unit.precludes),
        "incoming_licenses": [],
        "incoming_precludes": [],
    }
    for unit in list_units(lifecycle="all"):
        if unit.id == unit_id:
            continue
        for edge in unit.licenses:
            if edge.target == unit_id:
                result["incoming_licenses"].append((unit.id, edge))
        for edge in unit.precludes:
            if edge.target == unit_id:
                result["incoming_precludes"].append((unit.id, edge))
    return result


def traverse_licenses(unit_id: str, max_depth: int = 3) -> list[list[str]]:
    all_units = {u.id: u for u in list_units(lifecycle="all")}
    if max_depth <= 0:
        return []
    if unit_id not in all_units:
        all_units[unit_id] = load(unit_id)
    chains: list[list[str]] = []

    def _walk(current_id: str, path: list[str], depth: int) -> None:
        unit = all_units.get(current_id)
        if unit is None:
            return
        for edge in unit.licenses:
            if edge.target in path:
                continue
            new_path = path + [edge.target]
            chains.append(new_path)
            if depth < max_depth:
                _walk(edge.target, new_path, depth + 1)

    _walk(unit_id, [unit_id], 1)
    return chains


def find_incompatibility_violations() -> list[tuple[str, str]]:
    all_units = {u.id: u for u in list_units(lifecycle="entitled")}
    seen: set[tuple[str, str]] = set()
    violations: list[tuple[str, str]] = []
    for uid, unit in all_units.items():
        for inc_id in unit.incompatible_with:
            if inc_id in all_units:
                key = tuple(sorted([uid, inc_id]))
                if key not in seen:
                    seen.add(key)
                    violations.append(key)
    return violations


def find_preclusion_conflicts() -> list[tuple[str, str, str]]:
    entitled = {u.id: u for u in list_units(lifecycle="entitled")}
    conflicts: list[tuple[str, str, str]] = []
    for uid, unit in entitled.items():
        for edge in unit.precludes:
            if edge.target in entitled:
                conflicts.append((uid, edge.target, edge.reason))
    return conflicts


def find_dangling_edges() -> list[tuple[str, str, str]]:
    all_ids = {u.id for u in list_units(lifecycle="all")}
    danglers: list[tuple[str, str, str]] = []
    for unit in list_units(lifecycle="all"):
        for edge in unit.licenses:
            if edge.target not in all_ids:
                danglers.append((unit.id, "licenses", edge.target))
        for edge in unit.precludes:
            if edge.target not in all_ids:
                danglers.append((unit.id, "precludes", edge.target))
    return danglers


def edge_weight(source_lifecycle: str, target_lifecycle: str) -> str:
    if source_lifecycle == "entitled" and target_lifecycle == "entitled":
        return "load-bearing"
    if "superseded" in (source_lifecycle, target_lifecycle):
        return "historical"
    return "provisional"


def find_unvalidated_edges() -> list[tuple[str, str, InferenceEdge]]:
    unvalidated: list[tuple[str, str, InferenceEdge]] = []
    for unit in list_units(lifecycle="entitled"):
        for edge in unit.licenses:
            if edge.validated is None:
                unvalidated.append((unit.id, "licenses", edge))
        for edge in unit.precludes:
            if edge.validated is None:
                unvalidated.append((unit.id, "precludes", edge))
    return unvalidated
