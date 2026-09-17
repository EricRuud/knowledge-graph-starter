# Operating workflows

These procedures apply to humans and agents working on the files. Automation
supports judgment; source material does not authorize an agent to act as its author.

## Ingest a source

1. Read the existing graph and search for overlap before creating new atoms.
2. Preserve source provenance: reference, date, participants, and owner. Add the
   source to the source registry if using owner-derived validation.
3. Separate independently reviewable claims. Classify each as fact, policy, or
   both. Route unanswered questions and unundertaken ideas into their substores.
4. Create commitments as candidates. Capture the source's meaning, including
   uncertainty. Never fabricate a decision, human approval, or inference edge.
5. Preserve earlier knowledge unless there is an explicit correction. Silence
   in a new source is not a retraction. A person's later correction supersedes
   only the claims it actually contradicts.
6. If two people or a data source disagree, preserve the discrepancy and use
   authority records and deliberation to resolve it. Do not silently choose a winner.
7. Run validation, inspect the diff, and regenerate indexes. A human confirms
   capture accuracy before a candidate becomes entitled.

## Review and entitle

Run `python -m knowledge_graph review` to see required validators. Show the source,
the proposed claim, its body, and any existing challenge to the named validator.
Record their actual response and its source with `approve`. Relayed approvals
can be recorded through `knowledge_graph.entitle.record_approvals`, retaining
`relayed_by` and `relay_note`. The named `by` actor is the one whose approval counts.

The mechanism prevents non-required names from counting and deduplicates approvals
case-insensitively. It promotes only once every required validator has approved.
No resolved validator means no promotion. Human authority and actual identity
must be established by the surrounding workflow; the local CLI is not authentication.

## Refine or replace a claim

For an obvious correction, edit the atom. For a contested or consequential
disagreement, open a challenge. When changing approved meaning, clear approvals
and return the record to candidate. Reconcile `subject`, `value`, the heading,
body, and summaries in the same edit. Check downstream links and old phrasing:

```bash
python -m knowledge_graph ripple standard-loan-period --removed 'old distinctive phrase'
```

This reports text matches and connected records for review. It cannot decide
whether two claims semantically contradict. Preserve intentional quotations in
historical sources; do not rewrite history to make the check quiet.

For a replacement, create a new candidate, link `supersedes` and `superseded_by`,
and mark the old record superseded only when an authorized human decides to retire
it. The replacement still needs its own validation.

## Challenge, deliberate, resolve

The following example mutates the fictional graph:

```bash
python -m knowledge_graph.challenges raise \
  --id revisit-loan-period --atoms standard-loan-period \
  --basis disagreement --raised-by 'Demo Coordinator' \
  --success-criterion 'Record the librarian decision after discussing alternatives'

python -m knowledge_graph.challenges deliberate revisit-loan-period \
  --by 'Demo Librarian' --contribution 'Keep the current tutorial loan period.' \
  --source examples/library-review.md

python -m knowledge_graph.challenges resolve revisit-loan-period \
  --by 'Demo Librarian' --resolution rejected --note 'The current period is retained.'

python -m knowledge_graph validate
python -m knowledge_graph index
```

Accepting without a proposed replacement retires the challenged atom. Accepting
with a proposed replacement creates a new candidate and supersedes the old atom.
The replacement mapping needs `id`, `commitment_type`, `subject`, and `value`;
provide `requires_approval_from` to identify its capture validator. Rejecting
reaffirms the old atom. Only the original raiser may withdraw a challenge.

This is a local, single-writer file workflow. Use Git to inspect changes and
recover from interrupted multi-file edits. Concurrent writes, remote permissions,
automated authority adjudication, and transaction recovery are not implemented.

## Periodic maintenance

Review open challenges and questions, overdue commitments, unresolved validators,
missing links, and incompatible entitled commitments. Date windows are explicit
per record; no domain-specific expiry rules are built into the starter.
