# Implementation Plan: Phase 4 - Generated Project Bootstrapping

## Task Description

Ensure generated projects have the Claude SDK structure from day 1. This includes creating a project template with `.claude/` directory, bootstrapping expertise stubs, and generating initial CLAUDE.md from app_spec analysis.

## Objectives

- [ ] Create project template in `templates/claude-sdk-project/`
- [ ] Create ProjectBootstrapper class to copy template structure
- [ ] Create CLAUDEMDGenerator to generate CLAUDE.md from app_spec
- [ ] Pre-create domain expert stubs based on detected domains
- [ ] Hook into orchestrator to bootstrap during Session 0
- [ ] Support expertise updates after task completions

## Relevant Files

| File | Purpose | Action |
|------|---------|--------|
| `templates/claude-sdk-project/` | Template directory structure | Create |
| `core/bootstrap/project_bootstrapper.py` | Copy template and bootstrap | Create |
| `core/bootstrap/claude_md_generator.py` | Generate CLAUDE.md from spec | Create |
| `core/bootstrap/domain_detector.py` | Detect domains from app_spec | Create |
| `core/orchestrator.py` | Hook bootstrapper into Session 0 | Modify |

## Implementation Phases

### Batch 1 (No Dependencies - Can Run in Parallel)
- Create `templates/claude-sdk-project/` structure
- Create `core/bootstrap/domain_detector.py`

### Batch 2 (Depends on Batch 1)
- Create `core/bootstrap/claude_md_generator.py`
- Create `core/bootstrap/project_bootstrapper.py`

### Batch 3 (Depends on Batch 2)
- Hook into orchestrator for Session 0 bootstrapping
- Write tests

## File Specifications

---

### Directory: templates/claude-sdk-project/

**Purpose**: Template structure copied to new projects.

**Structure**:
```
templates/claude-sdk-project/
├── .claude/
│   ├── settings.json           # Project-specific Claude settings
│   ├── skills/
│   │   └── .gitkeep
│   └── commands/
│       └── experts/
│           └── .gitkeep
└── CLAUDE.md.template          # Template for generated CLAUDE.md
```

**settings.json content**:
```json
{
  "model": "claude-sonnet-4-20250514",
  "permissions": {
    "allow_bash": true,
    "allow_file_write": true
  },
  "project": {
    "name": "{{PROJECT_NAME}}",
    "description": "{{PROJECT_DESCRIPTION}}"
  }
}
```

---

### File: core/bootstrap/domain_detector.py

**Purpose**: Detect domains from app_spec to pre-create expert stubs.

**Requirements**:
- Parse app_spec.txt for technology keywords
- Detect domains: frontend, backend, database, api, testing, devops
- Return list of detected domains with confidence scores
- Support common tech stacks (React, FastAPI, PostgreSQL, etc.)

**Class Interface**:
```python
@dataclass
class DetectedDomain:
    name: str
    confidence: float
    keywords_found: List[str]
    suggested_files: List[str]

class DomainDetector:
    def __init__(self):
        pass

    def detect_domains(self, app_spec: str) -> List[DetectedDomain]:
        """Detect domains from app specification text."""
        pass

    def _detect_frontend(self, text: str) -> Optional[DetectedDomain]:
        pass

    def _detect_backend(self, text: str) -> Optional[DetectedDomain]:
        pass

    def _detect_database(self, text: str) -> Optional[DetectedDomain]:
        pass
```

---

### File: core/bootstrap/claude_md_generator.py

**Purpose**: Generate CLAUDE.md from app_spec analysis.

**Requirements**:
- Parse app_spec for project name, description, technologies
- Generate structured CLAUDE.md with sections:
  - What This Is
  - Tech Stack
  - Project Structure (predicted)
  - Key Commands
  - Development Workflow
- Include YokeFlow-specific guidance
- Support template variables

**Class Interface**:
```python
@dataclass
class GeneratedCLAUDEMD:
    content: str
    detected_stack: Dict[str, str]
    predicted_structure: List[str]

class CLAUDEMDGenerator:
    def __init__(self):
        pass

    async def generate(
        self,
        app_spec: str,
        project_name: str,
        detected_domains: List[DetectedDomain]
    ) -> GeneratedCLAUDEMD:
        """Generate CLAUDE.md content from app specification."""
        pass

    def _extract_tech_stack(self, app_spec: str) -> Dict[str, str]:
        pass

    def _predict_structure(self, detected_domains: List[DetectedDomain]) -> List[str]:
        pass

    def _generate_commands(self, tech_stack: Dict[str, str]) -> List[str]:
        pass
```

