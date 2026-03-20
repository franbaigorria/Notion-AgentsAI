---
name: notion-founder-workflow
description: Founder-oriented Notion workflow for capturing raw startup ideas, refining them into structured venture notes, and converting promising ideas into repo kickoff plans. Use when the user shares an AI product idea in natural language and wants it organized without command-like friction.
---

# Notion Founder Workflow

Use this skill when the user is brainstorming products with a cofounder mindset and wants Codex to:

- capture raw ideas in Notion
- impose a consistent structure
- preserve the user's wording where it matters
- separate explicit facts from inferred assumptions
- pressure-test the idea just enough to improve decisions
- turn a strong idea into a repo-ready kickoff

## Default Founder Flow

### 1. Capture the raw idea

Start from what the user actually said. Do not force precision too early.

Extract:

- idea name
- one-line pitch
- problem
- user
- buyer
- initial niche
- MVP
- AI layer
- risks
- suggested repo
- next step

Use [`templates/ai-venture-idea-template.md`](../../../../templates/ai-venture-idea-template.md) as the default shape.

### 2. Improve without over-polishing

Refine only enough to make the note useful later.

- tighten the problem statement
- narrow the MVP
- highlight the main hidden assumptions
- add `Open Questions` instead of pretending certainty

Avoid turning early ideas into bloated strategy documents.

### 3. Save in Notion

**Always save to the Ideas database in the Agent AI teamspace.** See [`workspace/notion-context.md`](../../../workspace/notion-context.md) for the database ID and URL.

Prefer this order:

1. Add a row to the Ideas database (ID: `a8ee2ffddc494d778c969d984c6c3386`).
2. If the idea needs more detail, create or update a linked page under the same teamspace.
3. If the database is not accessible, create a structured page first and ask the user to check permissions.

Use [`templates/notion-ideas-database-schema.md`](../../../../templates/notion-ideas-database-schema.md) as the default schema for an ideas database.

### 4. Convert to repo kickoff when the idea is mature enough

When the user wants to move from idea to build:

- identify the narrowest credible MVP
- propose a repo name
- define the first milestone
- define the first validation experiment
- create a short repo kickoff or implementation plan in Notion

## Pressure-Test Checklist

For AI ideas, explicitly check:

- Is the workflow frequent and painful enough?
- Is the first wedge narrow enough?
- Is the channel right for the market?
- Does this need memory, RAG, tools, or just good prompting?
- What breaks trust fastest?
- What should trigger human handoff?
- Is the moat likely to come from data, workflow, distribution, or brand?
- What metric proves the MVP is working?

## Writing Style

- Write like a thoughtful technical cofounder, not a PM template machine.
- Prefer compact notes with high leverage.
- Preserve ambiguity where it is real.
- Mark inferred content clearly through structure, not disclaimers everywhere.

