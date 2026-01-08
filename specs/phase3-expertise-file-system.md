# Implementation Plan: Phase 3 - Expertise File System (ADWS Pattern)

## Task Description

Implement a hybrid expertise storage system where expertise is stored both in the database (for querying) and in files (for portability and Git versioning). This follows the ADWS pattern where domain knowledge lives in `.claude/commands/experts/{domain}/` directories.

## Objectives

- [ ] Create ExpertiseExporter to write DB expertise to files
- [ ] Create ExpertiseSyncService for bidirectional DB ↔ file sync
- [ ] Generate native Claude skills when expertise matures
- [ ] Update domain router to check files first
- [ ] Run export after each session with new learnings
- [ ] Make expertise Git-friendly (part of codebase)

## Relevant Files

| File | Purpose | Action |
|------|---------|--------|
| `core/learning/expertise_exporter.py` | Export DB expertise to files | Create |
| `core/learning/expertise_sync.py` | Bidirectional sync service | Create |
| `core/learning/skill_generator.py` | Generate native Claude skills | Create |
| `core/learning/expertise_manager.py` | Update routing logic | Modify |
| `core/orchestrator.py` | Hook export after sessions | Modify |

## Implementation Phases

### Batch 1 (No Dependencies - Can Run in Parallel)
- Create `core/learning/expertise_exporter.py`
- Create `core/learning/skill_generator.py`

### Batch 2 (Depends on Batch 1)
- Create `core/learning/expertise_sync.py`
- Update `core/learning/expertise_manager.py` with file routing
- Hook into orchestrator for post-session export

## File Specifications

---

### File: core/learning/expertise_exporter.py

**Purpose**: Export database expertise to file-based format in `.claude/commands/experts/{domain}/`.

**Requirements**:
- Export expertise content to `expertise.yaml`
- Generate `question.md` template for querying this domain
- Generate `self-improve.md` with conditions for self-improvement
- Include metadata (confidence, usage_count, last_updated)
- Handle incremental updates (only export if changed)

**Related Files**:
- `core/learning/expertise_manager.py` - Source of expertise data
- `.claude/commands/experts/` - Target directory structure

**Data Structures**:
```python
@dataclass
class ExportResult:
    """Result of exporting expertise to files."""
    domain: str
    files_written: List[str]
    success: bool
    error: Optional[str] = None


class ExpertiseExporter:
    """Exports database expertise to file-based format."""

    def __init__(self, project_path: str, db: Any):
        self.project_path = Path(project_path)
        self.db = db
        self.experts_dir = self.project_path / ".claude" / "commands" / "experts"

    async def export_domain(self, domain: str, expertise: Dict) -> ExportResult:
        """Export a single domain's expertise to files."""

    async def export_all(self, project_id: UUID) -> List[ExportResult]:
        """Export all domains for a project."""

    def _generate_expertise_yaml(self, domain: str, expertise: Dict) -> str:
        """Generate expertise.yaml content."""

    def _generate_question_md(self, domain: str, expertise: Dict) -> str:
        """Generate question.md template."""

    def _generate_self_improve_md(self, domain: str, expertise: Dict) -> str:
        """Generate self-improve.md content."""
```

**File Format - expertise.yaml**:
```yaml
# {Domain} Domain Expertise
# Auto-generated from YokeFlow learning system

domain: {domain}
description: {derived from patterns}
confidence: {0.0-1.0}
usage_count: {int}
last_updated: {ISO date}

# Key files this domain works with
files:
  primary: [list of core files]
  related: [list of related files]

# Patterns learned
patterns:
  - name: pattern_name
    description: what this pattern does
    example: |
      code example here

# Techniques for this domain
techniques:
  - name: technique_name
    steps:
      - step 1
      - step 2

# Learnings from sessions
learnings:
  - type: success|failure
    lesson: what was learned
    date: when it happened
```

**File Format - question.md**:
```markdown
# {Domain} Expert Query

Use this template when consulting the {domain} expert.

## When to Consult

- {list of scenarios}

## Query Format

```
I need help with {domain}-related task:

**Context**: [describe the situation]
**Goal**: [what you want to achieve]
**Constraints**: [any limitations]
```

## Expert Capabilities

{list of what this expert knows}
```

**File Format - self-improve.md**:
```markdown
# {Domain} Self-Improvement Triggers

## Trigger Conditions

This expertise should be updated when:

1. A session modifies files in: {core_files}
2. A new pattern is discovered for: {keywords}
3. An error occurs related to: {domain}

## Update Process

1. Analyze the session's code changes
2. Extract new patterns or techniques
3. Update expertise.yaml with findings
4. Increment version and update timestamp

## Quality Thresholds

- Minimum confidence for patterns: 0.7
- Maximum learnings to retain: 50
- Stale threshold: 30 days
```

---

### File: core/learning/skill_generator.py

**Purpose**: Generate native Claude skills when expertise crosses maturity threshold.

**Requirements**:
- Check expertise maturity (confidence > 0.8, usage > 10)
- Generate `.claude/skills/{domain}-expert/SKILL.md`
- Include proper frontmatter (name, description)
- Embed relevant patterns as skill instructions
- Only generate if not already exists or expertise updated

**Data Structures**:
```python
@dataclass
class SkillGenerationResult:
    """Result of skill generation."""
    domain: str
    skill_path: str
    generated: bool
    reason: str  # "created", "updated", "skipped_immature", "skipped_unchanged"


class SkillGenerator:
    """Generates native Claude skills from mature expertise."""

    MATURITY_CONFIDENCE = 0.8
    MATURITY_USAGE = 10

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.skills_dir = self.project_path / ".claude" / "skills"

    def should_generate(self, expertise: Dict) -> bool:
        """Check if expertise is mature enough for skill generation."""

    async def generate_skill(self, domain: str, expertise: Dict) -> SkillGenerationResult:
        """Generate a skill from expertise."""

    def _generate_skill_content(self, domain: str, expertise: Dict) -> str:
        """Generate SKILL.md content."""
```

