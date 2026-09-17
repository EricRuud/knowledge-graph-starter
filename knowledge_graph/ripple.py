"""Find linked commitments and text fragments affected by an edit."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from knowledge_graph import loader
from knowledge_graph.stale_text import find_residue


@dataclass(frozen=True)
class RippleCandidate:
    atom_id: str
    site: str
    current_text: str
    reason: str


def _id_for_path(path: Path, root: Path) -> str:
    return path.relative_to(root).with_suffix("").as_posix()


def _residue_candidates(
    atom_id: str, removed_fragments: list[str], root: Path
) -> list[RippleCandidate]:
    out: list[RippleCandidate] = []
    for path, line_no, line, _fragment in find_residue(removed_fragments, root):
        hit_id = _id_for_path(path, root)
        reason = "value_body_mismatch" if hit_id == atom_id else "residue"
        out.append(RippleCandidate(hit_id, f"body:L{line_no}", line.strip(), reason))
    return out


def _connected_ids(atom_id: str) -> set[str]:
    connected: set[str] = set()
    edited = loader.load(atom_id)
    connected.update(edited.references)
    connected.update((e.target for e in edited.licenses))
    connected.update((e.target for e in edited.precludes))
    for unit in loader.list_units(lifecycle="all"):
        if (
            atom_id in unit.references
            or any((e.target == atom_id for e in unit.licenses))
            or any((e.target == atom_id for e in unit.precludes))
        ):
            connected.add(unit.id)
    connected.discard(atom_id)
    return connected


def _reference_candidates(atom_id: str, exclude_ids: set[str]) -> list[RippleCandidate]:
    out: list[RippleCandidate] = []
    for cid in _connected_ids(atom_id):
        if cid in exclude_ids:
            continue
        try:
            unit = loader.load(cid)
        except (FileNotFoundError, ValueError):
            continue
        if unit.lifecycle is not None and unit.lifecycle.value == "superseded":
            continue
        out.append(RippleCandidate(cid, "reference", unit.subject, "reference"))
    return out


def find_ripples(atom_id: str, removed_fragments: list[str]) -> list[RippleCandidate]:
    root = loader.KNOWLEDGE_ROOT
    residue = _residue_candidates(atom_id, removed_fragments, root)
    already_flagged = {c.atom_id for c in residue}
    reference = _reference_candidates(atom_id, already_flagged)
    return sorted(residue + reference, key=lambda c: (c.atom_id, c.site))
