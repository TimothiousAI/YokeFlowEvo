# Parallel-First Epic Design

## Problem Statement

Current epic creation is **feature-centric**:
- "Core Chat Interface" (all layers for chat)
- "Settings & Customization" (all layers for settings)
- "Performance & Polish" (optimization across all)

This creates **implicit dependencies** - you can't polish before building, settings might depend on core features, etc. The parallel executor can't safely run these in parallel.

## Proposed Solution: Layer-Centric Epics

Design epics around **architectural layers/domains** that can truly work in parallel:

```
┌─────────────────────────────────────────────────────────────┐
│                    PARALLEL EXECUTION                        │
├─────────────┬─────────────┬─────────────┬─────────────┬─────┤
│  Database   │  Backend    │  Frontend   │  Agents/AI  │ ... │
│  Layer      │  API Layer  │  UI Layer   │  Layer      │     │
├─────────────┼─────────────┼─────────────┼─────────────┼─────┤
│ - Schema    │ - Endpoints │ - Components│ - Prompts   │     │
│ - Models    │ - Services  │ - Pages     │ - Tools     │     │
│ - Migrations│ - Auth      │ - State     │ - Workflows │     │
│ - Seeds     │ - Validation│ - Styling   │ - Memory    │     │
└─────────────┴─────────────┴─────────────┴─────────────┴─────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 SEQUENTIAL (AFTER ALL ABOVE)                 │
├─────────────────────────────────────────────────────────────┤
│  Integration Epic: Wire layers together, E2E tests          │
├─────────────────────────────────────────────────────────────┤
│  Polish Epic: Performance, UX refinement, edge cases        │
└─────────────────────────────────────────────────────────────┘
```

## How Real Teams Work

This mirrors how professional dev teams operate:

| Team | Works On | Can Parallelize With |
|------|----------|---------------------|
| Database/Data Team | Schema, migrations, models | All (works from spec) |
| Backend Team | API endpoints, business logic | Frontend (uses API contracts) |
| Frontend Team | UI components, state management | Backend (uses API contracts) |
| AI/ML Team | Prompts, agent logic, tools | All (uses interface contracts) |
| DevOps Team | Infrastructure, CI/CD | All (independent) |

**Key Insight**: Teams work in parallel because they agree on **contracts/interfaces** upfront:
- API contracts (OpenAPI spec)
- Database schema (ERD)
- Component props (TypeScript interfaces)
- Event formats (message schemas)

## Phase 1: App Spec Analysis

Before creating epics, the initializer should analyze the app spec to identify:

### 1.1 Architectural Layers Present

```yaml
layers_detected:
  database:
    present: true
    technologies: [PostgreSQL, Prisma]
    entities: [User, Chat, Message, Settings]

  backend:
    present: true
    technologies: [FastAPI, Python]
    features: [REST API, WebSocket, Auth]

  frontend:
    present: true
    technologies: [Next.js, React, TypeScript]
    features: [Chat UI, Settings Panel, Dashboard]

  agents:
    present: true
    technologies: [Claude SDK, MCP]
    features: [Chat Agent, Code Agent, Research Agent]

  infrastructure:
    present: false  # Not in this app spec
```

### 1.2 Cross-Layer Features

Identify features that span multiple layers:

```yaml
cross_layer_features:
  - name: "User Authentication"
    layers: [database, backend, frontend]
    integration_points:
      - "User table schema"
      - "Auth API endpoints"
      - "Login/Register UI"

  - name: "Real-time Chat"
    layers: [database, backend, frontend, agents]
    integration_points:
      - "Message table schema"
      - "WebSocket endpoint"
      - "Chat component"
      - "AI response generation"
```

## Phase 2: Interface Contract Definition

Before any coding, define contracts between layers:

### 2.1 Database Schema Contract

```sql
-- contracts/database-schema.sql
-- This is the agreed-upon schema that all layers code against

CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    content TEXT NOT NULL,
    role VARCHAR(20) NOT NULL, -- 'user' | 'assistant'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2.2 API Contract

```yaml
# contracts/api-spec.yaml
openapi: 3.0.0
paths:
  /api/messages:
    post:
      summary: Send a message
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                content: { type: string }
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Message'
```

### 2.3 Component Interface Contract

```typescript
// contracts/component-props.ts
// Frontend components code against these interfaces

interface ChatMessageProps {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
}

