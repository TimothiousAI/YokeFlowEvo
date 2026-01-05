"""
Expertise Manager
=================

Manages domain-specific expertise accumulated from completed sessions.

Key Features:
- Classifies tasks into domains (database, api, frontend, testing, security, deployment, general)
- Extracts learnings from session logs (failures, patterns, techniques)
- Validates and prunes stale expertise
- Enforces line limits to prevent token bloat
- Self-improves by scanning codebase
- Formats expertise for prompt injection

Expertise Structure (JSONB):
{
    "core_files": ["path/to/file.py", ...],
    "patterns": [{"name": "...", "code": "...", "when_to_use": "..."}],
    "techniques": [{"name": "...", "steps": [...]}],
    "learnings": [{"type": "failure|success", "lesson": "...", "date": "..."}]
}
"""

from typing import Dict, List, Any, Optional
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

# Domain classification constants
DOMAINS = ['database', 'api', 'frontend', 'testing', 'security', 'deployment', 'general']
MAX_EXPERTISE_LINES = 1000

# Keywords for domain classification (lowercase for case-insensitive matching)
DOMAIN_KEYWORDS = {
    'database': ['schema', 'migration', 'query', 'table', 'index', 'sql', 'database', 'postgres',
                 'mysql', 'sqlite', 'column', 'row', 'select', 'insert', 'update', 'delete'],
    'api': ['endpoint', 'route', 'rest', 'request', 'response', 'http', 'api', 'fastapi',
            'flask', 'express', 'handler', 'controller', 'middleware', 'get', 'post', 'put', 'patch'],
    'frontend': ['component', 'react', 'css', 'ui', 'render', 'state', 'frontend', 'html',
                 'jsx', 'tsx', 'vue', 'angular', 'style', 'layout', 'button', 'form', 'input'],
    'testing': ['test', 'assert', 'mock', 'fixture', 'coverage', 'pytest', 'unittest',
                'jest', 'mocha', 'spec', 'testcase', 'expect', 'verify'],
    'security': ['auth', 'token', 'encrypt', 'permission', 'cors', 'security', 'password',
                 'jwt', 'oauth', 'authentication', 'authorization', 'credential', 'hash'],
    'deployment': ['docker', 'deploy', 'ci', 'build', 'environment', 'deployment', 'container',
                   'kubernetes', 'pipeline', 'release', 'production', 'staging', 'config']
}

# File extension patterns for domain classification
DOMAIN_FILE_PATTERNS = {
    'database': ['.sql', 'migration', 'schema'],
    'api': ['route', 'handler', 'controller', 'endpoint', 'api'],
    'frontend': ['.tsx', '.jsx', '.css', '.scss', '.html', 'component'],
    'testing': ['.test.', '.spec.', 'test_', '_test'],
    'security': ['auth', 'security', 'permission'],
    'deployment': ['docker', '.yml', '.yaml', 'deploy', '.sh']
}


@dataclass
class ExpertiseFile:
    """
    Dataclass representing a domain expertise file.

    Attributes:
        domain: Domain name (e.g., 'database', 'api', 'frontend')
        content: JSONB content dict with core_files, patterns, techniques, learnings
        version: Version number (incremented on each save)
        line_count: Approximate line count for token budget management
        validated_at: Timestamp of last validation (None if never validated)
    """
    domain: str
    content: Dict[str, Any]
    version: int
    line_count: int
    validated_at: Optional[datetime] = None


