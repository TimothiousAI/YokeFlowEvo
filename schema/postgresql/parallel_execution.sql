-- =============================================================================
-- YokeFlow Parallel Execution Schema Extensions
-- =============================================================================
-- Version: 1.0.0
-- Date: January 5, 2026
--
-- This schema extends the base YokeFlow schema to support:
-- - Task and epic dependencies for parallel execution ordering
-- - Parallel batch tracking for concurrent task execution
-- - Git worktree isolation for parallel agent sessions
-- - Agent cost tracking for budget management
-- - Expertise accumulation for self-learning system
--
-- To apply this schema:
--   psql -U yokeflow -d yokeflow < schema/postgresql/parallel_execution.sql
-- =============================================================================

-- =============================================================================
-- TASK AND EPIC DEPENDENCIES
-- =============================================================================

-- Add dependency tracking to tasks table
ALTER TABLE tasks
ADD COLUMN IF NOT EXISTS depends_on INTEGER[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS dependency_type VARCHAR(20) DEFAULT 'hard';

-- Add dependency tracking to epics table
ALTER TABLE epics
ADD COLUMN IF NOT EXISTS depends_on INTEGER[] DEFAULT '{}';

-- Create indexes for dependency queries
CREATE INDEX IF NOT EXISTS idx_tasks_depends_on ON tasks USING GIN (depends_on);
CREATE INDEX IF NOT EXISTS idx_epics_depends_on ON epics USING GIN (depends_on);

COMMENT ON COLUMN tasks.depends_on IS 'Array of task IDs that must be completed before this task can start';
COMMENT ON COLUMN tasks.dependency_type IS 'Type of dependency: "hard" (blocking) or "soft" (non-blocking)';
COMMENT ON COLUMN epics.depends_on IS 'Array of epic IDs that must be completed before this epic can start';

-- =============================================================================
-- PARALLEL BATCHES
-- =============================================================================

-- Track parallel execution batches
CREATE TABLE IF NOT EXISTS parallel_batches (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    batch_number INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    task_ids INTEGER[] DEFAULT '{}',

    -- Timestamps
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_batch_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT valid_batch_number CHECK (batch_number > 0),
    UNIQUE(project_id, batch_number)
);

CREATE INDEX IF NOT EXISTS idx_parallel_batches_project ON parallel_batches(project_id);
CREATE INDEX IF NOT EXISTS idx_parallel_batches_status ON parallel_batches(status);
CREATE INDEX IF NOT EXISTS idx_parallel_batches_batch_number ON parallel_batches(project_id, batch_number);

COMMENT ON TABLE parallel_batches IS 'Tracks parallel execution batches. Each batch contains tasks that can run concurrently.';
COMMENT ON COLUMN parallel_batches.batch_number IS 'Sequential batch number. Batch N must complete before batch N+1 starts.';
COMMENT ON COLUMN parallel_batches.task_ids IS 'Array of task IDs in this batch that can execute in parallel';

-- =============================================================================
-- GIT WORKTREES
-- =============================================================================

-- Track git worktrees for isolated parallel execution
CREATE TABLE IF NOT EXISTS worktrees (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    epic_id INTEGER NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    branch_name VARCHAR(255) NOT NULL,
    worktree_path TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    merge_commit VARCHAR(40),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    merged_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT valid_worktree_status CHECK (status IN ('active', 'merged', 'conflict', 'abandoned', 'cleanup')),
    UNIQUE(project_id, epic_id)
);

CREATE INDEX IF NOT EXISTS idx_worktrees_project ON worktrees(project_id);
CREATE INDEX IF NOT EXISTS idx_worktrees_epic ON worktrees(epic_id);
CREATE INDEX IF NOT EXISTS idx_worktrees_status ON worktrees(status);
CREATE INDEX IF NOT EXISTS idx_worktrees_branch ON worktrees(branch_name);

COMMENT ON TABLE worktrees IS 'Tracks git worktrees for isolated parallel task execution. One worktree per epic.';
COMMENT ON COLUMN worktrees.status IS 'Worktree lifecycle: active (in use), merged (successfully merged to main), conflict (merge conflicts), abandoned (not merged), cleanup (removed)';
COMMENT ON COLUMN worktrees.merge_commit IS 'SHA of the merge commit when worktree is merged to main';

-- =============================================================================
-- AGENT COSTS
-- =============================================================================

-- Track agent execution costs for budget management
CREATE TABLE IF NOT EXISTS agent_costs (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,

    -- Model and token usage
    model VARCHAR(50) NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0,

    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_tokens CHECK (input_tokens >= 0 AND output_tokens >= 0),
    CONSTRAINT valid_cost CHECK (cost_usd >= 0)
);

CREATE INDEX IF NOT EXISTS idx_agent_costs_project ON agent_costs(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_costs_session ON agent_costs(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_costs_task ON agent_costs(task_id);
CREATE INDEX IF NOT EXISTS idx_agent_costs_model ON agent_costs(model);
CREATE INDEX IF NOT EXISTS idx_agent_costs_created ON agent_costs(created_at DESC);

COMMENT ON TABLE agent_costs IS 'Tracks LLM API costs per task/session for budget management and optimization';
COMMENT ON COLUMN agent_costs.model IS 'Model used: haiku, sonnet, opus, etc.';

-- =============================================================================
-- EXPERTISE FILES (SELF-LEARNING SYSTEM)
-- =============================================================================

-- Store accumulated expertise by domain
CREATE TABLE IF NOT EXISTS expertise_files (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    domain VARCHAR(50) NOT NULL,
    content JSONB DEFAULT '{}',
    version INTEGER DEFAULT 1,
    line_count INTEGER DEFAULT 0,

    -- Timestamps
    validated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_domain CHECK (domain IN ('database', 'api', 'frontend', 'testing', 'security', 'deployment', 'general')),
    CONSTRAINT valid_version CHECK (version > 0),
    CONSTRAINT valid_line_count CHECK (line_count >= 0),
    UNIQUE(project_id, domain)
);

CREATE INDEX IF NOT EXISTS idx_expertise_project ON expertise_files(project_id);
CREATE INDEX IF NOT EXISTS idx_expertise_domain ON expertise_files(domain);
CREATE INDEX IF NOT EXISTS idx_expertise_content ON expertise_files USING GIN (content);

COMMENT ON TABLE expertise_files IS 'Stores accumulated expertise per domain for self-learning system';
COMMENT ON COLUMN expertise_files.content IS 'JSONB structure: {core_files: [], patterns: [], techniques: [], learnings: []}';
COMMENT ON COLUMN expertise_files.line_count IS 'Approximate line count to enforce MAX_EXPERTISE_LINES limit (default 1000)';

-- Track expertise updates for audit trail
CREATE TABLE IF NOT EXISTS expertise_updates (
    id SERIAL PRIMARY KEY,
    expertise_id INTEGER NOT NULL REFERENCES expertise_files(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    change_type VARCHAR(20) NOT NULL,
    summary TEXT NOT NULL,
    diff TEXT,

    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_change_type CHECK (change_type IN ('learned', 'validated', 'pruned', 'self_improved'))
);

CREATE INDEX IF NOT EXISTS idx_expertise_updates_expertise ON expertise_updates(expertise_id);
CREATE INDEX IF NOT EXISTS idx_expertise_updates_session ON expertise_updates(session_id);
CREATE INDEX IF NOT EXISTS idx_expertise_updates_type ON expertise_updates(change_type);
CREATE INDEX IF NOT EXISTS idx_expertise_updates_created ON expertise_updates(created_at DESC);

COMMENT ON TABLE expertise_updates IS 'Audit trail of expertise changes for transparency and rollback';
COMMENT ON COLUMN expertise_updates.change_type IS 'Type: learned (from session), validated (pruning), pruned (removed), self_improved (from codebase scan)';

-- =============================================================================
-- VIEWS FOR PARALLEL EXECUTION
-- =============================================================================

-- Project costs aggregated by model
CREATE OR REPLACE VIEW v_project_costs AS
SELECT
    ac.project_id,
    p.name as project_name,
    ac.model,
    COUNT(*) as execution_count,
    SUM(ac.input_tokens) as total_input_tokens,
    SUM(ac.output_tokens) as total_output_tokens,
    SUM(ac.cost_usd) as total_cost_usd
FROM agent_costs ac
JOIN projects p ON ac.project_id = p.id
GROUP BY ac.project_id, p.name, ac.model
ORDER BY ac.project_id, total_cost_usd DESC;

COMMENT ON VIEW v_project_costs IS 'Cost breakdown by model for budget tracking and optimization';

-- Parallel execution progress
CREATE OR REPLACE VIEW v_parallel_progress AS
SELECT
    pb.project_id,
    p.name as project_name,
    pb.batch_number,
    pb.status as batch_status,
    CARDINALITY(pb.task_ids) as total_tasks,
    COUNT(CASE WHEN t.done = true THEN 1 END) as completed_tasks,
    COUNT(CASE WHEN t.done = false THEN 1 END) as pending_tasks,
    pb.started_at,
    pb.completed_at,
    EXTRACT(EPOCH FROM (COALESCE(pb.completed_at, NOW()) - pb.started_at)) as duration_seconds
FROM parallel_batches pb
JOIN projects p ON pb.project_id = p.id
LEFT JOIN tasks t ON t.id = ANY(pb.task_ids)
GROUP BY pb.id, pb.project_id, p.name, pb.batch_number, pb.status, pb.started_at, pb.completed_at
ORDER BY pb.project_id, pb.batch_number;

COMMENT ON VIEW v_parallel_progress IS 'Real-time parallel batch execution progress for UI dashboards';

-- Worktree status overview
CREATE OR REPLACE VIEW v_worktree_status AS
SELECT
    w.id as worktree_id,
    w.project_id,
    p.name as project_name,
    w.epic_id,
    e.name as epic_name,
    w.branch_name,
    w.worktree_path,
    w.status,
    w.merge_commit,
    w.created_at,
    w.merged_at,
    EXTRACT(EPOCH FROM (COALESCE(w.merged_at, NOW()) - w.created_at)) as lifetime_seconds
FROM worktrees w
JOIN projects p ON w.project_id = p.id
JOIN epics e ON w.epic_id = e.id
ORDER BY w.project_id, w.created_at DESC;

COMMENT ON VIEW v_worktree_status IS 'Worktree lifecycle tracking for parallel execution monitoring';

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Update expertise_files.updated_at on modification
CREATE OR REPLACE FUNCTION update_expertise_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_expertise_files_updated_at
    BEFORE UPDATE ON expertise_files
    FOR EACH ROW
    EXECUTE FUNCTION update_expertise_updated_at();

-- =============================================================================
-- END OF PARALLEL EXECUTION SCHEMA
-- =============================================================================