interface ChatInputProps {
  onSend: (message: string) => Promise<void>;
  disabled?: boolean;
  placeholder?: string;
}
```

## Phase 3: Epic Structure

### 3.1 Parallel Epics (Run Simultaneously)

Each epic works against the contracts, not each other:

```yaml
epics:
  - id: 1
    name: "Database Layer"
    type: "parallel"  # Can run with other parallel epics
    domain: "database"
    contract_produces:
      - "contracts/database-schema.sql"
    tasks:
      - "Create database schema migrations"
      - "Implement User model with Prisma"
      - "Implement Message model"
      - "Create seed data for development"
      - "Add database indexes for performance"

  - id: 2
    name: "Backend API Layer"
    type: "parallel"
    domain: "backend"
    contract_consumes:
      - "contracts/database-schema.sql"  # Codes against schema
    contract_produces:
      - "contracts/api-spec.yaml"
    tasks:
      - "Set up FastAPI application structure"
      - "Implement user authentication endpoints"
      - "Implement message CRUD endpoints"
      - "Add WebSocket support for real-time"
      - "Implement rate limiting middleware"

  - id: 3
    name: "Frontend UI Layer"
    type: "parallel"
    domain: "frontend"
    contract_consumes:
      - "contracts/api-spec.yaml"  # Codes against API spec
      - "contracts/component-props.ts"
    tasks:
      - "Set up Next.js application structure"
      - "Create ChatMessage component"
      - "Create ChatInput component"
      - "Create ChatContainer with message list"
      - "Implement API client service"
      - "Add WebSocket connection for real-time"

  - id: 4
    name: "AI Agent Layer"
    type: "parallel"
    domain: "agents"
    contract_consumes:
      - "contracts/api-spec.yaml"
    tasks:
      - "Create chat agent with Claude SDK"
      - "Implement conversation memory"
      - "Add tool definitions for agent"
      - "Create prompt templates"
```

### 3.2 Sequential Epics (Run After Parallel Complete)

```yaml
  - id: 5
    name: "Integration Layer"
    type: "sequential"
    depends_on: [1, 2, 3, 4]  # All parallel epics
    domain: "integration"
    tasks:
      - "Wire frontend to backend API"
      - "Connect backend to database"
      - "Integrate AI agent with chat flow"
      - "End-to-end testing"
      - "Fix integration issues"

  - id: 6
    name: "Polish & Optimization"
    type: "sequential"
    depends_on: [5]  # After integration
    domain: "polish"
    tasks:
      - "Performance optimization"
      - "Error handling improvements"
      - "Loading states and UX polish"
      - "Edge case handling"
      - "Final testing and bug fixes"
```

## Phase 4: Initializer Prompt Changes

### Current Prompt Issue

The current initializer prompt doesn't guide toward layer-based thinking. It allows feature-centric epics that can't parallelize.

### Proposed Prompt Addition

```markdown
## Epic Design for Parallel Execution

When creating epics, you MUST design for parallel execution:

### Step 1: Identify Architectural Layers

Analyze the app spec and identify which layers are needed:
- **Database Layer**: Schema, models, migrations, seeds
- **Backend Layer**: API endpoints, services, middleware, auth
- **Frontend Layer**: Components, pages, state management, styling
- **Agent/AI Layer**: Prompts, tools, workflows, memory
- **Infrastructure Layer**: Docker, CI/CD, deployment (if applicable)

### Step 2: Create One Epic Per Layer

Each layer becomes ONE epic that can run in parallel:

CORRECT (Layer-centric):
- Epic 1: "Database Layer" - All database work
- Epic 2: "Backend API Layer" - All API work
- Epic 3: "Frontend UI Layer" - All UI work
- Epic 4: "AI Agent Layer" - All AI work

INCORRECT (Feature-centric):
- Epic 1: "Chat Feature" - DB + API + UI + AI for chat
- Epic 2: "Settings Feature" - DB + API + UI for settings
- Epic 3: "Polish" - Everything

### Step 3: Define Interface Contracts FIRST

Before coding tasks, create contract tasks:
1. "Define database schema contract" (what tables/columns)
2. "Define API contract" (what endpoints, request/response shapes)
3. "Define component interface contract" (what props components need)

### Step 4: Tasks Code Against Contracts, Not Each Other

Each task in a layer epic should:
- Read from contract files to understand interfaces
- Implement against the contract
- NOT depend on actual implementation in other layers

Example Backend Task:
"Implement POST /api/messages endpoint per api-spec.yaml contract"

Example Frontend Task:
"Create ChatMessage component per component-props.ts contract"

### Step 5: Add Integration Epic LAST

