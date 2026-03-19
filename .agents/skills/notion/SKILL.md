---
name: notion-workspace
description: General-purpose Notion workspace operations for Codex. Use when the user wants to search, find, query, create, or update pages and databases in Notion, or when another Notion skill needs a generic operational layer.
---

# Notion Workspace

This skill is the Codex-native entry point for working with Notion through the hosted `notion` MCP server.

Use it when the user wants to:

- Search their Notion workspace
- Find a page or database by title
- Query a database with natural-language filters
- Create a page with sensible structure
- Create a database row or task
- Update an existing page, task, or project tracker
- Set up a Notion board to coordinate work with Codex
- Capture startup or product ideas and turn them into structured venture notes

## Codex Porting Note

The imported Notion cookbook skills in this repository were originally written against Claude-oriented helper names such as:

- `Notion:notion-search`
- `Notion:notion-fetch`
- `Notion:notion-create-pages`
- `Notion:notion-update-page`

In Codex, treat those names as conceptual placeholders. Before acting:

1. Inspect the currently available tools on the `notion` MCP server.
2. Choose the real tool names that correspond to search, fetch/read, create, update, and database operations.
3. Use the real tools, not the legacy names.

## Default Workflow

1. Clarify the user's goal only if a wrong write would be risky.
2. Search or inspect first unless the target page/database is already explicit.
3. Summarize candidate targets when there is ambiguity.
4. Confirm only when the write target is still uncertain.
5. Perform the Notion action.
6. Return a short human-readable summary with titles, key fields, and links or identifiers.

## Operation Guides

### Search

- Interpret the request as a natural-language workspace query.
- Prefer high-signal search or database lookup tools.
- Return a concise list with title, object type, location, and why each result is relevant.

### Find

- Treat the input as title keywords.
- Bias toward precision over recall.
- Return the best few pages or databases, not a noisy dump.

### Database Query

- Resolve the target database by name or ID.
- Translate user filters into the database schema that actually exists.
- Keep the result set reasonably small unless the user asks for more.
- Present results in a readable table-like summary, not raw JSON.

### Create Page

- Infer a sensible initial structure from the title and context.
- If a parent is named but ambiguous, ask a brief clarification question before writing.
- If an exact duplicate exists in the same parent, ask before creating another one.

### Create Task or Database Row

- Resolve the target database first.
- Map natural-language fields to the actual Notion properties.
- Call out any inferred mappings or skipped properties.
- Ask for missing required properties before writing.

### Task Board Setup

When helping a user create or adapt a board for Codex-driven work, make sure it has:

- A status property with states equivalent to Planning, In Progress, and Done
- A short text property for agent status updates
- A checkbox or equivalent flag for blocked state

### Startup Idea Capture

When the user shares an early-stage product or AI idea, default to a structure that is useful for founders making decisions later.

Capture:

- Idea name
- One-line pitch
- Problem being solved
- Target user or buyer
- MVP scope
- Data or RAG needs
- Voice, UX, or channel details if relevant
- Technical risks
- Business risks
- Near-term use cases
- Long-term vision
- Suggested repo name
- Next validation step

When the idea is still fuzzy:

- Preserve the user's language and intent
- Separate what is explicit from what is inferred
- Add a short `Open Questions` section instead of inventing certainty
- Prefer a compact founder-ready page over a long speculative document

For AI-product ideas, explicitly pressure-test:

- Whether the workflow is high frequency and painful enough
- Whether the system needs real-time context, memory, or both
- Whether success depends on latency, accuracy, trust, or conversion
- Whether a human fallback is required
- Whether the moat is data, workflow, distribution, or brand

If the user wants, turn a promising idea into:

- A structured Notion page
- A row in an ideas database
- A repo kickoff plan with milestones and first tasks

## When To Hand Off To Specialized Skills

- Use `notion-knowledge-capture` for saving conversations as docs, FAQs, guides, or decisions.
- Use `notion-meeting-intelligence` for agendas, briefs, and meeting preparation.
- Use `notion-research-documentation` for synthesis across multiple pages.
- Use `notion-spec-to-implementation` for turning a spec into plans and tasks.
