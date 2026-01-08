"""
Expertise Exporter
==================

Exports database expertise to file-based format in `.claude/commands/experts/{domain}/`.

Key Features:
- Exports expertise content to expertise.yaml
- Generates question.md template for querying
- Generates self-improve.md with trigger conditions
- Includes metadata (confidence, usage_count, last_updated)
- Handles incremental updates (only export if changed)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
from uuid import UUID
from datetime import datetime
import logging
import json

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of exporting expertise to files."""
    domain: str
    files_written: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class ExpertiseExporter:
    """
    Exports database expertise to file-based format.

    Creates the ADWS-style expertise structure:
    .claude/commands/experts/{domain}/
    ├── expertise.yaml    # Core expertise data
    ├── question.md       # Query template
    └── self-improve.md   # Self-improvement triggers
    """

    def __init__(self, project_path: str, db: Any = None):
        """
        Initialize expertise exporter.

        Args:
            project_path: Path to project root
            db: Database connection (optional, for fetching expertise)
        """
        self.project_path = Path(project_path)
        self.db = db
        self.experts_dir = self.project_path / ".claude" / "commands" / "experts"

    async def export_domain(
        self,
        domain: str,
        expertise: Dict[str, Any],
        force: bool = False
    ) -> ExportResult:
        """
        Export a single domain's expertise to files.

        Args:
            domain: Domain name (e.g., 'database', 'api', 'frontend')
            expertise: Expertise data dictionary
            force: Force export even if unchanged

        Returns:
            ExportResult with status and files written
        """
        result = ExportResult(domain=domain)
        domain_dir = self.experts_dir / domain

        try:
            # Create domain directory
            domain_dir.mkdir(parents=True, exist_ok=True)

            # Check if export needed (skip if unchanged)
            if not force and await self._is_unchanged(domain_dir, expertise):
                logger.debug(f"Skipping unchanged domain: {domain}")
                result.success = True
                return result

            # Generate and write expertise.yaml
            yaml_content = self._generate_expertise_yaml(domain, expertise)
            yaml_path = domain_dir / "expertise.yaml"
            yaml_path.write_text(yaml_content, encoding='utf-8')
            result.files_written.append(str(yaml_path))

            # Generate and write question.md
            question_content = self._generate_question_md(domain, expertise)
            question_path = domain_dir / "question.md"
            question_path.write_text(question_content, encoding='utf-8')
            result.files_written.append(str(question_path))

            # Generate and write self-improve.md
            improve_content = self._generate_self_improve_md(domain, expertise)
            improve_path = domain_dir / "self-improve.md"
            improve_path.write_text(improve_content, encoding='utf-8')
            result.files_written.append(str(improve_path))

            logger.info(f"Exported expertise for domain '{domain}': {len(result.files_written)} files")
            result.success = True

        except Exception as e:
            logger.error(f"Failed to export domain '{domain}': {e}")
            result.success = False
            result.error = str(e)

        return result

    async def export_all(self, project_id: UUID) -> List[ExportResult]:
        """
        Export all domains for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of ExportResult for each domain
        """
        results = []

        if not self.db:
            logger.warning("No database connection, cannot export all domains")
            return results

        try:
            # Get all expertise domains from database
            from core.learning.expertise_manager import ExpertiseManager

            manager = ExpertiseManager(project_id, self.db)
            all_expertise = await manager.get_all_expertise()

            for domain, expertise_file in all_expertise.items():
                result = await self.export_domain(
                    domain,
                    expertise_file.content,
                    force=False
                )
                results.append(result)

            logger.info(f"Exported {len(results)} domains for project {project_id}")

        except Exception as e:
            logger.error(f"Failed to export all domains: {e}")

        return results

    async def _is_unchanged(self, domain_dir: Path, expertise: Dict) -> bool:
        """
        Check if expertise has changed since last export.

        Compares version numbers to avoid unnecessary writes.
        """
        yaml_path = domain_dir / "expertise.yaml"
        if not yaml_path.exists():
            return False

        try:
            content = yaml_path.read_text(encoding='utf-8')

            # Parse version from existing file
            if yaml:
                existing = yaml.safe_load(content)
                existing_version = existing.get('version', 0)
            else:
                # Fallback: look for version line
                for line in content.split('\n'):
                    if line.startswith('version:'):
                        existing_version = int(line.split(':')[1].strip())
                        break
                else:
                    existing_version = 0

            new_version = expertise.get('version', 0)
            return existing_version >= new_version

        except Exception:
            return False

    def _generate_expertise_yaml(self, domain: str, expertise: Dict) -> str:
        """
        Generate expertise.yaml content.

        Args:
            domain: Domain name
            expertise: Expertise data

        Returns:
            YAML-formatted string
        """
        # Extract data with defaults
        patterns = expertise.get('patterns', [])
        techniques = expertise.get('techniques', [])
        learnings = expertise.get('learnings', [])
        core_files = expertise.get('core_files', [])
        confidence = expertise.get('confidence', 0.5)
        usage_count = expertise.get('usage_count', 0)
        version = expertise.get('version', 1)

        # Generate description from patterns
        if patterns:
            pattern_names = [p.get('name', '') for p in patterns[:3]]
            description = f"Expertise in {', '.join(pattern_names)} and related patterns"
        else:
            description = f"Domain expertise for {domain}"

        # Build YAML content
        lines = [
            f"# {domain.title()} Domain Expertise",
            f"# Auto-generated from YokeFlow learning system",
            "",
            f"domain: {domain}",
            f"description: {description}",
            f"confidence: {confidence}",
            f"usage_count: {usage_count}",
            f"version: {version}",
            f"last_updated: {datetime.now().strftime('%Y-%m-%d')}",
            "",
        ]

        # Core files section
        if core_files:
            lines.append("# Key files this domain works with")
            lines.append("files:")
            for f in core_files[:10]:  # Limit to 10 files
                lines.append(f"  - {f}")
            lines.append("")

        # Patterns section
        if patterns:
            lines.append("# Patterns learned")
            lines.append("patterns:")
            for p in patterns[:10]:  # Limit to 10 patterns
                lines.append(f"  - name: {p.get('name', 'unnamed')}")
                if p.get('when_to_use'):
                    lines.append(f"    description: {p.get('when_to_use')}")
                if p.get('code'):
                    lines.append("    example: |")
                    for code_line in p.get('code', '').split('\n')[:10]:
                        lines.append(f"      {code_line}")
            lines.append("")

        # Techniques section
        if techniques:
            lines.append("# Techniques for this domain")
            lines.append("techniques:")
            for t in techniques[:5]:  # Limit to 5 techniques
                lines.append(f"  - name: {t.get('name', 'unnamed')}")
                if t.get('steps'):
                    lines.append("    steps:")
                    for step in t.get('steps', [])[:5]:
                        lines.append(f"      - {step}")
            lines.append("")

        # Learnings section (most recent)
        if learnings:
            lines.append("# Recent learnings from sessions")
            lines.append("learnings:")
            for l in learnings[-5:]:  # Last 5 learnings
                lines.append(f"  - type: {l.get('type', 'unknown')}")
                lines.append(f"    lesson: {l.get('lesson', '')}")
                if l.get('date'):
                    lines.append(f"    date: {l.get('date')}")
            lines.append("")

        return '\n'.join(lines)

    def _generate_question_md(self, domain: str, expertise: Dict) -> str:
        """
        Generate question.md template.

        Args:
            domain: Domain name
            expertise: Expertise data

        Returns:
            Markdown-formatted string
        """
        patterns = expertise.get('patterns', [])
        techniques = expertise.get('techniques', [])
        core_files = expertise.get('core_files', [])

        # Build capabilities list
        capabilities = []
        for p in patterns[:5]:
            capabilities.append(f"- {p.get('name', 'Pattern')}: {p.get('when_to_use', 'No description')}")
        for t in techniques[:3]:
            capabilities.append(f"- {t.get('name', 'Technique')}")

        if not capabilities:
            capabilities = [f"- General {domain} knowledge"]

        # Build scenarios
        scenarios = [
            f"Working with {domain}-related files",
            f"Debugging {domain} issues",
            f"Implementing new {domain} features",
        ]
        if core_files:
            scenarios.append(f"Modifying files like {core_files[0]}")

        content = f"""# {domain.title()} Expert Query

Use this template when consulting the {domain} expert.

## When to Consult

{chr(10).join(f'- {s}' for s in scenarios)}

## Query Format

```
I need help with a {domain}-related task:

**Context**: [describe the current situation]
**Goal**: [what you want to achieve]
**Constraints**: [any limitations or requirements]
**Files involved**: [list relevant files]
```

## Expert Capabilities

{chr(10).join(capabilities)}

## Example Queries

### Pattern Application
"How should I implement [feature] following the existing {domain} patterns?"

### Debugging
"I'm getting [error] when [action]. What's the recommended approach?"

### Best Practices
"What's the best way to [task] in this codebase?"
"""
        return content

    def _generate_self_improve_md(self, domain: str, expertise: Dict) -> str:
        """
        Generate self-improve.md content.

        Args:
            domain: Domain name
            expertise: Expertise data

        Returns:
            Markdown-formatted string
        """
        core_files = expertise.get('core_files', [])
        patterns = expertise.get('patterns', [])

        # Get file patterns to watch
        file_patterns = []
        for f in core_files[:5]:
            if '/' in f:
                dir_part = '/'.join(f.split('/')[:-1])
                file_patterns.append(f"{dir_part}/*")
            else:
                file_patterns.append(f)

        if not file_patterns:
            file_patterns = [f"*{domain}*", f"*/{domain}/*"]

        # Get keywords from patterns
        keywords = set()
        for p in patterns:
            name = p.get('name', '')
            for word in name.split('_'):
                if len(word) > 3:
                    keywords.add(word.lower())

        keywords = list(keywords)[:10] or [domain]

        content = f"""# {domain.title()} Self-Improvement Triggers

## Trigger Conditions

This expertise should be updated when:

1. **File Modifications**: A session modifies files matching:
{chr(10).join(f'   - `{fp}`' for fp in file_patterns)}

2. **Pattern Discovery**: New patterns are found for:
{chr(10).join(f'   - {kw}' for kw in keywords)}

3. **Error Handling**: An error occurs related to {domain}

4. **Success Patterns**: A task completes successfully using {domain} techniques

## Update Process

1. Analyze the session's code changes
2. Extract new patterns or techniques
3. Validate against existing expertise
4. Update expertise.yaml with findings
5. Increment version and update timestamp

## Quality Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Pattern confidence | > 0.7 | Add to expertise |
| Learning relevance | > 0.5 | Store learning |
| Stale expertise | > 30 days | Trigger validation |
| Max learnings | 50 | Prune oldest |

## Validation Triggers

Run expertise validation when:
- 10+ sessions have passed since last validation
- A major refactoring touches core files
- Confidence drops below 0.5
- User explicitly requests validation

## Exclusions

Do not update expertise for:
- Test file changes only
- Documentation-only changes
- Dependency updates
- Generated code
"""
        return content
