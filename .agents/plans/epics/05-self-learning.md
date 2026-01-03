# Epic 05: Self-Learning System

**Priority:** P1 (High Value)
**Estimated Duration:** 3-4 days
**Dependencies:** Epic 01 (Foundation), Epic 04 (Parallel Executor)
**Phase:** 3

---

## Overview

Implement the self-learning system that enables agents to accumulate and apply domain knowledge across sessions. This follows the ACT → LEARN → REUSE pattern from the Orchestrator-ADWS repository.

---

## Core Concept: Expertise Files

Expertise files are the agent's "working memory" - a persistent knowledge store that:

1. **Is NOT a source of truth** - It's a mental model validated against actual code
2. **Is capped at ~1000 lines** - Forces concise, high-value knowledge
3. **Self-updates** - Agents validate and correct expertise after each session
4. **Is domain-specific** - Separate files for database, API, frontend, etc.

```yaml
# Example: .expertise/database.yaml
domain: database
overview: "PostgreSQL patterns for this project"

core_files:
  - src/db/schema.sql
  - src/db/migrations/
  - core/database.py

patterns:
  - "Always use UUID for primary keys"
  - "JSONB for flexible metadata fields"
  - "ON DELETE CASCADE for child tables"

best_practices:
  - "Run migrations in transactions"
  - "Add indexes for foreign keys"
  - "Use connection pooling"

learned_from_failures:
  - issue: "Windows encoding error"
    error: "UnicodeDecodeError: 'charmap' codec..."
    solution: "Always use encoding='utf-8' in open()"
    sessions: [12, 15, 23]

effective_patterns:
  - "Read file → Edit → Run tests sequence works well"
  - "Check git status before committing"
```

---

## Tasks

### 5.1 ExpertiseManager Core Implementation

**Description:** Implement the expertise management class.

**File:** `core/learning/expertise_manager.py`

**Class Structure:**

```python
DOMAINS = [
    'database',
    'api',
    'frontend',
    'testing',
    'security',
    'deployment',
    'general'
]

MAX_EXPERTISE_LINES = 1000

@dataclass
class ExpertiseFile:
    """Represents an expertise file"""
    domain: str
    content: Dict[str, Any]
    version: int
    line_count: int
    last_validated: Optional[datetime]

class ExpertiseManager:
    """
    Manages domain expertise files for self-improving agents.

    Implements the ACT → LEARN → REUSE pattern:
    1. Before task: Agent reads domain expertise
    2. During task: Agent validates expertise against actual code
    3. After task: Agent updates expertise with learnings
    """

    def __init__(self, project_path: Path, project_id: UUID):
        self.project_path = project_path
        self.project_id = project_id
        self.expertise_dir = project_path / ".expertise"

    async def get_expertise_for_task(self, task: Dict) -> str:
        """Get formatted expertise relevant to a task"""

    async def learn_from_session(
        self,
        task: Dict,
        result: Dict,
        session_logs: List[Dict]
    ) -> Dict[str, Any]:
        """Extract learnings from a completed session"""

    async def validate_expertise(self, domain: str) -> Dict[str, Any]:
        """Validate expertise against actual codebase"""

    async def self_improve(self, domain: str) -> Dict[str, Any]:
        """Run self-improvement cycle for a domain"""
```

**Acceptance Criteria:**
- [ ] Creates and manages expertise files
- [ ] Correctly classifies tasks by domain
- [ ] Extracts learnings from sessions
- [ ] Validates against codebase

---

### 5.2 Domain Classification

**Description:** Implement intelligent domain classification for tasks.

**Implementation:**

