"""
Project Bootstrapper
====================

Bootstraps new projects with Claude SDK structure.

Key Features:
- Copy template structure to project directory
- Generate CLAUDE.md using CLAUDEMDGenerator
- Create domain expert stubs for detected domains
- Replace template variables in settings.json
- Support incremental updates (don't overwrite existing)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import shutil
import json
import logging

from core.bootstrap.domain_detector import DomainDetector, DetectedDomain
from core.bootstrap.claude_md_generator import CLAUDEMDGenerator

logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    """Result of project bootstrap."""
    success: bool
    files_created: List[str] = field(default_factory=list)
    domains_initialized: List[str] = field(default_factory=list)
    claude_md_generated: bool = False
    errors: List[str] = field(default_factory=list)


class ProjectBootstrapper:
    """
    Bootstraps new projects with Claude SDK structure.

    Creates the .claude/ directory structure and generates
    initial configuration files.
    """

    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize project bootstrapper.

        Args:
            templates_dir: Path to templates directory (optional)
        """
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            self.templates_dir = Path(__file__).parent.parent.parent / 'templates' / 'claude-sdk-project'

        self.detector = DomainDetector()
        self.claude_md_generator = CLAUDEMDGenerator(str(self.templates_dir))

    async def bootstrap(
        self,
        project_path: str,
        app_spec: str,
        project_name: str,
        force: bool = False
    ) -> BootstrapResult:
        """
        Bootstrap project with Claude SDK structure.

        Args:
            project_path: Path to project directory
            app_spec: Application specification text
            project_name: Name of the project
            force: Force overwrite existing files

        Returns:
            BootstrapResult with status and details
        """
        result = BootstrapResult(success=True)
        project_dir = Path(project_path)

        try:
            # Ensure project directory exists
            if not project_dir.exists():
                result.errors.append(f"Project directory does not exist: {project_path}")
                result.success = False
                return result

            # 1. Copy template structure
            template_files = self._copy_template(project_dir, force)
            result.files_created.extend(template_files)

            # 2. Detect domains from app_spec
            detected_domains = self.detector.detect_domains(app_spec)

            # 3. Create domain expert stubs
            domain_files = self._create_domain_stubs(project_dir, detected_domains, force)
            result.files_created.extend(domain_files)
            result.domains_initialized = [d.name for d in detected_domains]

            # 4. Generate CLAUDE.md
            claude_md_path = project_dir / 'CLAUDE.md'
            if not claude_md_path.exists() or force:
                claude_md_result = await self.claude_md_generator.generate(
                    app_spec=app_spec,
                    project_name=project_name,
                    detected_domains=detected_domains
                )
                claude_md_path.write_text(claude_md_result.content, encoding='utf-8')
                result.files_created.append(str(claude_md_path))
                result.claude_md_generated = True
                logger.info(f"Generated CLAUDE.md for project: {project_name}")

            # 5. Update settings.json with project info
            description = self._extract_short_description(app_spec)
            self._write_settings(project_dir, project_name, description, force)

            logger.info(
                f"Bootstrapped project '{project_name}': "
                f"{len(result.files_created)} files, "
                f"{len(result.domains_initialized)} domains"
            )

        except Exception as e:
            result.errors.append(str(e))
            result.success = False
            logger.error(f"Bootstrap failed for '{project_name}': {e}")

        return result

    def _copy_template(self, project_dir: Path, force: bool = False) -> List[str]:
        """
        Copy template structure to project directory.

        Args:
            project_dir: Target project directory
            force: Force overwrite existing files

        Returns:
            List of created file paths
        """
        created_files = []

        # Create .claude directory structure
        claude_dir = project_dir / '.claude'
        dirs_to_create = [
            claude_dir,
            claude_dir / 'skills',
            claude_dir / 'commands',
            claude_dir / 'commands' / 'experts',
        ]

        for dir_path in dirs_to_create:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {dir_path}")

        # Copy template files
        if self.templates_dir.exists():
            template_claude_dir = self.templates_dir / '.claude'
            if template_claude_dir.exists():
                for template_file in template_claude_dir.rglob('*'):
                    if template_file.is_file():
                        # Calculate relative path
                        rel_path = template_file.relative_to(template_claude_dir)
                        target_path = claude_dir / rel_path

                        # Create parent directories
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # Copy if doesn't exist or force
                        if not target_path.exists() or force:
                            shutil.copy2(template_file, target_path)
                            created_files.append(str(target_path))
                            logger.debug(f"Copied template file: {target_path}")

        return created_files

    def _create_domain_stubs(
        self,
        project_dir: Path,
        domains: List[DetectedDomain],
        force: bool = False
    ) -> List[str]:
        """
        Create domain expert stubs for detected domains.

        Args:
            project_dir: Target project directory
            domains: List of detected domains
            force: Force overwrite existing files

        Returns:
            List of created file paths
        """
        created_files = []
        experts_dir = project_dir / '.claude' / 'commands' / 'experts'

        for domain in domains:
            domain_dir = experts_dir / domain.name
            domain_dir.mkdir(parents=True, exist_ok=True)

            # Create expertise.yaml stub
            yaml_path = domain_dir / 'expertise.yaml'
            if not yaml_path.exists() or force:
                yaml_content = self._generate_domain_stub(domain)
                yaml_path.write_text(yaml_content, encoding='utf-8')
                created_files.append(str(yaml_path))
                logger.debug(f"Created domain stub: {yaml_path}")

            # Create question.md stub
            question_path = domain_dir / 'question.md'
            if not question_path.exists() or force:
                question_content = self._generate_question_stub(domain)
                question_path.write_text(question_content, encoding='utf-8')
                created_files.append(str(question_path))

            # Create self-improve.md stub
            improve_path = domain_dir / 'self-improve.md'
            if not improve_path.exists() or force:
                improve_content = self._generate_improve_stub(domain)
                improve_path.write_text(improve_content, encoding='utf-8')
                created_files.append(str(improve_path))

        return created_files

    def _generate_domain_stub(self, domain: DetectedDomain) -> str:
        """Generate expertise.yaml stub for a domain."""
        stack_yaml = ""
        if domain.stack:
            stack_lines = [f"  {k}: {v}" for k, v in domain.stack.items()]
            stack_yaml = "stack:\n" + "\n".join(stack_lines)
        else:
            stack_yaml = "stack: {}"

        return f"""# {domain.name.title()} Domain Expertise
# Auto-generated by YokeFlow bootstrapper

domain: {domain.name}
description: {domain.description}
confidence: 0.3
usage_count: 0
version: 1
last_updated: {datetime.now().strftime('%Y-%m-%d')}

# Detected technologies
{stack_yaml}

# Keywords that triggered detection
detected_keywords:
{self._format_list(domain.keywords_found[:5])}

# Key files (to be populated during development)
files: []

# Patterns (to be learned during development)
patterns: []

# Techniques (to be learned during development)
techniques: []

# Learnings (to be captured during development)
learnings: []
"""

    def _generate_question_stub(self, domain: DetectedDomain) -> str:
        """Generate question.md stub for a domain."""
        return f"""# {domain.name.title()} Expert Query

Use this template when consulting the {domain.name} expert.

## When to Consult

- Working with {domain.name}-related files
- Debugging {domain.name} issues
- Implementing new {domain.name} features

## Query Format

```
I need help with a {domain.name}-related task:

**Context**: [describe the current situation]
**Goal**: [what you want to achieve]
**Constraints**: [any limitations or requirements]
**Files involved**: [list relevant files]
```

## Expert Capabilities

This is a new domain expert. Capabilities will be learned during development.

- {domain.description}

## Example Queries

### Pattern Application
"How should I implement [feature] following the existing {domain.name} patterns?"

### Debugging
"I'm getting [error] when [action]. What's the recommended approach?"

### Best Practices
"What's the best way to [task] in this codebase?"
"""

    def _generate_improve_stub(self, domain: DetectedDomain) -> str:
        """Generate self-improve.md stub for a domain."""
        file_patterns = domain.suggested_files if domain.suggested_files else [f"*{domain.name}*"]

        return f"""# {domain.name.title()} Self-Improvement Triggers

## Trigger Conditions

This expertise should be updated when:

1. **File Modifications**: A session modifies files matching:
{self._format_list(file_patterns)}

2. **Pattern Discovery**: New patterns are found for {domain.name}

3. **Error Handling**: An error occurs related to {domain.name}

4. **Success Patterns**: A task completes successfully using {domain.name} techniques

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

    def _write_settings(
        self,
        project_dir: Path,
        project_name: str,
        description: str,
        force: bool = False
    ) -> None:
        """
        Write settings.json with project-specific values.

        Args:
            project_dir: Target project directory
            project_name: Name of the project
            description: Project description
            force: Force overwrite existing
        """
        settings_path = project_dir / '.claude' / 'settings.json'

        if settings_path.exists() and not force:
            # Update existing settings
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                # Update project info if placeholders exist
                if 'project' in settings:
                    if settings['project'].get('name') == '{{PROJECT_NAME}}':
                        settings['project']['name'] = project_name
                    if settings['project'].get('description') == '{{PROJECT_DESCRIPTION}}':
                        settings['project']['description'] = description

                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2)

            except Exception as e:
                logger.warning(f"Failed to update settings.json: {e}")
        else:
            # Write new settings
            settings = {
                "model": "claude-sonnet-4-20250514",
                "permissions": {
                    "allow_bash": True,
                    "allow_file_write": True
                },
                "project": {
                    "name": project_name,
                    "description": description
                }
            }

            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)

    def _extract_short_description(self, app_spec: str) -> str:
        """Extract a short description from app_spec."""
        if not app_spec:
            return "A project generated by YokeFlow"

        # Get first non-empty line that's not a header
        for line in app_spec.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('-'):
                # Truncate to 100 chars
                if len(line) > 100:
                    return line[:97] + '...'
                return line

        return "A project generated by YokeFlow"

    def _format_list(self, items: List[str]) -> str:
        """Format a list as YAML list items."""
        if not items:
            return "  - (none detected)"
        return '\n'.join(f"  - {item}" for item in items)


async def bootstrap_project(
    project_path: str,
    app_spec: str,
    project_name: str
) -> BootstrapResult:
    """
    Convenience function to bootstrap a project.

    Args:
        project_path: Path to project directory
        app_spec: Application specification text
        project_name: Name of the project

    Returns:
        BootstrapResult with status
    """
    bootstrapper = ProjectBootstrapper()
    return await bootstrapper.bootstrap(project_path, app_spec, project_name)
