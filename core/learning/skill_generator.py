"""
Skill Generator
===============

Generates native Claude skills from mature expertise.

Key Features:
- Checks expertise maturity (confidence > 0.8, usage > 10)
- Generates .claude/skills/{domain}-expert/SKILL.md
- Includes proper frontmatter (name, description)
- Embeds relevant patterns as skill instructions
- Only generates if expertise is mature enough
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class SkillGenerationResult:
    """Result of skill generation attempt."""
    domain: str
    skill_path: Optional[str] = None
    generated: bool = False
    reason: str = "unknown"  # "created", "updated", "skipped_immature", "skipped_unchanged", "error"


class SkillGenerator:
    """
    Generates native Claude skills from mature expertise.

    Skills are created in .claude/skills/{domain}-expert/SKILL.md
    when expertise crosses the maturity threshold.
    """

    # Maturity thresholds
    MATURITY_CONFIDENCE = 0.8
    MATURITY_USAGE = 10

    def __init__(self, project_path: str):
        """
        Initialize skill generator.

        Args:
            project_path: Path to project root
        """
        self.project_path = Path(project_path)
        self.skills_dir = self.project_path / ".claude" / "skills"

    def should_generate(self, expertise: Dict[str, Any]) -> bool:
        """
        Check if expertise is mature enough for skill generation.

        Args:
            expertise: Expertise data dictionary

        Returns:
            True if expertise meets maturity thresholds
        """
        confidence = expertise.get('confidence', 0)
        usage_count = expertise.get('usage_count', 0)

        meets_confidence = confidence >= self.MATURITY_CONFIDENCE
        meets_usage = usage_count >= self.MATURITY_USAGE

        if not meets_confidence:
            logger.debug(f"Expertise confidence {confidence} < {self.MATURITY_CONFIDENCE}")
        if not meets_usage:
            logger.debug(f"Expertise usage {usage_count} < {self.MATURITY_USAGE}")

        return meets_confidence and meets_usage

    async def generate_skill(
        self,
        domain: str,
        expertise: Dict[str, Any],
        force: bool = False
    ) -> SkillGenerationResult:
        """
        Generate a skill from expertise if mature enough.

        Args:
            domain: Domain name (e.g., 'database', 'api')
            expertise: Expertise data dictionary
            force: Force generation even if immature

        Returns:
            SkillGenerationResult with status
        """
        result = SkillGenerationResult(domain=domain)
        skill_name = f"{domain}-expert"
        skill_dir = self.skills_dir / skill_name
        skill_path = skill_dir / "SKILL.md"

        try:
            # Check maturity
            if not force and not self.should_generate(expertise):
                result.reason = "skipped_immature"
                logger.debug(f"Skipping immature expertise for domain: {domain}")
                return result

            # Check if unchanged
            if not force and skill_path.exists():
                existing_version = self._get_skill_version(skill_path)
                new_version = expertise.get('version', 0)
                if existing_version >= new_version:
                    result.reason = "skipped_unchanged"
                    result.skill_path = str(skill_path)
                    logger.debug(f"Skipping unchanged skill for domain: {domain}")
                    return result

            # Create skill directory
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Generate skill content
            content = self._generate_skill_content(domain, expertise)

            # Write skill file
            skill_path.write_text(content, encoding='utf-8')

            result.generated = True
            result.skill_path = str(skill_path)
            result.reason = "created" if not skill_path.exists() else "updated"

            logger.info(f"Generated skill for domain '{domain}': {skill_path}")

        except Exception as e:
            logger.error(f"Failed to generate skill for domain '{domain}': {e}")
            result.reason = "error"

        return result

    async def generate_all_skills(
        self,
        expertise_by_domain: Dict[str, Dict[str, Any]]
    ) -> List[SkillGenerationResult]:
        """
        Generate skills for all mature domains.

        Args:
            expertise_by_domain: Dict mapping domain -> expertise data

        Returns:
            List of SkillGenerationResult for each domain
        """
        results = []

        for domain, expertise in expertise_by_domain.items():
            result = await self.generate_skill(domain, expertise)
            results.append(result)

        generated_count = sum(1 for r in results if r.generated)
        logger.info(f"Generated {generated_count}/{len(results)} skills")

        return results

    def _get_skill_version(self, skill_path: Path) -> int:
        """
        Extract version from existing skill file.

        Looks for <!-- version: N --> comment in file.
        """
        try:
            content = skill_path.read_text(encoding='utf-8')
            for line in content.split('\n'):
                if '<!-- version:' in line:
                    version_str = line.split('version:')[1].split('-->')[0].strip()
                    return int(version_str)
        except Exception:
            pass
        return 0

    def _generate_skill_content(self, domain: str, expertise: Dict[str, Any]) -> str:
        """
        Generate SKILL.md content.

        Args:
            domain: Domain name
            expertise: Expertise data

        Returns:
            Markdown content for skill file
        """
        patterns = expertise.get('patterns', [])
        techniques = expertise.get('techniques', [])
        core_files = expertise.get('core_files', [])
        learnings = expertise.get('learnings', [])
        confidence = expertise.get('confidence', 0.8)
        version = expertise.get('version', 1)

        # Generate description
        if patterns:
            pattern_names = [p.get('name', '') for p in patterns[:3]]
            description = f"Expert in {', '.join(pattern_names)} for this project"
        else:
            description = f"Expert in {domain} patterns and techniques for this project"

        # Build content
        lines = [
            "---",
            f"name: {domain}-expert",
            f"description: {description}",
            "---",
            "",
            f"<!-- version: {version} -->",
            f"<!-- generated: {datetime.now().isoformat()} -->",
            f"<!-- confidence: {confidence} -->",
            "",
            f"# {domain.title()} Expert Skill",
            "",
            f"You are an expert in **{domain}** for this project. "
            f"Your expertise is based on {len(patterns)} patterns, "
            f"{len(techniques)} techniques, and {len(learnings)} learnings.",
            "",
        ]

        # Core knowledge section
        if core_files:
            lines.extend([
                "## Core Knowledge",
                "",
                "You have deep knowledge of these key files:",
                "",
            ])
            for f in core_files[:10]:
                lines.append(f"- `{f}`")
            lines.append("")

        # Patterns section
        if patterns:
            lines.extend([
                "## Patterns",
                "",
                "Apply these patterns when working in this domain:",
                "",
            ])
            for p in patterns[:8]:
                name = p.get('name', 'Pattern')
                when_to_use = p.get('when_to_use', '')
                code = p.get('code', '')

                lines.append(f"### {name}")
                if when_to_use:
                    lines.append(f"\n{when_to_use}\n")
                if code:
                    lines.append("```python")
                    for code_line in code.split('\n')[:15]:
                        lines.append(code_line)
                    lines.append("```")
                lines.append("")

        # Techniques section
        if techniques:
            lines.extend([
                "## Techniques",
                "",
            ])
            for t in techniques[:5]:
                name = t.get('name', 'Technique')
                steps = t.get('steps', [])

                lines.append(f"### {name}")
                if steps:
                    lines.append("")
                    for i, step in enumerate(steps[:7], 1):
                        lines.append(f"{i}. {step}")
                lines.append("")

        # Guidelines from learnings
        success_learnings = [l for l in learnings if l.get('type') == 'success']
        failure_learnings = [l for l in learnings if l.get('type') == 'failure']

        if success_learnings or failure_learnings:
            lines.extend([
                "## Guidelines",
                "",
            ])

            if success_learnings:
                lines.append("**Do:**")
                for l in success_learnings[-5:]:
                    lines.append(f"- {l.get('lesson', '')}")
                lines.append("")

            if failure_learnings:
                lines.append("**Avoid:**")
                for l in failure_learnings[-5:]:
                    lines.append(f"- {l.get('lesson', '')}")
                lines.append("")

        # Usage instructions
        lines.extend([
            "## When to Use This Skill",
            "",
            f"Activate this skill when:",
            f"- Working with {domain}-related code",
            f"- Debugging {domain} issues",
            f"- Implementing new {domain} features",
            "",
            "This skill will automatically apply the patterns and techniques "
            "learned from previous sessions in this project.",
        ])

        return '\n'.join(lines)

    def list_generated_skills(self) -> List[str]:
        """
        List all generated skills.

        Returns:
            List of skill names
        """
        skills = []
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skills.append(skill_dir.name)
        return skills
