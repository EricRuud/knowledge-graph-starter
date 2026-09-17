"""Find stale text fragments across a knowledge directory."""

from __future__ import annotations
import argparse
from pathlib import Path

DEFAULT_EXCLUDES = (
    "review-digests",
    "advisor-runs",
    "log.md",
    "meeting-notes-index.md",
    "index.md",
    "index-candidates.md",
)


def _excluded(path: Path, root: Path, excludes: tuple[str, ...]) -> bool:
    rel = path.relative_to(root)
    return rel.parts[0] in excludes


def find_residue(
    fragments: list[str], root: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES
) -> list[tuple[Path, int, str, str]]:
    root = Path(root)
    needles = [(f, f.lower()) for f in fragments]
    hits: list[tuple[Path, int, str, str]] = []
    for path in sorted(root.rglob("*.md")):
        if _excluded(path, root, excludes):
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lowered = line.lower()
            for fragment, needle in needles:
                if needle in lowered:
                    hits.append((path, line_no, line, fragment))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_stale_text",
        description="Grep removed-text fragments across the knowledge base; exit 1 if any survive (residue), 0 if clean.",
    )
    parser.add_argument("--root", default="knowledge", help="knowledge tree to search")
    parser.add_argument("fragments", nargs="+", help="distinctive fragment(s) of the removed text")
    args = parser.parse_args(argv)
    hits = find_residue(args.fragments, root=Path(args.root))
    if not hits:
        print(f"clean — no residue for {len(args.fragments)} fragment(s)")
        return 0
    for path, line_no, line, fragment in hits:
        print(f"{path}:{line_no}: [{fragment}] {line.strip()}")
    print(f"\n{len(hits)} residue hit(s) — reconcile before shipping the refine")
    return 1
