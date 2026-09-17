"""Inspect shareable files for common accidental secrets and personal paths.

Pass --denylist /outside/path.txt for private terms; that file stays outside the
repository. This check does not replace reviewing knowledge or Git history.
"""

import argparse
from pathlib import Path
import re

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"}
ALLOWED_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "access token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9_-]{25,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"
    ),
    "home directory": re.compile(r"(?:/Users/|/home/)[A-Za-z0-9_.-]+/|[A-Z]:\\Users\\[^\\]+\\"),
    "cloud access key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "email address": re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|org|net|invalid)\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
}


def check(root: Path, denylist: list[str] | None = None) -> tuple[list[str], int]:
    findings = []
    count = 0
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in rel.parts):
            continue
        if path.is_symlink():
            findings.append(f"{rel}: symlink must be reviewed")
            continue
        if not path.is_file():
            continue
        count += 1
        if path.name.startswith(".env") or path.suffix.lower() in {".pem", ".key", ".p12"}:
            findings.append(f"{rel}: credential-bearing file type")
        if path.suffix not in ALLOWED_SUFFIXES and path.name != ".gitignore":
            findings.append(f"{rel}: unexpected file type")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            findings.append(f"{rel}: non-text file must be reviewed")
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{rel}: possible {label}")
        for term in denylist or []:
            if term.casefold() in (str(rel) + "\n" + content).casefold():
                findings.append(f"{rel}: private denylist match (term withheld)")
    return findings, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--denylist", type=Path)
    args = parser.parse_args()
    denied = args.denylist.read_text(encoding="utf-8").splitlines() if args.denylist else []
    findings, count = check(args.root, [term.strip() for term in denied if term.strip()])
    for finding in findings:
        print(finding)
    print(f"Scanned {count} files; {len(findings)} finding(s).")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
