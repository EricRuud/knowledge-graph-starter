"""Load proposals that have not yet become commitments."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any
import frontmatter
from knowledge_graph.config import KNOWLEDGE_ROOT as _ROOT, safe_path

IDEAS_ROOT = _ROOT / "ideas"


class IdeaStatus(str, Enum):
    OPEN = "open"
    PROMOTED = "promoted"
    DROPPED = "dropped"


@dataclass
class Idea:
    id: str
    subject: str
    proposed_by: str | None = None
    surfaced_at: date | None = None
    source: dict[str, Any] | None = None
    status: IdeaStatus = IdeaStatus.OPEN
    promoted_to: list[str] = field(default_factory=list)
    promoted_at: date | None = None
    dropped_reason: str | None = None
    domains: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    body: str = ""


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


def _idea_from_frontmatter(post: frontmatter.Post, idea_id: str) -> Idea:
    md = post.metadata
    return Idea(
        id=md.get("id", idea_id),
        subject=md.get("subject", ""),
        proposed_by=md.get("proposed_by"),
        surfaced_at=_parse_date(md.get("surfaced_at")),
        source=md.get("source"),
        status=IdeaStatus(md.get("status", "open")),
        promoted_to=md.get("promoted_to", []) or [],
        promoted_at=_parse_date(md.get("promoted_at")),
        dropped_reason=md.get("dropped_reason"),
        domains=md.get("domains", []) or [],
        tags=md.get("tags", []) or [],
        body=post.content,
    )


def load_idea(idea_id: str) -> Idea:
    path = safe_path(IDEAS_ROOT, idea_id)
    if not path.exists():
        raise FileNotFoundError(f"Idea not found: {idea_id} (looked at {path})")
    post = frontmatter.load(safe_path(IDEAS_ROOT, path.stem))
    return _idea_from_frontmatter(post, idea_id)


def list_ideas(
    *, status: str | None = None, domain: str | None = None, proposed_by: str | None = None
) -> list[Idea]:
    ideas: list[Idea] = []
    for path in sorted(IDEAS_ROOT.glob("*.md")):
        if path.name.startswith(".") or path.name == "README.md":
            continue
        try:
            post = frontmatter.load(safe_path(IDEAS_ROOT, path.stem))
            if post.metadata.get("type") != "idea":
                continue
            idea = _idea_from_frontmatter(post, path.stem)
        except Exception:
            continue
        if status is not None and idea.status.value != status:
            continue
        if domain is not None and domain not in idea.domains:
            continue
        if proposed_by is not None and idea.proposed_by != proposed_by:
            continue
        ideas.append(idea)
    return ideas
