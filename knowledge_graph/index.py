"""Generate separate catalogs for entitled and unsettled knowledge."""

from knowledge_graph import loader


def render_indexes() -> dict[str, str]:
    primary = [
        "# Knowledge index",
        "",
        "Entitled commitments. Check source, dates, and open challenges before acting.",
        "",
    ]
    unsettled = [
        "# Unsettled knowledge",
        "",
        "Candidates and history are not current validated commitments.",
        "",
    ]
    for unit in loader.list_units(lifecycle="all"):
        target = primary if unit.lifecycle.value == "entitled" else unsettled
        subject = unit.subject.replace("\n", " ")
        overdue = f"; overdue since {unit.valid_until}" if unit.overdue else ""
        target.append(f"- [{unit.id}]({unit.id}.md) — {subject} [{unit.lifecycle.value}{overdue}]")
    return {
        "index.md": "\n".join(primary) + "\n",
        "index-candidates.md": "\n".join(unsettled) + "\n",
    }


def regenerate(check: bool = False) -> list[str]:
    drift = []
    for name, content in render_indexes().items():
        path = loader.KNOWLEDGE_ROOT / name
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            drift.append(name)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
    return drift