```python
DOMAIN_KEYWORDS = {
    'database': [
        'database', 'schema', 'migration', 'sql', 'postgres',
        'table', 'column', 'index', 'query', 'transaction'
    ],
    'api': [
        'api', 'endpoint', 'route', 'rest', 'graphql', 'http',
        'request', 'response', 'json', 'websocket'
    ],
    'frontend': [
        'ui', 'component', 'react', 'vue', 'angular', 'frontend',
        'css', 'html', 'style', 'button', 'form', 'page'
    ],
    'testing': [
        'test', 'spec', 'validation', 'assert', 'mock', 'fixture',
        'pytest', 'jest', 'playwright', 'coverage'
    ],
    'security': [
        'auth', 'authentication', 'authorization', 'security',
        'permission', 'token', 'encrypt', 'password', 'jwt'
    ],
    'deployment': [
        'deploy', 'docker', 'kubernetes', 'ci', 'cd', 'build',
        'release', 'container', 'pipeline', 'environment'
    ]
}

def classify_domain(self, task: Dict) -> str:
    """Classify task into expertise domain"""
    text = f"{task.get('description', '')} {task.get('action', '')}".lower()

    scores = {domain: 0 for domain in DOMAINS}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[domain] += 1

    # Also check file paths mentioned
    if task.get('files'):
        for file in task['files']:
            if 'test' in file.lower():
                scores['testing'] += 2
            elif 'api' in file.lower() or 'route' in file.lower():
                scores['api'] += 2
            elif 'component' in file.lower() or 'ui' in file.lower():
                scores['frontend'] += 2

    best_domain = max(scores, key=scores.get)
    return best_domain if scores[best_domain] > 0 else 'general'
```

**Acceptance Criteria:**
- [ ] Correctly classifies common task types
- [ ] Handles multi-domain tasks (picks primary)
- [ ] Falls back to 'general' when uncertain

---

### 5.3 Learning Extraction

**Description:** Extract learnings from completed sessions.

**Implementation:**

```python
async def learn_from_session(
    self,
    task: Dict,
    result: Dict,
    session_logs: List[Dict]
) -> Dict[str, Any]:
    """Extract learnings from a completed session"""
    domain = self.classify_domain(task)
    expertise = await self._load_expertise(domain)

    if not expertise:
        expertise = self._create_initial_expertise(domain)

    changes = []

    # 1. Learn from failures
    if result.get('status') == 'error':
        error_learning = {
            'issue': task['description'][:100],
            'error': result.get('error', 'Unknown')[:200],
            'task_id': task['id'],
            'timestamp': datetime.now().isoformat()
        }
        expertise.setdefault('learned_from_failures', []).append(error_learning)
        changes.append({'type': 'failure_learning', 'data': error_learning})

    # 2. Learn from tool patterns
    tool_patterns = self._extract_tool_patterns(session_logs)
    for pattern in tool_patterns:
        if pattern not in expertise.get('effective_patterns', []):
            expertise.setdefault('effective_patterns', []).append(pattern)
            changes.append({'type': 'pattern_discovered', 'data': pattern})

    # 3. Track modified files
    modified_files = self._extract_modified_files(session_logs)
    for file in modified_files:
        relative_file = self._make_relative(file)
        if relative_file not in expertise.get('core_files', []):
            expertise.setdefault('core_files', []).append(relative_file)
            changes.append({'type': 'file_discovered', 'data': relative_file})

    # 4. Extract successful techniques
    if result.get('status') == 'completed':
        technique = self._extract_successful_technique(task, session_logs)
        if technique:
            expertise.setdefault('successful_techniques', []).append(technique)
            changes.append({'type': 'technique_learned', 'data': technique})

    # Enforce line limit
    expertise = self._enforce_line_limit(expertise)

    # Save updated expertise
    await self._save_expertise(domain, expertise)

    # Record learning history in database
    await self._record_learning(domain, changes, task['id'])

    return {
        'domain': domain,
        'changes_count': len(changes),
        'changes': changes
    }
```

**Acceptance Criteria:**
- [ ] Extracts learnings from failures
- [ ] Identifies effective tool patterns
- [ ] Tracks modified files
- [ ] Records successful techniques
- [ ] Enforces line limit

---

### 5.4 Tool Pattern Extraction

**Description:** Extract effective tool usage patterns from session logs.

**Implementation:**

