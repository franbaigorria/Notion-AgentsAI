# Notion Founder Workflow

This repository packages a Codex-native Notion workflow centered on founder idea capture and repo kickoffs.

## Before You Start

**Read [`workspace/notion-context.md`](workspace/notion-context.md)** to know where everything lives in Notion. All our data is in the **Agent AI** teamspace. If you can't see it, ask the user to invite you.

## Use These Skills

- Shared skills live in `.agents/skills/notion/`.
- Start with `.agents/skills/notion/SKILL.md` for general Notion workspace operations.
- Prefer `.agents/skills/notion-founder-workflow/SKILL.md` when the user is sharing a startup or AI product idea in plain language.
- Use the specialized skills when the user asks for:
  - Knowledge capture
  - Meeting preparation and agendas
  - Research synthesis and documentation
  - Turning specs into implementation plans or tasks

## MCP Expectations

- Prefer the `notion` MCP server configured in `.codex/config.toml`.
- Before acting, inspect the currently available Notion MCP tools and map any legacy references in the imported cookbook skills to the real tool names exposed by the server.
- Treat the legacy names below as conceptual only:
  - `Notion:notion-search`
  - `Notion:notion-fetch`
  - `Notion:notion-create-pages`
  - `Notion:notion-update-page`

## Working Style

- Favor natural-language requests over command-style interactions.
- When the user says things like "agrega esta idea", "refina esta", or "pasala a repo", use the founder workflow skill plus the Notion MCP directly.
- Keep the final Notion output compact, structured, and useful for later decision-making.
