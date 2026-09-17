"""Weighted keyword search and compact context assembly."""

from knowledge_graph.loader import list_units


def _load_all_units():
    return list_units(lifecycle="candidate,entitled")


def _score_match(unit, keywords: list[str], domains: list[str] | None) -> float:
    score = 0.0
    subject_lower = unit.subject.lower()
    body_lower = unit.body.lower() if unit.body else ""
    tags_lower = [t.lower() for t in unit.tags]
    for kw in keywords:
        if kw in subject_lower:
            score += 2.0
        elif kw in body_lower:
            score += 0.5
    if domains:
        domain_match = any((d.lower() in tags_lower for d in domains))
        if not domain_match:
            return 0.0
    for kw in keywords:
        if any((kw in t for t in tags_lower)):
            score += 1.0
    return score


def search_units(query: str, domains: list[str] | None = None, max_results: int = 10) -> list[dict]:
    units = _load_all_units()
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    if not keywords:
        return []
    scored = []
    for unit in units:
        score = _score_match(unit, keywords, domains)
        if score > 0:
            scored.append(
                {
                    "id": unit.id,
                    "subject": unit.subject,
                    "lifecycle": str(unit.lifecycle.value)
                    if hasattr(unit.lifecycle, "value")
                    else str(unit.lifecycle),
                    "tags": unit.tags,
                    "match_score": score,
                }
            )
    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:max_results]


def context_summary(domains: list[str] | None = None) -> str:
    units = _load_all_units()
    lines = []
    for unit in units:
        if domains:
            tags_lower = [t.lower() for t in unit.tags]
            if not any((d.lower() in tags_lower for d in domains)):
                continue
        ctx = ""
        if isinstance(unit.value, dict):
            ctx = unit.value.get("context", "")
        lifecycle = (
            str(unit.lifecycle.value) if hasattr(unit.lifecycle, "value") else str(unit.lifecycle)
        )
        entry = f"- **{unit.id}** [{lifecycle}]: {unit.subject}"
        if ctx:
            ctx_short = ctx[:200].rstrip()
            if len(ctx) > 200:
                ctx_short += "..."
            entry += f"\n  Context: {ctx_short}"
        lines.append(entry)
    return "\n".join(lines)
