# Skill Registry — voice-agent

Generated: 2026-04-04
Project: voice-agent

## Convention Files

| File | Level | Purpose |
|------|-------|---------|
| `~/.claude/CLAUDE.md` | user | Global rules, personality, language, SDD config |

## User Skills (`~/.claude/skills/`)

| Skill | Trigger Context |
|-------|----------------|
| `ai-sdk` | Code using Anthropic SDK, AI agent building, generateText/streamText |
| `branch-pr` | Creating pull requests, preparing changes for review |
| `find-skills` | User asks how to do something, looking for installable capabilities |
| `go-testing` | Go tests, Bubbletea TUI testing, teatest |
| `issue-creation` | Creating GitHub issues, bug reports, feature requests |
| `judgment-day` | Adversarial dual review ("judgment day", "doble review", "juzgar") |
| `remotion-best-practices` | Remotion video creation in React |
| `sdd-apply` | Implementing tasks from a change (SDD phase) |
| `sdd-archive` | Closing a completed change (SDD phase) |
| `sdd-design` | Technical design document (SDD phase) |
| `sdd-explore` | Exploring ideas before a change (SDD phase) |
| `sdd-init` | Initializing SDD context in a project |
| `sdd-propose` | Creating a change proposal (SDD phase) |
| `sdd-spec` | Writing specifications (SDD phase) |
| `sdd-tasks` | Breaking a change into tasks (SDD phase) |
| `sdd-verify` | Validating implementation against specs (SDD phase) |
| `skill-creator` | Creating or improving skills, running evals |
| `web-design-guidelines` | UI review, accessibility audit, UX check |

## Project Skills (`.agents/skills/`)

| Skill | Trigger Context |
|-------|----------------|
| `voice-agent-workspace` | Saving decisions, tasks, learnings, or costs to Notion for the voice agent project |

## Compact Rules

### voice-agent-workspace
When working in this project and making decisions, discoveries, or agreeing on tasks:
1. Read `workspace/notion-context.md` for Notion database IDs before any Notion operation
2. Save tasks → Tareas DB | discoveries → Aprendizajes DB | tools → Stack & Herramientas DB | costs → Inversión/Gastos DB | architecture decisions → Decisiones de Arquitectura page
3. Always populate the `Detalle` field in Aprendizajes — title alone has no value
4. Trigger: any decision made, tool evaluated, task agreed, experiment completed, or cost incurred

### sdd (all phases)
- Strict TDD Mode: CONFIGURED enabled, UNAVAILABLE until pytest is added to the project
- Persistence: engram
- When test runner exists: write tests before implementation
- Engram topic keys: `sdd-init/voice-agent`, `sdd/{change}/explore|proposal|spec|design|tasks|apply-progress|verify-report|archive-report`