---

### File: core/bootstrap/project_bootstrapper.py

**Purpose**: Bootstrap new projects with Claude SDK structure.

**Requirements**:
- Copy template structure to project directory
- Generate CLAUDE.md using CLAUDEMDGenerator
- Create domain expert stubs for detected domains
- Replace template variables in settings.json
- Support incremental updates (don't overwrite existing)

**Class Interface**:
```python
@dataclass
class BootstrapResult:
    success: bool
    files_created: List[str]
    domains_initialized: List[str]
    claude_md_generated: bool
    errors: List[str]

class ProjectBootstrapper:
    def __init__(self, templates_dir: str = None):
        pass

    async def bootstrap(
        self,
        project_path: str,
        app_spec: str,
        project_name: str,
        force: bool = False
    ) -> BootstrapResult:
        """Bootstrap project with Claude SDK structure."""
        pass

    def _copy_template(self, project_path: str) -> List[str]:
        pass

    def _create_domain_stubs(
        self,
        project_path: str,
        domains: List[DetectedDomain]
    ) -> List[str]:
        pass

    def _write_settings(
        self,
        project_path: str,
        project_name: str,
        description: str
    ) -> None:
        pass
```

---

### File: core/orchestrator.py (Modification)

**Purpose**: Hook bootstrapper into Session 0.

**Changes**:
1. After Session 0 completes successfully, call bootstrapper
2. Pass app_spec content to bootstrapper
3. Log bootstrap results

**New Method**:
```python
async def _bootstrap_project_structure(
    self,
    project_id: UUID,
    project_path: str,
    db,
    session_logger
) -> None:
    """Bootstrap Claude SDK structure for new project."""
    try:
        from core.bootstrap.project_bootstrapper import ProjectBootstrapper

        # Read app_spec
        app_spec_path = Path(project_path) / 'app_spec.txt'
        if not app_spec_path.exists():
            session_logger.info("No app_spec.txt found, skipping bootstrap")
            return

        app_spec = app_spec_path.read_text()
        project = await db.get_project(project_id)

        bootstrapper = ProjectBootstrapper()
        result = await bootstrapper.bootstrap(
            project_path=project_path,
            app_spec=app_spec,
            project_name=project['name']
        )

        if result.success:
            session_logger.info(
                f"Bootstrapped project: {len(result.files_created)} files, "
                f"{len(result.domains_initialized)} domains"
            )
        else:
            session_logger.warning(f"Bootstrap had errors: {result.errors}")

    except Exception as e:
        session_logger.debug(f"Bootstrap skipped: {e}")
```

**Integration Point** (after Session 0 completes):
```python
# In run_session(), after initializer session completes
if is_initializer and status != "error":
    await self._bootstrap_project_structure(project_id, project_path, db, session_logger)
```

---

## Domain Expert Stub Template

When creating domain stubs, use this template for `expertise.yaml`:

```yaml
# {{DOMAIN}} Domain Expertise
# Auto-generated by YokeFlow bootstrapper

domain: {{DOMAIN}}
description: {{DESCRIPTION}}
confidence: 0.3
usage_count: 0
version: 1
last_updated: {{DATE}}

# Detected technologies
stack: {{STACK}}

# Key files (to be populated)
files: []

# Patterns (to be learned)
patterns: []

# Techniques (to be learned)
techniques: []
```

---

## Testing Requirements

1. **DomainDetector tests**:
   - Detect frontend from React/Vue/Angular keywords
   - Detect backend from FastAPI/Django/Express keywords
   - Detect database from PostgreSQL/MongoDB keywords
   - Handle mixed tech stacks

2. **CLAUDEMDGenerator tests**:
   - Generate valid markdown
   - Include detected technologies
   - Predict reasonable structure

3. **ProjectBootstrapper tests**:
   - Copy template structure correctly
   - Create domain stubs
   - Don't overwrite existing files
   - Handle missing app_spec gracefully

4. **Integration tests**:
   - End-to-end bootstrap from app_spec
   - Verify file structure created

---

## Success Criteria

- [ ] New projects have `.claude/` directory after Session 0
- [ ] CLAUDE.md is generated with project-specific content
- [ ] Domain expert stubs created for detected domains
- [ ] Existing files are not overwritten
- [ ] All tests pass