**Skill Format**:
```markdown
---
name: {domain}-expert
description: Expert in {domain} patterns and techniques for this project
---

# {Domain} Expert Skill

You are an expert in {domain} for this project.

## Core Knowledge

{list of core files and their purposes}

## Patterns

{formatted patterns from expertise}

## Techniques

{formatted techniques from expertise}

## Guidelines

{derived from learnings}
```

---

### File: core/learning/expertise_sync.py

**Purpose**: Bidirectional synchronization between file-based and database expertise.

**Requirements**:
- Import: Read files → update DB (on project load)
- Export: Read DB → write files (after expertise update)
- Detect conflicts and prefer newer version
- Validate YAML format before import
- Track sync timestamps

**Data Structures**:
```python
@dataclass
class SyncResult:
    """Result of synchronization operation."""
    direction: str  # "import" or "export"
    domains_synced: List[str]
    conflicts: List[str]
    errors: List[str]


class ExpertiseSyncService:
    """Bidirectional sync between file and database expertise."""

    def __init__(self, project_path: str, project_id: UUID, db: Any):
        self.project_path = Path(project_path)
        self.project_id = project_id
        self.db = db
        self.exporter = ExpertiseExporter(project_path, db)

    async def import_from_files(self) -> SyncResult:
        """Import expertise from files to database."""

    async def export_to_files(self) -> SyncResult:
        """Export expertise from database to files."""

    async def sync(self) -> SyncResult:
        """Full bidirectional sync with conflict resolution."""

    def _parse_expertise_yaml(self, path: Path) -> Optional[Dict]:
        """Parse expertise.yaml file."""

    def _detect_conflicts(self, file_data: Dict, db_data: Dict) -> bool:
        """Check if file and DB versions conflict."""
```

---

### File: core/learning/expertise_manager.py (Modifications)

**Purpose**: Update routing logic to check files first, then fall back to DB.

**New Methods**:
```python
async def route_to_expert(self, query: str, context: Dict) -> Optional[str]:
    """
    Route a query to the appropriate domain expert.

    Priority:
    1. Check .claude/skills/ for native skills
    2. Check .claude/commands/experts/ for file expertise
    3. Fall back to DB-stored expertise
    """

async def get_expertise_from_files(self, domain: str) -> Optional[Dict]:
    """Load expertise from file system."""

def _find_native_skill(self, domain: str) -> Optional[Path]:
    """Check if a native skill exists for this domain."""
```

---

### File: core/orchestrator.py (Modifications)

**Purpose**: Hook expertise export after sessions with new learnings.

**Integration Point** (after session completion):
```python
# After successful session with learnings
if session_info.status == SessionStatus.COMPLETED:
    await self._export_updated_expertise(project_id, project_path, db)

async def _export_updated_expertise(
    self,
    project_id: UUID,
    project_path: str,
    db: Any
) -> None:
    """Export updated expertise to files after session."""
    from core.learning.expertise_sync import ExpertiseSyncService

    try:
        sync_service = ExpertiseSyncService(project_path, project_id, db)
        result = await sync_service.export_to_files()

        if result.domains_synced:
            logger.info(f"Exported expertise for domains: {result.domains_synced}")
    except Exception as e:
        logger.warning(f"Failed to export expertise: {e}")
        # Don't fail session for export errors
```

---

## Testing Strategy

### Unit Tests (`tests/test_expertise_exporter.py`)

```python
@pytest.mark.asyncio
async def test_export_domain_creates_files():
    """Exporting a domain creates expertise.yaml, question.md, self-improve.md."""

@pytest.mark.asyncio
async def test_export_yaml_format():
    """Exported YAML is valid and contains expected fields."""

@pytest.mark.asyncio
async def test_skill_generation_threshold():
    """Skills only generated when confidence > 0.8 and usage > 10."""

@pytest.mark.asyncio
async def test_import_from_files():
    """Importing from files updates database correctly."""

@pytest.mark.asyncio
async def test_sync_conflict_resolution():
    """Conflicts resolved by preferring newer version."""

@pytest.mark.asyncio
async def test_routing_prefers_files():
    """Route to expert checks files before database."""
```

## Acceptance Criteria

- [ ] Expertise exported to `.claude/commands/experts/{domain}/` after sessions
- [ ] Files include expertise.yaml, question.md, self-improve.md
- [ ] Native skills generated when expertise matures
- [ ] Bidirectional sync works correctly
- [ ] File-based expertise loads on project start
- [ ] Routing checks files before database
- [ ] All files are Git-friendly (text-based, diffable)
- [ ] Tests pass

## Validation Commands

```bash
# Run Phase 3 tests
pytest tests/test_expertise_exporter.py tests/test_skill_generator.py -v

# Verify exported files exist
ls -la .claude/commands/experts/*/

# Check skill generation
ls -la .claude/skills/*/
```

## Dependencies

- Existing: `core/learning/expertise_manager.py`
- Existing: `.claude/commands/experts/` structure (from Phase 1 setup)
- Python: `pyyaml` for YAML parsing

## Notes

- YAML format chosen for human readability and Git-friendliness
- Confidence threshold of 0.8 prevents premature skill generation
- File-first routing allows manual expertise editing
- Sync runs after sessions but is non-blocking (failures don't fail sessions)