```python
def _extract_tool_patterns(self, logs: List[Dict]) -> List[str]:
    """Extract effective tool usage patterns from logs"""
    patterns = []
    tool_sequence = []

    for log in logs:
        if log.get('type') == 'tool_use':
            tool_name = log.get('tool_name', '')
            tool_sequence.append(tool_name)

            # Detect patterns
            if len(tool_sequence) >= 3:
                recent = tool_sequence[-3:]

                # Read → Edit → Test pattern
                if 'Read' in recent and 'Edit' in recent:
                    if any('test' in t.lower() for t in recent):
                        patterns.append("Read → Edit → Test sequence works well")

                # Glob → Read pattern
                if recent[0] == 'Glob' and recent[1] == 'Read':
                    patterns.append("Glob to find files, then Read is effective")

        elif log.get('type') == 'tool_result':
            if log.get('success') and len(tool_sequence) >= 2:
                # Record successful tool combinations
                combo = f"{tool_sequence[-2]} → {tool_sequence[-1]}"
                if combo not in patterns:
                    patterns.append(f"Successful combo: {combo}")

    # Deduplicate and limit
    unique_patterns = list(set(patterns))
    return unique_patterns[:5]

def _extract_modified_files(self, logs: List[Dict]) -> List[str]:
    """Extract list of modified files from logs"""
    files = set()

    for log in logs:
        if log.get('type') == 'tool_use':
            tool_name = log.get('tool_name', '')

            if tool_name in ['Write', 'Edit']:
                file_path = log.get('input', {}).get('file_path', '')
                if file_path:
                    files.add(file_path)

            elif tool_name == 'Bash':
                command = log.get('input', {}).get('command', '')
                # Extract files from git commands
                if 'git add' in command:
                    # Parse file from command
                    pass

    return list(files)
```

**Acceptance Criteria:**
- [ ] Identifies Read → Edit → Test patterns
- [ ] Captures successful tool combinations
- [ ] Extracts modified files from logs

---

### 5.5 Expertise Validation

**Description:** Validate expertise against actual codebase.

**Implementation:**

```python
async def validate_expertise(self, domain: str) -> Dict[str, Any]:
    """Validate expertise against actual codebase"""
    expertise = await self._load_expertise(domain)

    if not expertise:
        return {'status': 'no_expertise', 'corrections': []}

    corrections = []

    # 1. Validate core files exist
    for file in list(expertise.get('core_files', [])):
        file_path = self.project_path / file
        if not file_path.exists():
            corrections.append({
                'type': 'file_removed',
                'file': file,
                'action': 'removed from core_files'
            })
            expertise['core_files'].remove(file)

    # 2. Validate patterns still apply (sample-based)
    for pattern in expertise.get('patterns', [])[:3]:
        # Try to verify pattern is still valid
        # This could involve code analysis
        pass

    # 3. Check for stale failure learnings (older than 30 days)
    if expertise.get('learned_from_failures'):
        cutoff = datetime.now() - timedelta(days=30)
        fresh_failures = [
            f for f in expertise['learned_from_failures']
            if datetime.fromisoformat(f.get('timestamp', '2000-01-01')) > cutoff
        ]
        removed_count = len(expertise['learned_from_failures']) - len(fresh_failures)
        if removed_count > 0:
            corrections.append({
                'type': 'stale_failures_removed',
                'count': removed_count
            })
            expertise['learned_from_failures'] = fresh_failures

    # Update validation timestamp
    expertise['last_validated'] = datetime.now().isoformat()

    if corrections:
        await self._save_expertise(domain, expertise)

    return {
        'status': 'validated',
        'corrections': corrections,
        'validated_at': expertise['last_validated']
    }

async def self_improve(self, domain: str) -> Dict[str, Any]:
    """
    Run full self-improvement cycle:
    1. Load expertise
    2. Scan codebase for relevant files
    3. Compare documented vs actual
    4. Update expertise
    """
    expertise = await self._load_expertise(domain)

    if not expertise:
        expertise = self._create_initial_expertise(domain)

    improvements = []

    # Scan for files matching domain
    file_patterns = self._get_file_patterns(domain)
    for pattern in file_patterns:
        files = list(self.project_path.glob(pattern))
        for file in files[:20]:  # Limit scan
            relative = str(file.relative_to(self.project_path))
            if relative not in expertise.get('core_files', []):
                expertise.setdefault('core_files', []).append(relative)
                improvements.append({
                    'type': 'file_discovered',
                    'file': relative
                })

    # Enforce line limit
    expertise = self._enforce_line_limit(expertise)

    await self._save_expertise(domain, expertise)

    return {
        'domain': domain,
        'improvements': improvements,
        'line_count': self._count_lines(expertise)
    }
```

