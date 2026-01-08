# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## What This Is

**YokeFlow** - An autonomous AI development platform that uses Claude to build complete applications over multiple sessions.

**Status**: Production Ready - v1.2.0 (December 2025)

**Architecture**: API-first platform with FastAPI + Next.js Web UI + PostgreSQL + MCP task management

**Workflow**: Opus plans roadmap (Session 0) → Sonnet implements features (Sessions 1+)

## How to Work on YokeFlow (IMPORTANT)

When implementing features or fixing bugs in YokeFlow itself, follow this workflow:

### 1. Consult Domain Expertise First
Before writing code, read the relevant expertise files:
```
.claude/commands/experts/{domain}/expertise.yaml
```
Domains: `backend`, `frontend`, `database`, `orchestration`, `mcp`, `testing`

### 2. Use Commands for Structured Work
- `/plan <feature>` → Generate spec in `specs/`
- `/build <spec>` → Implement (parallel capable)
- `/review` → Risk-tiered code review
- `/fix <review>` → Auto-fix issues

### 3. Spawn Sub-Agents for Parallel Work
```
.claude/agents/
├── planner-agent.md   (Opus - planning)
├── build-agent.md     (Sonnet - implementation)
├── scout-agent.md     (Haiku - investigation)
├── reviewer-agent.md  (Sonnet - review)
└── merge-agent.md     (Sonnet - merging)
```

### 4. Update Expertise After Implementation
If you discover new patterns, update the relevant `expertise.yaml`.

### 5. Use Output Directories
- `specs/` - Implementation plans
- `reviews/` - Code review reports
- `fix-reports/` - Fix reports
- `build-reports/` - Build reports

**Run `/prime` to load full context at session start.**

---

## Core Workflow (Generated Projects)

**Session 0 (Initialization)**: Reads `app_spec.txt` → Creates epics/tasks/tests in PostgreSQL → Runs `init.sh`

**Sessions 1+ (Coding)**: Get next task → Implement → Browser verify (with Playwright) → Update database → Git commit → Auto-continue

**Key Files**:
- `core/orchestrator.py` - Session lifecycle
- `core/agent.py` - Agent loop
- `core/database.py` - PostgreSQL abstraction (async)
- `api/main.py` - REST API + WebSocket
- `core/observability.py` - Session logging (JSONL + TXT)
- `core/security.py` - Blocklist validation
- `prompts/` - Agent instructions


## Database

**Schema**: PostgreSQL with 3-tier hierarchy: `epics` → `tasks` → `tests`

**Key tables**: `projects`, `epics`, `tasks`, `tests`, `sessions`, `session_quality_checks`

**Key views**: `v_next_task`, `v_progress`, `v_epic_progress`

**Access**: Use `core/database.py` abstraction (async/await). See `schema/postgresql/` for DDL.

## MCP Tools

The `mcp-task-manager/` provides 15+ tools (prefix: `mcp__task-manager__`):

**Query**: `task_status`, `get_next_task`, `list_epics`, `get_epic`, `list_tasks`, `get_task`, `list_tests`

**Update**: `update_task_status`, `start_task`, `update_test_result`

**Create**: `create_epic`, `create_task`, `create_test`, `expand_epic`, `log_session`

Must build before use: `cd mcp-task-manager && npm run build`

## Configuration

**Priority**: Web UI settings > Config file (`.yokeflow.yaml`) > Defaults

**Key settings**:
- `models.initializer` / `models.coding` - Override default Opus/Sonnet models
- `timing.auto_continue_delay` - Seconds between sessions (default 3)
- `project.max_iterations` - Limit session count (null = unlimited)

## Security

**Blocklist approach**: Allows dev tools (npm, git, curl), blocks dangerous commands (rm, sudo, apt)

Edit `core/security.py` `BLOCKED_COMMANDS` to modify. Safe in Docker containers.

## Project Structure

