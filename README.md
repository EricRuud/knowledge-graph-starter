# Knowledge Graph Starter

A small, Git-backed knowledge graph for turning source material into structured
commitments that humans can review and agents can query. Records are Markdown
with YAML frontmatter. No database, model API, account, or network service is
needed for the core.

**All included people, sources, decisions, and approvals are invented examples
about a fictional lending library.** This repository contains reusable mechanics
and new documentation, with no original organization records or Git history.

## Start here

Requires Python 3.11 or later. Run from this repository's root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m knowledge_graph validate
python -m knowledge_graph list
python -m knowledge_graph search 'loan period'
python -m knowledge_graph graph standard-loan-period
python -m knowledge_graph review
python -m pytest -q
```

`kg` is a shorthand for `python -m knowledge_graph` after installation.
On Windows, activate with `.venv\Scripts\activate`.

## What it does

- **Capture:** one claim or commitment per file, with its source and structured value.
- **Review:** `candidate → entitled → superseded`, with explicit human approvals.
- **Connect:** declared `licenses`, `precludes`, references, and incompatibilities.
- **Question:** separate stores for unanswered questions, ideas, and challenges.
- **Inspect:** keyword search, graph traversal, review queues, and generated indexes.
- **Maintain:** schema checks, missing-link checks, incompatible-policy detection,
  overdue flags, and searches for stale text after an edit.
- **Use with agents:** a Python API, command line tools, agent instructions, and
  an optional local MCP server.

The default list contains entitled commitments. Search includes candidates too
and labels their lifecycle. An overdue record keeps its lifecycle; the owner
decides whether to renew, retire, or replace it. An open challenge should be
read before relying on the challenged commitment.

## Try a review

The tutorial's `return-reminder` record is a candidate. The source registry names
`Demo Librarian` as its capture validator. To simulate that human's validation:

```bash
python -m knowledge_graph approve return-reminder \
  --by 'Demo Librarian' --source examples/library-review.md
python -m knowledge_graph validate
python -m knowledge_graph index
```

This **edits the tutorial** and appends to `knowledge/log.md`. It demonstrates
capture validation; the separate reminder-timing challenge remains open. In a
real graph, record an approval only after the named person actually provides it.
The command records an attestation; it does not authenticate the person typing it.

## Files

| Path | Purpose |
|---|---|
| `knowledge_graph/` | Standalone Python library, CLI, and optional MCP server |
| `knowledge/` | Entirely fictional example records and validator settings |
| `templates/` | Blank record patterns for a new graph |
| `examples/` | Invented source session and capture review |
| `docs/model.md` | The conceptual model and why each part exists |
| `docs/schema.md` | Field definitions, relationships, and configuration |
| `docs/workflows.md` | Source ingestion, review, edits, and challenges |
| `docs/mcp.md` | Local agent integration |
| `docs/extraction.md` | Included mechanics, adaptations, and scope |
| `tests/` | Isolated tests using temporary fictional graphs |
| `scripts/check_share.py` | Share-time checks for credentials and machine paths |

## Bring your own knowledge

Keep private records outside this shareable repo. Create an empty directory and
point `KG_ROOT` at it before launching a command:

```bash
mkdir -p private/knowledge/standing
export KG_ROOT="$PWD/private/knowledge"
python -m knowledge_graph validate
```

Copy the needed [templates](templates/) into that graph, fill them from your own
sources, and create standing records for validators. Choose a source owner or
set `requires_approval_from` on each commitment. With no resolved validator,
candidates stay candidates. Optional `_config.yaml` settings can define participant
priority and a fallback; there are no hardcoded people.

`KG_ROOT` defaults to `./knowledge` in the current working directory. The package
does not look up parent repositories or use a sibling graph. Set an absolute
path when launching it from an agent client.

## Development and sharing

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m knowledge_graph validate
python -m knowledge_graph index --check
python scripts/check_share.py
```

The privacy check is a useful guard, not a semantic guarantee. If you add real
knowledge later, review both files and Git history before sharing. A fresh clone
of this starter has only the fictional example corpus.