class ExpertiseManager:
    """
    Manages accumulated expertise for self-learning system.

    Expertise is stored per domain with automatic versioning,
    validation, and line limit enforcement.
    """

    def __init__(self, project_id: UUID, db_connection: Any):
        """
        Initialize expertise manager.

        Args:
            project_id: Project UUID
            db_connection: Database connection for persistence
        """
        self.project_id = project_id
        self.db = db_connection
        logger.info(f"ExpertiseManager initialized for project {project_id}")

    async def get_expertise(self, domain: str) -> Optional[ExpertiseFile]:
        """
        Get expertise for a specific domain.

        Args:
            domain: Domain name (database/api/frontend/etc.)

        Returns:
            ExpertiseFile object or None if not found
        """
        if domain not in DOMAINS:
            logger.warning(f"Invalid domain '{domain}', defaulting to 'general'")
            domain = 'general'

        try:
            record = await self.db.get_expertise(self.project_id, domain)
            if not record:
                logger.debug(f"No expertise found for domain '{domain}'")
                return None

            # Parse content from JSONB string if needed
            content = record['content']
            if isinstance(content, str):
                content = json.loads(content)

            return ExpertiseFile(
                domain=record['domain'],
                content=content,
                version=record['version'],
                line_count=record['line_count'],
                validated_at=record.get('validated_at')
            )
        except Exception as e:
            logger.error(f"Failed to get expertise for domain '{domain}': {e}")
            return None

    async def get_all_expertise(self) -> Dict[str, ExpertiseFile]:
        """
        Get expertise for all domains.

        Returns:
            Dict mapping domain -> ExpertiseFile object
        """
        try:
            domains_list = await self.db.list_expertise_domains(self.project_id)
            result = {}

            for domain_record in domains_list:
                domain = domain_record['domain']
                expertise = await self.get_expertise(domain)
                if expertise:
                    result[domain] = expertise

            logger.info(f"Retrieved expertise for {len(result)} domains")
            return result
        except Exception as e:
            logger.error(f"Failed to get all expertise: {e}")
            return {}

    def classify_domain(self, task_description: str, file_paths: List[str]) -> str:
        """
        Classify task into appropriate domain.

        Args:
            task_description: Task description text
            file_paths: List of file paths involved

        Returns:
            Domain name (one of DOMAINS)
        """
        # Initialize scores for each domain
        domain_scores = {domain: 0 for domain in DOMAINS if domain != 'general'}

        # Score based on task description keywords
        description_lower = task_description.lower()
        for domain, keywords in DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in description_lower:
                    domain_scores[domain] += 1

        # Score based on file path patterns
        for file_path in file_paths:
            file_lower = file_path.lower()
            for domain, patterns in DOMAIN_FILE_PATTERNS.items():
                for pattern in patterns:
                    if pattern in file_lower:
                        # File path matches are weighted more heavily
                        domain_scores[domain] += 2

        # Find domain with highest score
        max_score = max(domain_scores.values()) if domain_scores else 0

        if max_score == 0:
            logger.debug(f"No domain keywords found, classifying as 'general'")
            return 'general'

        # Get domain with highest score (first one if tie)
        best_domain = max(domain_scores.items(), key=lambda x: x[1])[0]

        logger.debug(f"Classified task as '{best_domain}' domain (score: {domain_scores[best_domain]})")
        return best_domain

    async def learn_from_session(
        self,
        session_id: UUID,
        task: Dict[str, Any],
        logs: str
    ) -> None:
        """
        Extract and store learnings from a completed session.

        Args:
            session_id: Session UUID
            task: Task dictionary
            logs: Session log content
        """
        try:
            # Classify domain from task
            task_desc = task.get('description', '') + ' ' + task.get('action', '')
            file_paths = self._extract_file_paths_from_logs(logs)
            domain = self.classify_domain(task_desc, file_paths)

            # Get or create expertise for this domain
            expertise = await self.get_expertise(domain)
            if not expertise:
                # Initialize new expertise
                content = {
                    'core_files': [],
                    'patterns': [],
                    'techniques': [],
                    'learnings': []
                }
            else:
                content = expertise.content

            # Extract learnings from logs
            learnings_added = []

            # Check for errors/failures
            if 'error' in logs.lower() or 'traceback' in logs.lower() or 'failed' in logs.lower():
                failure_learning = self._extract_failure_learning(logs)
                if failure_learning:
                    content['learnings'].append(failure_learning)
                    learnings_added.append(failure_learning['lesson'])

            # Extract successful patterns
            if task.get('status') == 'completed' or task.get('done'):
                success_patterns = self._extract_success_patterns(logs, task_desc)
                for pattern in success_patterns:
                    if pattern not in content['techniques']:
                        content['techniques'].append(pattern)
                        learnings_added.append(f"Technique: {pattern['name']}")

                # Extract tool usage patterns
                tool_patterns = self._extract_tool_patterns(logs)
                if 'patterns' not in content:
                    content['patterns'] = []

                for tool_pattern in tool_patterns:
                    # Check if pattern already exists
                    existing = any(p.get('name') == tool_pattern['name'] for p in content['patterns'])
                    if not existing:
                        content['patterns'].append(tool_pattern)
                        learnings_added.append(f"Pattern: {tool_pattern['name']}")

            # Update core files list with modified files
            modified_files = self._extract_modified_files(logs)
            for file_path in modified_files:
                if file_path not in content['core_files'] and len(content['core_files']) < 50:
                    content['core_files'].append(file_path)

            # Also add files from generic file path extraction
            for file_path in file_paths:
                if file_path not in content['core_files'] and len(content['core_files']) < 50:
                    content['core_files'].append(file_path)

            # Save updated expertise if we learned something
            if learnings_added:
                # Calculate approximate line count
                import json
                line_count = len(json.dumps(content, indent=2).split('\n'))

                # Save to database
                saved = await self.db.save_expertise(
                    self.project_id,
                    domain,
                    content,
                    line_count
                )

                # Record update in history
                await self.db.record_expertise_update(
                    expertise_id=saved['id'],
                    session_id=session_id,
                    change_type='learned',
                    summary=f"Learned {len(learnings_added)} insights from session",
                    diff='\n'.join(learnings_added)
                )

                logger.info(f"Learned {len(learnings_added)} insights for '{domain}' domain from session {session_id}")
            else:
                logger.debug(f"No new learnings extracted from session {session_id}")

        except Exception as e:
            logger.error(f"Failed to learn from session {session_id}: {e}")

    def _extract_file_paths_from_logs(self, logs: str) -> List[str]:
        """Extract file paths from log content."""
        import re
        # Look for common file path patterns
        paths = set()

        # Match paths like "core/learning/expertise_manager.py"
        for match in re.finditer(r'[\w/]+\.[\w]+', logs):
            path = match.group(0)
            if '/' in path or '\\' in path:
                paths.add(path)

        return list(paths)[:20]  # Limit to 20 files

    def _extract_failure_learning(self, logs: str) -> Optional[Dict[str, Any]]:
        """Extract learning from failure in logs."""
        import re
        from datetime import datetime

        # Look for error messages
        error_match = re.search(r'(Error|Exception|Failed):\s*(.+)', logs, re.IGNORECASE)
        if error_match:
            error_type = error_match.group(1)
            error_msg = error_match.group(2)[:200]  # Limit length

            return {
                'type': 'failure',
                'lesson': f"{error_type}: {error_msg}",
                'date': datetime.now().isoformat()
            }

        return None

    def _extract_success_patterns(self, logs: str, task_desc: str) -> List[Dict[str, Any]]:
        """Extract successful techniques from logs."""
        patterns = []

        # Look for tool usage patterns
        if 'Edit' in logs and 'Read' in logs:
            patterns.append({
                'name': 'Read-Edit pattern',
                'steps': ['Read file to understand context', 'Edit file with changes']
            })

        if 'test' in logs.lower() and 'pass' in logs.lower():
            patterns.append({
                'name': 'Test-driven approach',
                'steps': ['Write tests', 'Implement functionality', 'Verify tests pass']
            })

        return patterns

    def _extract_tool_patterns(self, logs: str) -> List[Dict[str, Any]]:
        """
        Extract tool usage patterns from logs.

        Detects sequences like Read -> Edit -> Test and other successful workflows.

        Args:
            logs: Session log content

        Returns:
            List of pattern dictionaries with name, tools, and description
        """
        patterns = []

        # Detect Read -> Edit -> Test sequence
        if 'Read' in logs and 'Edit' in logs:
            # Check order (Read should come before Edit)
            read_pos = logs.find('Read')
            edit_pos = logs.find('Edit')

            if read_pos < edit_pos:
                pattern = {
                    'name': 'Read-Edit workflow',
                    'tools': ['Read', 'Edit'],
                    'description': 'Read file to understand context, then edit with changes'
                }

                # Check if followed by testing
                if 'test' in logs[edit_pos:].lower() or 'pytest' in logs[edit_pos:].lower():
                    pattern['name'] = 'Read-Edit-Test workflow'
                    pattern['tools'].append('Test')
                    pattern['description'] += ', followed by testing'

                patterns.append(pattern)

        # Detect Write -> Bash sequence (e.g., creating a file then running it)
        if 'Write' in logs and 'Bash' in logs:
            write_pos = logs.find('Write')
            bash_pos = logs.find('Bash')

            if write_pos < bash_pos:
                patterns.append({
                    'name': 'Write-Execute workflow',
                    'tools': ['Write', 'Bash'],
                    'description': 'Create file then execute with bash command'
                })

        # Detect Grep -> Read sequence (search then examine)
        if 'Grep' in logs and 'Read' in logs:
            grep_pos = logs.find('Grep')
            read_pos = logs.find('Read')

            if grep_pos < read_pos:
                patterns.append({
                    'name': 'Search-Examine workflow',
                    'tools': ['Grep', 'Read'],
                    'description': 'Search for pattern, then read matching files'
                })

        # Detect browser verification pattern
        if 'browser' in logs.lower() and ('screenshot' in logs.lower() or 'navigate' in logs.lower()):
            patterns.append({
                'name': 'Browser verification workflow',
                'tools': ['Browser'],
                'description': 'Verify changes through browser testing'
            })

        return patterns

    def _extract_modified_files(self, logs: str) -> List[str]:
        """
        Extract list of modified files from logs.

        Looks for Edit and Write tool calls to identify changed files.

        Args:
            logs: Session log content

        Returns:
            List of file paths that were modified
        """
        import re
        modified_files = set()

        # Look for Edit tool calls: Edit(file_path="...")
        edit_pattern = r'Edit\([^)]*file_path["\s]*[:=]["\s]*([^"\']+)["\']'
        for match in re.finditer(edit_pattern, logs):
            file_path = match.group(1)
            if file_path and not file_path.startswith('<'):
                modified_files.add(file_path)

        # Look for Write tool calls: Write(file_path="...")
        write_pattern = r'Write\([^)]*file_path["\s]*[:=]["\s]*([^"\']+)["\']'
        for match in re.finditer(write_pattern, logs):
            file_path = match.group(1)
            if file_path and not file_path.startswith('<'):
                modified_files.add(file_path)

        # Also look for simple file mentions in edit/write contexts
        if 'Edit' in logs or 'Write' in logs:
            # Match file paths with extensions
            for match in re.finditer(r'[\w/\\]+\.\w+', logs):
                path = match.group(0)
                if '/' in path or '\\' in path:
                    # Check if it appears near Edit/Write mentions
                    pos = logs.find(path)
                    nearby = logs[max(0, pos-100):min(len(logs), pos+100)]
                    if 'Edit' in nearby or 'Write' in nearby:
                        modified_files.add(path)

        return sorted(list(modified_files))[:20]  # Limit to 20 files

    async def validate_expertise(self, domain: str) -> Dict[str, Any]:
        """
        Validate and prune expertise for a domain.

        Args:
            domain: Domain name

        Returns:
            Validation report with changes made
        """
        try:
            from datetime import datetime, timedelta
            from pathlib import Path

            # Get existing expertise
            expertise = await self.get_expertise(domain)
            if not expertise:
                logger.info(f"No expertise found for domain '{domain}', nothing to validate")
                return {'status': 'no_expertise', 'changes': []}

            content = expertise.content
            changes = []

            # 1. Verify referenced core files still exist
            if 'core_files' in content:
                original_count = len(content['core_files'])
                valid_files = []

                for file_path in content['core_files']:
                    # Check if file exists (relative to project root)
                    file_exists = Path(file_path).exists()
                    if file_exists:
                        valid_files.append(file_path)
                    else:
                        changes.append(f"Removed non-existent file: {file_path}")

                content['core_files'] = valid_files
                removed_count = original_count - len(valid_files)
                if removed_count > 0:
                    logger.info(f"Removed {removed_count} non-existent files from '{domain}' expertise")

            # 2. Prune stale failure learnings (older than 30 days)
            if 'learnings' in content:
                original_count = len(content['learnings'])
                cutoff_date = datetime.now() - timedelta(days=30)
                fresh_learnings = []

                for learning in content['learnings']:
                    # Only prune failures, keep successes
                    if learning.get('type') == 'failure':
                        learning_date_str = learning.get('date')
                        if learning_date_str:
                            try:
                                learning_date = datetime.fromisoformat(learning_date_str.replace('Z', '+00:00'))
                                if learning_date > cutoff_date:
                                    fresh_learnings.append(learning)
                                else:
                                    changes.append(f"Pruned stale failure: {learning.get('lesson', '')[:50]}...")
                            except (ValueError, AttributeError):
                                # Keep if date parsing fails
                                fresh_learnings.append(learning)
                        else:
                            # Keep if no date
                            fresh_learnings.append(learning)
                    else:
                        # Keep non-failure learnings
                        fresh_learnings.append(learning)

                content['learnings'] = fresh_learnings
                pruned_count = original_count - len(fresh_learnings)
                if pruned_count > 0:
                    logger.info(f"Pruned {pruned_count} stale learnings from '{domain}' expertise")

            # 3. Remove duplicate entries in patterns
            if 'patterns' in content:
                original_count = len(content['patterns'])
                seen_names = set()
                unique_patterns = []

                for pattern in content['patterns']:
                    pattern_name = pattern.get('name', '')
                    if pattern_name not in seen_names:
                        seen_names.add(pattern_name)
                        unique_patterns.append(pattern)
                    else:
                        changes.append(f"Removed duplicate pattern: {pattern_name}")

                content['patterns'] = unique_patterns
                dup_count = original_count - len(unique_patterns)
                if dup_count > 0:
                    logger.info(f"Removed {dup_count} duplicate patterns from '{domain}' expertise")

            # 4. Remove duplicate entries in techniques
            if 'techniques' in content:
                original_count = len(content['techniques'])
                seen_names = set()
                unique_techniques = []

                for technique in content['techniques']:
                    technique_name = technique.get('name', '')
                    if technique_name not in seen_names:
                        seen_names.add(technique_name)
                        unique_techniques.append(technique)
                    else:
                        changes.append(f"Removed duplicate technique: {technique_name}")

                content['techniques'] = unique_techniques
                dup_count = original_count - len(unique_techniques)
                if dup_count > 0:
                    logger.info(f"Removed {dup_count} duplicate techniques from '{domain}' expertise")

            # Save updated expertise with validation timestamp
            if changes:
                # Calculate line count
                line_count = len(json.dumps(content, indent=2).split('\n'))

                # Save to database
                saved = await self.db.save_expertise(
                    self.project_id,
                    domain,
                    content,
                    line_count
                )

                # Update validation timestamp
                async with self.db.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE expertise_files
                        SET validated_at = NOW()
                        WHERE id = $1
                        """,
                        saved['id']
                    )

                # Record validation in history
                await self.db.record_expertise_update(
                    expertise_id=saved['id'],
                    session_id=None,
                    change_type='validated',
                    summary=f"Validated expertise: {len(changes)} changes",
                    diff='\n'.join(changes)
                )

                logger.info(f"Validated '{domain}' expertise with {len(changes)} changes")

            return {
                'status': 'validated',
                'domain': domain,
                'changes': changes,
                'changes_count': len(changes)
            }

        except Exception as e:
            logger.error(f"Failed to validate expertise for domain '{domain}': {e}")
            return {
                'status': 'error',
                'error': str(e),
                'changes': []
            }

    async def self_improve(self, domain: str) -> None:
        """
        Scan codebase to discover patterns and update expertise.

        Args:
            domain: Domain name
        """
        # Stub - will be implemented in Epic 94
        logger.warning("ExpertiseManager.self_improve() not yet implemented")

    def format_for_prompt(self, domain: str) -> str:
        """
        Format expertise as markdown for prompt injection.

        Args:
            domain: Domain name

        Returns:
            Formatted markdown string (limited to MAX_EXPERTISE_LINES)
        """
        # Stub - will be implemented in Epic 94
        logger.warning("ExpertiseManager.format_for_prompt() not yet implemented")
        return ""
