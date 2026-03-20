# Notion Workspace Context

This file tells agents where to find things in our Notion workspace. **Read this before searching Notion.**

## Teamspace

All project data lives in the **Agent AI** teamspace. If you can't see it, the user needs to invite you as a member.

## Databases

### Ideas Database

- **Location**: Agent AI teamspace
- **URL**: https://www.notion.so/a8ee2ffddc494d778c969d984c6c3386?v=7b8bdc5a70f4475eb15b22362788583d
- **Database ID**: `a8ee2ffddc494d778c969d984c6c3386`
- **Purpose**: Capture and track AI product ideas from raw capture to repo kickoff
- **Default schema**: See `templates/notion-ideas-database-schema.md`
- **Statuses**: Inbox → Shaping → Validating → Building → Paused → Dropped

### Other Databases

<!-- Add other databases here as they are created -->
<!-- Example:
### Tasks Database
- **Location**: Agent AI teamspace
- **Database ID**: `xxx`
- **Purpose**: Track implementation tasks
-->

## Pages

### Development & Roadmap

<!-- Add key pages here -->
<!-- Example:
- **Roadmap**: https://www.notion.so/xxx
- **Architecture Decisions**: https://www.notion.so/xxx
-->

## How Agents Should Use This

1. **When capturing ideas**: Always save to the Ideas database above. Don't create standalone pages unless the user explicitly asks.
2. **When searching**: Start by searching within the Agent AI teamspace, not the entire workspace.
3. **When unsure**: Ask the user which teamspace or database to target before creating anything.

## Adding New Resources

When you create a new database or important page in the Agent AI teamspace, add it here so other agents (and team members) can find it.
