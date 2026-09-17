"""Load human and agent authority records from the standing substore."""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
import frontmatter
import yaml
from knowledge_graph.config import KNOWLEDGE_ROOT as _ROOT, safe_path

logger = logging.getLogger(__name__)
STANDING_ROOT = _ROOT / "standing"


@dataclass
class StandingRecord:
    entity: str
    type: str
    role: str
    domains: list[str] = field(default_factory=list)
    id: str | None = None
    standing_basis: str | None = None
    body: str = ""


def _record_from_post(post: frontmatter.Post) -> StandingRecord:
    md = post.metadata
    return StandingRecord(
        entity=md["entity"],
        type=md.get("type", "human"),
        role=md.get("role", ""),
        domains=list(md.get("domains") or []),
        id=md.get("id"),
        standing_basis=md.get("standing_basis"),
        body=post.content,
    )


def load_standing(name: str) -> StandingRecord:
    path = safe_path(STANDING_ROOT, name)
    if not path.exists():
        raise FileNotFoundError(f"Standing record not found: {path}")
    return _record_from_post(frontmatter.load(path))


def list_standings() -> list[StandingRecord]:
    if not STANDING_ROOT.exists():
        return []
    out: list[StandingRecord] = []
    for path in sorted(STANDING_ROOT.glob("*.md")):
        if path.name.startswith(".") or path.name.lower() == "readme.md":
            continue
        try:
            out.append(_record_from_post(frontmatter.load(safe_path(STANDING_ROOT, path.stem))))
        except (KeyError, yaml.YAMLError) as exc:
            logger.warning("Skipping malformed standing record %s: %s", path, exc)
            continue
    return out


def list_human_standings() -> list[StandingRecord]:
    return [r for r in list_standings() if r.type == "human"]


def find_by_entity(entity: str) -> StandingRecord | None:
    needle = entity.strip().lower()
    for r in list_standings():
        if r.entity.lower() == needle:
            return r
    return None