**Acceptance Criteria:**
- [ ] Removes references to deleted files
- [ ] Prunes stale failure learnings
- [ ] Discovers new relevant files
- [ ] Updates validation timestamp

---

### 5.6 Prompt Formatting

**Description:** Format expertise for injection into prompts.

**Implementation:**

```python
def _format_for_prompt(self, expertise: Dict, task: Dict) -> str:
    """Format expertise for prompt injection"""
    lines = [
        f"## Domain Expertise: {expertise.get('domain', 'General').title()}",
        "",
        expertise.get('overview', ''),
        ""
    ]

    # Core files (limited)
    if expertise.get('core_files'):
        lines.append("### Key Files")
        for f in expertise['core_files'][:10]:
            lines.append(f"- `{f}`")
        if len(expertise['core_files']) > 10:
            lines.append(f"- ... and {len(expertise['core_files']) - 10} more")
        lines.append("")

    # Patterns
    if expertise.get('patterns'):
        lines.append("### Known Patterns")
        for p in expertise['patterns'][:5]:
            lines.append(f"- {p}")
        lines.append("")

    # Best practices
    if expertise.get('best_practices'):
        lines.append("### Best Practices")
        for bp in expertise['best_practices'][:5]:
            lines.append(f"- {bp}")
        lines.append("")

    # Recent failures (most relevant)
    if expertise.get('learned_from_failures'):
        lines.append("### Lessons from Past Issues")
        for lesson in expertise['learned_from_failures'][-3:]:
            issue = lesson.get('issue', 'Issue')[:50]
            error = lesson.get('error', '')[:100]
            solution = lesson.get('solution', '')
            lines.append(f"- **{issue}**: {error}")
            if solution:
                lines.append(f"  - Solution: {solution}")
        lines.append("")

    # Effective patterns
    if expertise.get('effective_patterns'):
        lines.append("### Effective Approaches")
        for ep in expertise['effective_patterns'][-3:]:
            lines.append(f"- {ep}")
        lines.append("")

    return '\n'.join(lines)
```

**Acceptance Criteria:**
- [ ] Formats expertise as readable markdown
- [ ] Limits content to avoid token bloat
- [ ] Prioritizes recent/relevant information

---

### 5.7 Line Limit Enforcement

**Description:** Enforce maximum line limit on expertise files.

**Implementation:**

```python
def _enforce_line_limit(self, expertise: Dict) -> Dict:
    """Enforce maximum line limit by pruning old entries"""
    yaml_str = yaml.dump(expertise, default_flow_style=False)
    line_count = len(yaml_str.split('\n'))

    if line_count <= MAX_EXPERTISE_LINES:
        return expertise

    # Prune in order of priority (least important first)

    # 1. Trim old failure learnings
    if expertise.get('learned_from_failures'):
        expertise['learned_from_failures'] = expertise['learned_from_failures'][-10:]

    # 2. Trim old patterns
    if expertise.get('effective_patterns'):
        expertise['effective_patterns'] = expertise['effective_patterns'][-15:]

    # 3. Trim core files
    if expertise.get('core_files'):
        expertise['core_files'] = expertise['core_files'][:30]

    # 4. Trim successful techniques
    if expertise.get('successful_techniques'):
        expertise['successful_techniques'] = expertise['successful_techniques'][-10:]

    # Recheck
    yaml_str = yaml.dump(expertise, default_flow_style=False)
    line_count = len(yaml_str.split('\n'))

    if line_count > MAX_EXPERTISE_LINES:
        logger.warning(f"Expertise still over limit after pruning: {line_count} lines")

    return expertise
```