```
yokeflow/
├── core/                    # Core platform modules
│   ├── orchestrator.py      # Session lifecycle management
│   ├── agent.py             # Agent loop and session logic
│   ├── database.py          # PostgreSQL abstraction (async)
│   ├── database_connection.py  # Connection pooling
│   ├── client.py            # Claude SDK client setup
│   ├── config.py            # Configuration management
│   ├── observability.py     # Session logging (JSONL + TXT)
│   ├── security.py          # Blocklist validation
│   ├── progress.py          # Progress tracking
│   ├── prompts.py           # Prompt loading
│   ├── reset.py             # Project reset logic
│   ├── sandbox_manager.py   # Docker sandbox management
│   └── sandbox_hooks.py     # Sandbox hooks
├── review/                  # Review system modules
│   ├── review_client.py     # Automated deep reviews (Phase 2)
│   ├── review_metrics.py    # Quality metrics (Phase 1)
│   └── prompt_improvement_analyzer.py  # Prompt optimization (Phase 4)
├── api/                     # FastAPI REST API
├── web-ui/                  # Next.js Web UI
├── scripts/                 # Utility tools (task_status, reset_project, cleanup_*)
├── mcp-task-manager/        # MCP server (TypeScript)
├── prompts/                 # Agent instructions (initializer, coding, review)
├── schema/postgresql/       # Database DDL
├── tests/                   # Test suites
├── docs/                    # Documentation
└── generations/             # Generated projects
```

## Domain Expertise & Skills (.claude/)

YokeFlow uses the ADWS pattern for domain expertise and Claude SDK skills:

```
.claude/
├── settings.json              # Project settings and thresholds
├── skills/                    # Native Claude SDK skills
│   ├── implement-feature/     # Feature implementation skill
│   ├── review-code/           # Code review skill
│   └── debug-issue/           # Debugging skill
└── commands/experts/          # Domain expertise
    ├── backend/               # FastAPI, async Python
    ├── frontend/              # Next.js, React, TypeScript
    ├── database/              # PostgreSQL, asyncpg
    ├── orchestration/         # Agent management, sessions
    ├── mcp/                   # Model Context Protocol
    └── testing/               # pytest, async tests
```

**Each domain expert contains**:
- `expertise.yaml` - Patterns, anti-patterns, stack info
- `question.md` - How to query this expert
- `self-improve.md` - When/how to update expertise

**Expertise Workflow**:
1. Route task to appropriate domain expert
2. Consult `expertise.yaml` for patterns
3. Implement following established patterns
4. If new pattern discovered, update `expertise.yaml`
5. When confidence > 0.8 and usage > 10, generate skill

**Skills vs Expertise**:
- **Expertise**: Domain knowledge that evolves (yaml files)
- **Skills**: Condensed, actionable procedures (SKILL.md)

## Key Design Decisions

**PostgreSQL**: Production-ready, async operations, JSONB metadata, UUID-based IDs

**Orchestrator**: Decouples session management, enables API control, foundation for job queues

**MCP over Shell**: Protocol-based, structured I/O, no injection risks, language-agnostic

**Tasks Upfront**: Complete visibility from day 1, accurate progress tracking, user can review roadmap

**Dual Models**: Opus for planning (comprehensive), Sonnet for coding (fast + cheap)

**Blocklist Security**: Agent autonomy with safety, designed for containers

## Troubleshooting

**MCP server failed**: Run `cd mcp-task-manager && npm run build`

**Database error**: Ensure PostgreSQL running (`docker-compose up -d`), check DATABASE_URL in `.env`

**Command blocked**: Check `core/security.py` BLOCKED_COMMANDS list

**Agent stuck**: Check logs in `generations/[project]/logs/`, run with `--verbose`

**Web UI no projects**: Ensure PostgreSQL running, verify API connection

## Testing

```bash
python tests/test_security.py           # Security validation (64 tests)
python tests/test_mcp.py                 # MCP integration
python tests/test_database_abstraction.py # Database layer
python tests/test_orchestrator.py        # Orchestrator
```

## Important Files

**Core**: `core/orchestrator.py`, `core/agent.py`, `core/database.py`, `core/observability.py`, `core/security.py`, `core/config.py`

**Prompts**: `prompts/initializer_prompt.md`, `prompts/coding_prompt.md`, `prompts/review_prompt.md`

**API**: `api/main.py`, `web-ui/src/lib/api.ts`

**MCP**: `mcp-task-manager/src/index.ts`

**Schema**: `schema/postgresql/schema.sql`

**Docs**: `docs/developer-guide.md`, `docs/review-system.md`, `README.md`, `TODO-FUTURE.md` (post-release enhancements)

