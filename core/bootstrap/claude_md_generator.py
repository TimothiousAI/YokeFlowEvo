"""
CLAUDE.md Generator
====================

Generates CLAUDE.md from app_spec analysis.

Key Features:
- Parse app_spec for project name, description, technologies
- Generate structured CLAUDE.md with relevant sections
- Include YokeFlow-specific guidance
- Support template variables
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import re
import logging

from core.bootstrap.domain_detector import DomainDetector, DetectedDomain

logger = logging.getLogger(__name__)


@dataclass
class GeneratedCLAUDEMD:
    """Result of CLAUDE.md generation."""
    content: str
    detected_stack: Dict[str, str] = field(default_factory=dict)
    predicted_structure: List[str] = field(default_factory=list)
    project_type: str = "general"


class CLAUDEMDGenerator:
    """
    Generates CLAUDE.md content from app specification.

    Creates a structured markdown file with project-specific
    guidance for Claude Code.
    """

    # Tech-specific commands
    TECH_COMMANDS = {
        'react': [
            '`npm install` - Install dependencies',
            '`npm run dev` - Start development server',
            '`npm run build` - Build for production',
            '`npm test` - Run tests',
        ],
        'vue': [
            '`npm install` - Install dependencies',
            '`npm run serve` - Start development server',
            '`npm run build` - Build for production',
            '`npm run test:unit` - Run unit tests',
        ],
        'fastapi': [
            '`pip install -r requirements.txt` - Install dependencies',
            '`uvicorn main:app --reload` - Start development server',
            '`pytest` - Run tests',
            '`alembic upgrade head` - Run database migrations',
        ],
        'django': [
            '`pip install -r requirements.txt` - Install dependencies',
            '`python manage.py runserver` - Start development server',
            '`python manage.py test` - Run tests',
            '`python manage.py migrate` - Run database migrations',
        ],
        'express': [
            '`npm install` - Install dependencies',
            '`npm run dev` - Start development server',
            '`npm test` - Run tests',
        ],
        'nextjs': [
            '`npm install` - Install dependencies',
            '`npm run dev` - Start development server',
            '`npm run build` - Build for production',
            '`npm test` - Run tests',
        ],
    }

    # Predicted project structures
    STRUCTURE_TEMPLATES = {
        'fullstack': [
            'src/',
            '  components/',
            '  pages/',
            '  api/',
            '  lib/',
            'public/',
            'tests/',
            'package.json',
        ],
        'api': [
            'api/',
            '  routes/',
            '  models/',
            '  services/',
            'core/',
            'tests/',
            'requirements.txt or package.json',
        ],
        'frontend': [
            'src/',
            '  components/',
            '  pages/',
            '  styles/',
            '  hooks/',
            'public/',
            'package.json',
        ],
    }

    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize CLAUDE.md generator.

        Args:
            templates_dir: Path to templates directory (optional)
        """
        self.detector = DomainDetector()

        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            self.templates_dir = Path(__file__).parent.parent.parent / 'templates' / 'claude-sdk-project'

    async def generate(
        self,
        app_spec: str,
        project_name: str,
        detected_domains: Optional[List[DetectedDomain]] = None
    ) -> GeneratedCLAUDEMD:
        """
        Generate CLAUDE.md content from app specification.

        Args:
            app_spec: The application specification text
            project_name: Name of the project
            detected_domains: Pre-detected domains (optional)

        Returns:
            GeneratedCLAUDEMD with content and metadata
        """
        # Detect domains if not provided
        if detected_domains is None:
            detected_domains = self.detector.detect_domains(app_spec)

        # Get tech stack
        detected_stack = self.detector.get_all_detected_stack(app_spec)

        # Get project type
        project_type = self.detector.classify_project_type(app_spec)

        # Predict structure
        predicted_structure = self._predict_structure(project_type, detected_domains)

        # Extract description
        description = self._extract_description(app_spec)

        # Generate content
        content = self._generate_content(
            project_name=project_name,
            description=description,
            detected_stack=detected_stack,
            detected_domains=detected_domains,
            predicted_structure=predicted_structure,
            project_type=project_type
        )

        return GeneratedCLAUDEMD(
            content=content,
            detected_stack=detected_stack,
            predicted_structure=predicted_structure,
            project_type=project_type
        )

    def _extract_description(self, app_spec: str) -> str:
        """
        Extract project description from app_spec.

        Looks for first paragraph or first few sentences.
        """
        if not app_spec:
            return "A new project generated by YokeFlow."

        # Split into lines and find first non-empty, non-header line
        lines = app_spec.strip().split('\n')
        description_lines = []

        for line in lines:
            line = line.strip()
            # Skip empty lines, headers, and bullet points at start
            if not line:
                if description_lines:
                    break  # End of first paragraph
                continue
            if line.startswith('#'):
                continue
            if line.startswith('-') and not description_lines:
                continue

            description_lines.append(line)

            # Limit to first 2-3 sentences
            if len(description_lines) >= 3:
                break

        if description_lines:
            description = ' '.join(description_lines)
            # Truncate to reasonable length
            if len(description) > 300:
                description = description[:297] + '...'
            return description

        return "A new project generated by YokeFlow."

    def _predict_structure(
        self,
        project_type: str,
        detected_domains: List[DetectedDomain]
    ) -> List[str]:
        """
        Predict project structure based on type and domains.
        """
        base_structure = self.STRUCTURE_TEMPLATES.get(
            project_type,
            self.STRUCTURE_TEMPLATES['api']
        )

        structure = list(base_structure)

        # Add domain-specific directories
        for domain in detected_domains:
            for suggested_file in domain.suggested_files[:2]:
                if suggested_file not in '\n'.join(structure):
                    structure.append(suggested_file)

        return structure

    def _generate_content(
        self,
        project_name: str,
        description: str,
        detected_stack: Dict[str, str],
        detected_domains: List[DetectedDomain],
        predicted_structure: List[str],
        project_type: str
    ) -> str:
        """
        Generate the full CLAUDE.md content.
        """
        sections = []

        # Header
        sections.append("# CLAUDE.md\n")
        sections.append("This file provides guidance to Claude Code when working with this repository.\n")

        # What This Is
        sections.append("## What This Is\n")
        sections.append(f"**{project_name}** - {description}\n")
        sections.append(f"**Status**: In Development (Generated by YokeFlow)\n")
        sections.append(f"**Type**: {project_type.title()} Application\n")

        # Tech Stack
        sections.append("## Tech Stack\n")
        if detected_stack:
            for layer, tech in detected_stack.items():
                sections.append(f"- **{layer.title()}**: {tech.title()}")
            sections.append("")
        else:
            sections.append("- To be determined during development\n")

        # Project Structure
        sections.append("## Project Structure\n")
        sections.append("```")
        sections.append(project_name + "/")
        for item in predicted_structure:
            sections.append(f"  {item}")
        sections.append("```\n")

        # Key Commands
        sections.append("## Key Commands\n")
        commands = self._get_commands(detected_stack)
        for cmd in commands:
            sections.append(cmd)
        sections.append("")

        # Development Workflow
        sections.append("## Development Workflow\n")
        sections.append("1. Read relevant files before making changes")
        sections.append("2. Follow existing patterns in the codebase")
        sections.append("3. Run tests after making changes")
        sections.append("4. Commit with descriptive messages\n")

        # Detected Domains
        if detected_domains:
            sections.append("## Detected Domains\n")
            for domain in detected_domains[:5]:
                sections.append(f"- **{domain.name.title()}**: {domain.description}")
            sections.append("")

        # Important Files
        sections.append("## Important Files\n")
        sections.append("- `app_spec.txt` - Project specification")
        sections.append("- `CLAUDE.md` - This file (guidance for Claude)")
        sections.append("- `.claude/` - Claude SDK configuration and expertise\n")

        # YokeFlow Notes
        sections.append("## YokeFlow Notes\n")
        sections.append("This project was generated by YokeFlow autonomous development platform.\n")
        sections.append("- **Expertise**: Domain expertise is stored in `.claude/commands/experts/`")
        sections.append("- **Skills**: As expertise matures, native skills are generated in `.claude/skills/`")
        sections.append("- **Learning**: The system learns from each session to improve future development\n")

        # Footer
        sections.append("---\n")
        sections.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d')}")
        sections.append("**By**: [YokeFlow](https://github.com/yokeflow/yokeflow)")

        return '\n'.join(sections)

    def _get_commands(self, detected_stack: Dict[str, str]) -> List[str]:
        """
        Get relevant commands based on detected stack.
        """
        commands = []

        # Add commands for detected technologies
        for layer, tech in detected_stack.items():
            tech_lower = tech.lower()
            if tech_lower in self.TECH_COMMANDS:
                commands.extend(self.TECH_COMMANDS[tech_lower])

        # Default commands if none detected
        if not commands:
            commands = [
                '`npm install` or `pip install -r requirements.txt` - Install dependencies',
                '`npm run dev` or `python main.py` - Start development',
                '`npm test` or `pytest` - Run tests',
            ]

        # Deduplicate while preserving order
        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd not in seen:
                seen.add(cmd)
                unique_commands.append(cmd)

        return unique_commands
