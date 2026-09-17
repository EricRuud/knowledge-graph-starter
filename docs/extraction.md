# What this starter contains

This is a standalone extraction of the reusable file-based graph engine and its
operating model. The original workspace and its Git objects are not dependencies.

## Retained mechanics

The model, loader, lifecycle and expiry behavior, inference traversal, keyword
scoring, approval recording, idea/question/standing stores, challenge lifecycle,
content hashing, and change-ripple search come from the reusable engine. Original
company-oriented comments and examples were removed. This documentation and the
fictional lending-library corpus were written specifically for the starter.

## Adaptations

- Python imports live under the standalone `knowledge_graph` package.
- `KG_ROOT` selects the graph; no source-workspace paths are retained.
- Configurable source ownership replaces hardcoded people and principal maps.
- Unresolved owners do not cause approval or promotion.
- Atom paths are confined to the selected store.
- Validation and index generation are generic, with no company-specific expected
  record counts, canonical values, or business rules.
- A small local CLI and read-only stdio MCP server replace application integrations.
- New isolated tests use only invented records.

## Deliberate scope

This package does not include the original corpus, meeting notes, personnel,
customer information, financial or operational rules, original fixtures, archived
documents, media, generated reports, secrets, deployment settings, Git history,
or remote URLs. It also excludes the web application, chat bots, business-system
connectors, charter application, transcription services, remote review-digest
pipeline, and automatic extraction by a language model.

The core is useful without those integrations. Source ingestion remains an
explicit workflow for a person or an agent; the engine handles storage, retrieval,
validation, and lifecycle mechanics. The test suite and generic share checker can
be run locally. Privacy-sensitive source checks were done outside the exported
repository, so the check itself does not embed private names or identifiers.
