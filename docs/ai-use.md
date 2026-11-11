# Use of AI tools (MASTER G6): draft

Audience: Space Apps judges and organizers.

Space Apps rules require listing every AI tool, where and how it was used, and acknowledging AI-assisted code and data work. Keep this file current; the project page copies it.

## Tools and uses

| Tool | Where it was used | How it was used | Human review |
|---|---|---|---|
| Claude Code (Anthropic; model Claude Opus 5.5) | Session 2026-11-10 | Audited the repository against MASTER v3. Wrote the audit, the execution plan, the worklog, the decisions log, and the pre-registration drafts. Wrote `scripts/nisar_inventory.py`, `scripts/freeze_inputs.py`, and their tests. Ran the NASA CMR inventory query. Corrected the corrections and wavelength guidance in README, CLAUDE.md, and MASTER (v3.1). | Decisions delegated to the AI's recommendations by the repository owner on 2026-11-10 (`docs/decisions.md`). Team review pending before merge. |
| *To fill in:* tools used for commits from 2026-11-06 to 2026-11-09 (backend, ingestion, provisional build, website) | | | |
| *To fill in:* tools used for the deck, images, or text | | | |

## Statement for the project page (draft)

> TerraGauge was built with AI-assisted coding. AI tools helped write and review code, data-processing scripts, and documentation, and helped audit the project against its own scientific rules. Every number on this page is computed by code in the repository from the cited NASA and partner data, and every rule that produces a label was written down and committed before the results it governs. Team members reviewed and approved the decisions recorded in `docs/decisions.md`.

Edit the last sentence so it is true at submission time.