After all parallel layer epics, add:
- Epic N-1: "Integration" - Wire everything together, depends on all parallel epics
- Epic N: "Polish" - Optimization and refinement, depends on integration
```

## Phase 5: Database Schema Changes

Add epic dependency tracking:

```sql
-- Add to epics table
ALTER TABLE epics ADD COLUMN epic_type VARCHAR(20) DEFAULT 'parallel';
-- 'parallel' = can run with other parallel epics
-- 'sequential' = must wait for depends_on epics

ALTER TABLE epics ADD COLUMN depends_on_epics INTEGER[] DEFAULT '{}';
-- Array of epic IDs this epic depends on

ALTER TABLE epics ADD COLUMN domain VARCHAR(50);
-- 'database', 'backend', 'frontend', 'agents', 'integration', 'polish'
```

## Phase 6: Execution Plan Builder Changes

Update `execution_plan.py` to respect epic dependencies:

```python
def build_plan(self, project_id: UUID) -> ExecutionPlan:
    # Load epics with their types and dependencies
    epics = await self.db.get_epics(project_id)

    # Group epics by dependency level
    parallel_epics = [e for e in epics if e['epic_type'] == 'parallel']
    sequential_epics = [e for e in epics if e['epic_type'] == 'sequential']

    # Sort sequential epics by depends_on (topological sort)
    sequential_epics = self._topological_sort(sequential_epics)

    # Create batches:
    # - Batch 0: All parallel epics (run together)
    # - Batch 1+: Sequential epics in order

    batches = []

    # All parallel epics in one batch
    if parallel_epics:
        parallel_batch = {
            'batch_id': 0,
            'epic_ids': [e['id'] for e in parallel_epics],
            'task_ids': flatten([e['task_ids'] for e in parallel_epics]),
            'can_parallel': True,
            'depends_on': []
        }
        batches.append(parallel_batch)

    # Sequential epics each get their own batch
    for i, epic in enumerate(sequential_epics):
        seq_batch = {
            'batch_id': i + 1,
            'epic_ids': [epic['id']],
            'task_ids': epic['task_ids'],
            'can_parallel': False,
            'depends_on': [0] if i == 0 else [i]  # Depends on previous
        }
        batches.append(seq_batch)

    return ExecutionPlan(batches=batches, ...)
```

## Example: YouTube AI Coach

Applying this to your youtube-ai-coach project:

### Current (Feature-Centric) - WRONG
```
Epic 1: Core Chat Interface (47 tasks) - FE+BE+DB+AI
Epic 2: Artifacts Panel UI (28 tasks) - FE+BE
Epic 3: Settings & Customization (42 tasks) - FE+BE+DB
Epic 4: Performance & Polish (30 tasks) - Everything
```
❌ Can't parallelize - implicit dependencies

### Proposed (Layer-Centric) - CORRECT
```
Epic 1: Database Layer (parallel)
  - Chat schema, User schema, Settings schema
  - All migrations, models, seeds

Epic 2: Backend API Layer (parallel)
  - Chat endpoints, Settings endpoints
  - WebSocket, Auth, Middleware

Epic 3: Frontend UI Layer (parallel)
  - Chat components, Settings components
  - Artifacts panel, Navigation

Epic 4: AI Agent Layer (parallel)
  - YouTube analysis agent
  - Chat response agent
  - Tool definitions

Epic 5: Integration (sequential, depends on 1-4)
  - Wire FE to BE
  - Wire BE to DB
  - Wire Agents to API
  - E2E tests

Epic 6: Polish (sequential, depends on 5)
  - Performance optimization
  - UX improvements
  - Edge cases
```
✅ Epics 1-4 run in TRUE parallel (different worktrees)
✅ Integration happens after all layers built
✅ Polish is always last

## Implementation Roadmap

1. **Update initializer prompt** with layer-centric guidance
2. **Add epic_type, depends_on_epics, domain to schema**
3. **Update execution plan builder** to respect epic dependencies
4. **Update UI** to show epic dependencies visually
5. **Test with new project** to validate parallel execution

## Migration for Existing Projects

For existing projects with feature-centric epics:
1. Can't easily migrate - epic structure is fundamental
2. Option: Add manual `depends_on_epics` to enforce ordering
3. Better: Re-initialize project with new prompt

## Conclusion

True parallel execution requires **designing for parallelism from the start**. The epics must be structured around architectural layers that can genuinely work independently, connected only by interface contracts. This is how real development teams achieve parallelism, and it's how YokeFlow should work.