**Review System**:
- Phase 1: `review/review_metrics.py` - Quick checks (zero-cost) ✅ Production Ready
- Phase 2: `review/review_client.py` - Deep reviews (AI-powered) ✅ Production Ready
- Phase 3: `web-ui/src/components/QualityDashboard.tsx` - UI dashboard ✅ Production Ready
- Phase 4: `review/prompt_improvement_analyzer.py` - Prompt improvements ✅ **RESTORED** (feature branch)

## Recent Changes

**January 6, 2026**:
- ✅ **ADWS Pattern Adopted**: Domain expertise structure in `.claude/commands/experts/`
- ✅ **Native Skills Created**: `implement-feature`, `review-code`, `debug-issue` skills
- ✅ **6 Domain Experts**: backend, frontend, database, orchestration, mcp, testing
- ✅ **Parallel Execution v2 Roadmap**: 5 epics, 32 tasks for automatic parallel mode
- 🚧 **In Progress**: Phase 1-5 implementation for default parallel execution

**December 29, 2025 - v1.2.0 Release**:
- ✅ **Playwright Browser Automation**: Full browser testing within Docker containers
- ✅ **Docker Integration**: Headless Chromium runs inside containers without port forwarding
- ✅ **Visual Verification**: Screenshots and page snapshots for testing web applications
- ✅ **Codebase Cleanup**: Removed experimental files from Playwright development
- ✅ **Documentation Update**: Consolidated Playwright docs into main Docker guide

**December 27, 2025 - v1.1.0 Release**:
- ✅ **Version 1.1.0**: Database schema improvements, migration scripts removed
- ✅ **Fresh Install Required**: Schema changes require clean database installation
- ✅ **Migration Scripts Removed**: All migration-related scripts and directories cleaned up
- ⚠️ **Breaking Change**: Existing v1.0.0 databases cannot be migrated - fresh install required

**December 24, 2025**:
- ✅ **Prompt Improvements Restored**: Phase 4 of Review System re-enabled in feature branch
- ✅ **Backend Components**: Restored `prompt_improvement_analyzer.py` and API routes
- ✅ **Web UI Pages**: Restored `/prompt-improvements` dashboard and detail views
- ✅ **Integration Complete**: Connected with existing Review System (Phases 1-3)

**December 2025**:
- ✅ Review system Phases 1-3 complete (quick checks, deep reviews, UI dashboard)
- ✅ Prompt Improvement System (Phase 4) - Archived for post-release refactoring
- ✅ PostgreSQL migration complete (UUID-based, async, connection pooling)
- ✅ API-first platform with Next.js Web UI
- ✅ Project completion tracking with celebration UI
- ✅ Coding prompt improvements (browser verification enforcement, bash_docker mandate)
- 🚀 **YokeFlow Transition**: Rebranding and repository migration in progress
- ✅ **Code Organization**: Refactored to `core/` and `review/` modules for better structure
- ✅ **Pre-Release Cleanup**: Experimental features archived, TODO split into pre/post-release

**Key Evolution**:
- Shell scripts → MCP (protocol-based task management)
- JSONL + TXT dual logging (human + machine readable)
- Autonomous Coding → **YokeFlow** (production-ready platform)

## Philosophy

**Greenfield Development**: Builds new applications from scratch, not modifying existing codebases.

**Workflow**: Create `app_spec.txt` → Initialize roadmap → Review → Autonomous coding → Completion verification

**Core Principle**: One-shot success. Improve the agent system itself rather than fixing generated apps.

## Release Status

**Current State**: Production Ready - v1.2.0

**Release Highlights**:
- ✅ **Complete Platform**: All 7 phases of development complete
- ✅ **Playwright Integration**: Browser automation within Docker containers
- ✅ **Production Tested**: 31-session validation, 64 security tests passing
- ✅ **Full Documentation**: Comprehensive guides, API docs, contribution guidelines
- ✅ **Quality System**: Automated reviews, dashboard, trend tracking
- ✅ **Professional Repository**: CONTRIBUTING.md, SECURITY.md, CI/CD

**Post-Release Roadmap**:
- See `TODO-FUTURE.md` for planned enhancements
- Per-user authentication, prompt improvements, E2B integration, and more

---

**For detailed documentation, see `docs/` directory. Originally forked from Anthropic's autonomous coding demo, now evolved into YokeFlow with extensive enhancements.**
