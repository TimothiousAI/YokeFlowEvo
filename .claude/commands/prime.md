# Context Priming Command

Read these files to understand the autonomous coding agent system:

## Essential Context

1. **CLAUDE.md** - Quick reference overview (START HERE!)
   - What this project is and why it exists
   - Key features
   - Architecture overview
   - Common commands and workflows

2. **README.md** - User guide
   - Installation and setup
   - Usage examples
   - Project structure

## YokeFlow Development Workflow (CRITICAL)

When working on YokeFlow itself, you MUST follow this structured approach:

### Before Writing Any Code

1. **Identify affected domains**: backend, frontend, database, orchestration, mcp, testing
2. **Read domain expertise**:
   ```
   .claude/commands/experts/{domain}/expertise.yaml
   ```
3. **Check for existing patterns** to follow and anti-patterns to avoid

### For Non-Trivial Features

Use the command workflow:

```
/plan <feature>     → Generate detailed spec
/build <spec>       → Implement (can be parallel)
/review             → Risk-tiered code review
/fix <review>       → Auto-fix issues
```

### For Parallel Execution

Spawn sub-agents in isolated worktrees:

| Agent | Model | Use For |
|-------|-------|---------|
| planner-agent | Opus | Feature planning |
| build-agent | Sonnet | File implementation |
| scout-agent | Haiku | Read-only investigation |
| reviewer-agent | Sonnet | Code review |
| merge-agent | Sonnet | Worktree merging |

Agent definitions: `.claude/agents/*.md`

### After Implementation

1. **Update expertise** if new patterns discovered
2. **Use output directories**:
   - `specs/` - Plans
   - `reviews/` - Review reports
   - `fix-reports/` - Fix reports
   - `build-reports/` - Build reports

## Current Roadmap

Check `yokeflow-enhancement` project in database for active epics:
- Phase 1: Execution Plan Engine (Epic 150)
- Phase 2: Auto Parallel Orchestration (Epic 151)
- Phase 3: Expertise File System (Epic 152)
- Phase 4: Project Bootstrapping (Epic 153)
- Phase 5: Kanban UI (Epic 154)

## After Reading

You should understand:

### Core System
- **Purpose**: Autonomous coding agent using Claude to build complete applications
- **Architecture**: API-first platform
  - FastAPI REST API with WebSocket (port 8000)
  - Next.js Web UI (TypeScript/React, port 3000)
  - PostgreSQL database with async operations
  - Agent orchestrator (decoupled session management)
  - MCP (Model Context Protocol) for task operations

### Two-Phase Workflow (for generated projects)
- **Session 0 (Initialization, Opus)**: Creates complete roadmap (epics → tasks → tests)
- **Sessions 1+ (Coding, Sonnet)**: Implements tasks with browser verification
- **Review System**: Production-ready quality monitoring (all 3 phases complete)

### Development Workflow (for YokeFlow itself)
- **Consult expertise** before coding
- **Use /plan → /build → /review → /fix** for structured work
- **Spawn sub-agents** for parallel execution
- **Update expertise** after implementation

### Key Features (All Production Ready)
- **Observability**: Dual logging (JSONL + TXT)
- **Task Management**: PostgreSQL database with async operations, 15+ MCP tools
- **Quality System**: Automated reviews, quality dashboard, trend tracking
- **Project Management**: completion tracking, environment UI
- **Real-time Updates**: WebSocket live progress, session logs viewer
- **Domain Expertise**: 6 domains with patterns and anti-patterns
- **Sub-Agents**: 5 specialized agents for parallel work
- **Commands**: /plan, /build, /review, /fix, /parallel, /orchestrate

### Platform Capabilities
- **API Usage**: FastAPI server with REST endpoints + WebSocket (port 8000)
- **Web UI**: Next.js interface with 4 tabs (Overview/History/Quality/Logs, port 3000)
- **Quality Monitoring**: Automated deep reviews, quality dashboard, trend charts

### How to Extend
- Add API endpoints (api/main.py) - consult `backend/expertise.yaml`
- Enhance Web UI (web-ui/src/) - consult `frontend/expertise.yaml`
- Improve prompts (prompts/ directory)
- Add tests (tests/ directory) - consult `testing/expertise.yaml`
