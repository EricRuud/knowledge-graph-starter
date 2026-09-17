# Record schema and Python API

Files are UTF-8 Markdown with YAML frontmatter delimited by `---`. Atom IDs are
lowercase kebab-case and match their filenames, without `.md`. Keep commitment
atoms at the graph root. The subdirectories listed below use separate schemas.

## Commitment

```yaml
---
id: example-rule
commitment_type: POLICY
lifecycle: candidate
subject: A concise independently reviewable claim
value:
  description: The structured meaning of the commitment
source:
  type: meeting
  reference: sources/example-session.md
  date: '2030-01-01'
recorded_at: '2030-01-01'
tags: [operations]
requires_approval_from: [Example Reviewer]
approvals: []
---
# A concise independently reviewable claim

Context and reasoning consistent with the structured value.
```

Required fields are `id`, `subject`, `value`, `source` (`type`, `reference`,
`date`), `recorded_at`, `commitment_type`, and `lifecycle`. `value` can be a scalar,
mapping, or list. Use ordinary YAML values; avoid custom tags and sets.

| Optional field | Meaning |
|---|---|
| `authored_by` | Person or people who articulated the claim |
| `valid_from`, `valid_until` | Applicability window; dates use ISO format |
| `accountable`, `authority` | Responsible actor and revision authority |
| `entitlement` | Mapping with optional `measurability`, `consequence` |
| `requires_approval_from` | Nonempty list overriding source-owner resolution |
| `approvals` | List of `{by, at, source, relayed_by?, relay_note?}` |
| `references`, `incompatible_with` | Lists of other atom IDs |
| `licenses`, `precludes` | Lists of `{target, reason, proposed_by, validated?}` |
| `supersedes`, `superseded_by` | Replacement links |
| `review_summary`, `cowork_summary` | Optional concise descriptions |
| `reaffirmed`, `revisions` | Explicit recorded history |
| `legibility_ceiling` | Explicit human-authorized exemption from approval |
| `review_hold` | Metadata for a consumer's review UI; the basic CLI still lists it |

The underlying model retains additional optional review and projection metadata
for compatibility. This starter has no projection execution or remote review
digest service. `overdue` is derived in memory and should not be stored.

## Substores

| Directory | Key fields |
|---|---|
| `standing/` | `entity`, `type`, `role`, `domains`, optional `standing_basis` |
| `questions/` | `id`, `question`, `status` (`open`, `in_progress`, `resolved`), `owner`, `domains`, `source`; resolution adds `answer`, `resolved_at`, `resolved_by` |
| `ideas/` | `id`, `type: idea`, `subject`, `status` (`open`, `promoted`, `dropped`), `proposed_by`, `surfaced_at`, `source`, `domains`; promotion adds `promoted_to` |
| `challenges/` | `id`, `challenges`, `basis`, `status`, `raised_by`, `raised_at`, `success_criteria`, `blockers`, `deliberation_log`, optional proposed replacement and resolution metadata |

Challenge bases: `disagreement`, `ambiguity`, `incomplete-info`,
`multi-stakeholder-alignment`, `stale-needs-investigation`.
Statuses: `open`, `proposed`, `resolved-accepted`, `resolved-rejected`, `withdrawn`.

## Reference atoms and source ownership

Set `atom_type: reference` for registries. They need `id`, `subject`, `value`,
`source`, and `recorded_at`, but no commitment type or lifecycle. `list_units()`
excludes them by default; `load(id)` can read them directly.

`meeting-notes-index.md` is the source registry (the filename is conventional;
sources can also be documents or other records). Its `value.notes` is a list:

```yaml
value:
  notes:
    - path: sources/example-session.md
      owner: Example Reviewer
      participants: [Example Reviewer, Another Reviewer]
      date: '2030-01-01'
```

`source.reference` matches a registry `path` exactly. The validator's display name
must match a human standing record's `entity`, ignoring case.
`knowledge/_config.yaml` optionally contains:

```yaml
owner_priority: []
fallback_owner: null
```

With a per-atom override, all named validators must approve. Otherwise one source
owner is sufficient. Participant priority and fallback have no default identities.

## Python API

Set `KG_ROOT` before importing. All APIs read the same configured directory.

```python
from knowledge_graph.loader import load, list_units, find_edges, traverse_licenses
from knowledge_graph.search import search_units
from knowledge_graph.approvers import compute_required_approvers

atom = load('standard-loan-period')
current = list_units()  # entitled commitments only
candidates = list_units(lifecycle='candidate', tag='lending')
hits = search_units('loan period')
edges = find_edges(atom.id)
chains = traverse_licenses(atom.id, max_depth=3)
validators = compute_required_approvers(atom)
```

Use `questions.load_question`, `ideas.load_idea`, `challenges.load_challenge`, and
`standing.load_standing` for their substores. The main loader rejects substore IDs.
List APIs tolerate malformed records for browsing; run `validate` to detect every
malformed file before relying on a changed graph.