**Acceptance Criteria:**
- [ ] Keeps expertise under 1000 lines
- [ ] Preserves most recent/important entries
- [ ] Logs warning if still over limit

---

### 5.8 Database Integration

**Description:** Store expertise in database for persistence and versioning.

**Database Methods:**

```python
# In core/database.py

async def get_expertise(self, project_id: UUID, domain: str) -> Optional[Dict]:
    """Get expertise file from database"""
    row = await conn.fetchrow(
        """
        SELECT * FROM expertise_files
        WHERE project_id = $1 AND domain = $2
        """,
        project_id, domain
    )
    if row:
        return dict(row)
    return None

async def save_expertise(
    self,
    project_id: UUID,
    domain: str,
    content: Dict
) -> Dict:
    """Save or update expertise file"""
    yaml_str = yaml.dump(content, default_flow_style=False)
    line_count = len(yaml_str.split('\n'))

    row = await conn.fetchrow(
        """
        INSERT INTO expertise_files (project_id, domain, content, line_count, version)
        VALUES ($1, $2, $3, $4, 1)
        ON CONFLICT (project_id, domain)
        DO UPDATE SET
            content = $3,
            line_count = $4,
            version = expertise_files.version + 1,
            updated_at = NOW()
        RETURNING *
        """,
        project_id, domain, json.dumps(content), line_count
    )
    return dict(row)

async def record_expertise_update(
    self,
    expertise_id: UUID,
    session_id: UUID,
    change_type: str,
    summary: str,
    diff: Optional[Dict] = None
) -> Dict:
    """Record expertise update for audit trail"""
    row = await conn.fetchrow(
        """
        INSERT INTO expertise_updates
        (expertise_id, session_id, change_type, change_summary, diff)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        expertise_id, session_id, change_type, summary, json.dumps(diff)
    )
    return dict(row)
```

**Acceptance Criteria:**
- [ ] Expertise persists across sessions
- [ ] Version tracking works
- [ ] Update history recorded

---

### 5.9 API Endpoints

**Description:** Add API endpoints for expertise management.

**Endpoints:**

```python
@app.get("/api/projects/{project_id}/expertise")
async def list_expertise(project_id: str):
    """List all expertise domains for a project"""

@app.get("/api/projects/{project_id}/expertise/{domain}")
async def get_expertise(project_id: str, domain: str):
    """Get expertise for a domain"""

@app.post("/api/projects/{project_id}/expertise/{domain}/validate")
async def validate_expertise(project_id: str, domain: str):
    """Validate expertise against codebase"""

@app.post("/api/projects/{project_id}/expertise/{domain}/improve")
async def improve_expertise(project_id: str, domain: str):
    """Run self-improvement cycle"""

@app.get("/api/projects/{project_id}/expertise/{domain}/history")
async def get_expertise_history(project_id: str, domain: str):
    """Get expertise update history"""
```

**Acceptance Criteria:**
- [ ] All endpoints functional
- [ ] Proper error handling
- [ ] Returns formatted expertise

---

## Testing Requirements

### Unit Tests

```python
class TestExpertiseManager:
    def test_domain_classification(self):
        """Correctly classifies task domains"""

    def test_learning_extraction(self):
        """Extracts learnings from session logs"""

    def test_line_limit_enforcement(self):
        """Prunes to stay under limit"""

    def test_validation(self):
        """Validates against codebase"""

    def test_prompt_formatting(self):
        """Formats expertise for prompts"""
```

---

## Dependencies

- Epic 01: Foundation (database schema)
- Epic 04: Parallel Executor (provides session logs)

## Dependents

- Epic 06: Cost Optimization (uses expertise for model selection)

---

## Notes

- Consider pre-seeding expertise from YokeFlow's own patterns
- May need to handle very large projects differently
- Expertise validation could be enhanced with AST analysis
