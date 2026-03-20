# Notion Founder Workflow for Codex

This repository is now optimized for one job: helping founders capture raw AI product ideas in natural language, structure them consistently, save them in Notion, and turn promising ones into repo kickoffs.

## What This Repo Keeps

- **Notion workspace context** in [`workspace/notion-context.md`](workspace/notion-context.md) — tells agents where to find databases and pages
- Repo-local Notion MCP configuration in [`.codex/config.toml`](.codex/config.toml)
- Shared Notion skills in [`.agents/skills/notion`](.agents/skills/notion)
- A founder-specific workflow skill in [`.agents/skills/notion-founder-workflow/SKILL.md`](.agents/skills/notion-founder-workflow/SKILL.md)
- Reusable templates in [`templates/`](templates)
- Example captured ideas in [`ideas/`](ideas)

## Notion Setup

All data lives in the **Agent AI** teamspace in Notion. Before using this repo:

1. Make sure you have access to the Agent AI teamspace (ask the owner to invite you)
2. Authenticate the Notion MCP: `opencode mcp auth notion` (or `codex mcp login notion`)
3. Read [`workspace/notion-context.md`](workspace/notion-context.md) to understand the structure

## What We Removed

The repo no longer centers on prompt-style command wrappers.

For this team, the useful interface is conversation plus skills:

- "agrega esta idea"
- "refina esta idea"
- "pasala a repo MVP"

That keeps friction low and lets Codex act more like a technical cofounder than a command runner.

## Recommended Workflow

### 1. Talk naturally

Share the idea in plain language.

Example:

```text
Agrega esta nueva idea: agente de voz con acento argentino, con RAG, para soporte y seguimiento.
```

### 2. Let Codex structure it

Codex should apply the founder workflow skill and shape the note using:

- [`templates/ai-venture-idea-template.md`](templates/ai-venture-idea-template.md)
- [`templates/notion-ideas-database-schema.md`](templates/notion-ideas-database-schema.md)

### 3. Save to Notion

If the Notion MCP is available, Codex should:

- create or update an entry in an ideas database
- or create a structured page if no database exists yet

### 4. Escalate to repo planning

When an idea is worth building, Codex should turn it into:

- a tighter MVP definition
- a suggested repo name
- first milestones
- early tasks
- a validation plan

## Core Skills

- [`.agents/skills/notion/SKILL.md`](.agents/skills/notion/SKILL.md): general Notion operations and idea capture guidance
- [`.agents/skills/notion-founder-workflow/SKILL.md`](.agents/skills/notion-founder-workflow/SKILL.md): founder-focused capture, refinement, and repo handoff
- [`.agents/skills/notion/knowledge-capture/SKILL.md`](.agents/skills/notion/knowledge-capture/SKILL.md): saving conversations, learnings, and decisions
- [`.agents/skills/notion/spec-to-implementation/SKILL.md`](.agents/skills/notion/spec-to-implementation/SKILL.md): turning a validated idea into an implementation plan

## Notes

- The imported Notion cookbook skills still contain some Claude-oriented helper names. In this repo, treat them as conceptual only and map them to the real tools exposed by the active Notion MCP server.
- Authentication happens through Notion's hosted MCP flow.
