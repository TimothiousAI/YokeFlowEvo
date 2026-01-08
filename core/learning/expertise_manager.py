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

    async def get_expertise_history(self, domain: str) -> List[Dict[str, Any]]:
        """
        Get update history for expertise in a specific domain.

        Provides audit trail of all changes made to expertise over time,
        including who made changes, when, and what was modified.

        Args:
            domain: Domain name

        Returns:
            List of update records with details:
            - id: Update record ID
            - expertise_id: ID of expertise file
            - session_id: Session that made the change (if applicable)
            - change_type: Type of change (learned, validated, pruned, self_improved)
            - summary: Brief description of changes
            - diff: Detailed diff of changes
            - created_at: Timestamp of update
        """
        try:
            # Get expertise for this domain
            expertise = await self.get_expertise(domain)
            if not expertise:
                logger.debug(f"No expertise found for domain '{domain}', no history available")
                return []

            # Get the expertise ID from database
            record = await self.db.get_expertise(self.project_id, domain)
            if not record:
                return []

            expertise_id = record['id']

            # Get history from database
            history = await self.db.get_expertise_history(expertise_id)

            logger.debug(f"Retrieved {len(history)} history records for '{domain}' domain")
            return history

        except Exception as e:
            logger.error(f"Failed to get expertise history for domain '{domain}': {e}")
            return []

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

    async def self_improve(self, domain: str) -> Dict[str, Any]:
        """
        Scan codebase to discover patterns and update expertise.

        Performs intelligent codebase scanning to extract:
        - Relevant files for the domain
        - Common patterns and conventions
        - Library usage patterns
        - Code style preferences

        Args:
            domain: Domain name

        Returns:
            Dict with scan results and update summary
        """
        try:
            from pathlib import Path
            import re

            logger.info(f"Starting self-improvement scan for domain '{domain}'")

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

            # Initialize scan results
            discovered_files = []
            discovered_patterns = []
            discovered_libraries = set()

            # 1. Scan for relevant files (limit to 50 files to avoid token bloat)
            relevant_files = self._scan_relevant_files(domain, limit=50)
            logger.debug(f"Found {len(relevant_files)} relevant files for '{domain}'")

            # 2. Extract patterns and conventions from files
            file_scan_limit = min(20, len(relevant_files))  # Scan max 20 files deeply
            for file_path in relevant_files[:file_scan_limit]:
                try:
                    # Read file content (limit to first 500 lines to avoid huge files)
                    path_obj = Path(file_path)
                    if not path_obj.exists() or not path_obj.is_file():
                        continue

                    # Skip binary files, large files
                    if path_obj.stat().st_size > 500_000:  # Skip files > 500KB
                        continue

                    with open(path_obj, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[:500]  # Max 500 lines
                        file_content = ''.join(lines)

                    # Extract imports/libraries
                    libs = self._extract_libraries(file_content, file_path)
                    discovered_libraries.update(libs)

                    # Extract code patterns
                    patterns = self._extract_code_patterns(file_content, file_path, domain)
                    discovered_patterns.extend(patterns)

                    # Add to discovered files
                    if file_path not in content['core_files']:
                        discovered_files.append(file_path)

                except Exception as e:
                    logger.debug(f"Failed to scan file {file_path}: {e}")
                    continue

            # 3. Update expertise content
            changes_made = []

            # Add new files (limit total to 50)
            for file_path in discovered_files:
                if file_path not in content['core_files'] and len(content['core_files']) < 50:
                    content['core_files'].append(file_path)
                    changes_made.append(f"Added core file: {file_path}")

            # Add discovered patterns (avoid duplicates)
            for pattern in discovered_patterns:
                pattern_name = pattern.get('name', '')
                existing = any(p.get('name') == pattern_name for p in content.get('patterns', []))
                if not existing and len(content.get('patterns', [])) < 30:
                    if 'patterns' not in content:
                        content['patterns'] = []
                    content['patterns'].append(pattern)
                    changes_made.append(f"Added pattern: {pattern_name}")

            # Add library usage insights
            if discovered_libraries:
                libraries_list = sorted(list(discovered_libraries))[:20]  # Limit to 20 libs
                library_insight = {
                    'type': 'success',
                    'lesson': f"Common libraries in {domain}: {', '.join(libraries_list)}",
                    'date': datetime.now().isoformat()
                }

                # Check if similar library insight exists
                existing_lib_insight = any(
                    'Common libraries' in l.get('lesson', '')
                    for l in content.get('learnings', [])
                )

                if not existing_lib_insight:
                    if 'learnings' not in content:
                        content['learnings'] = []
                    content['learnings'].append(library_insight)
                    changes_made.append(f"Added library insight: {len(libraries_list)} libraries")

            # 4. Save updated expertise if changes were made
            if changes_made:
                # Calculate line count
                line_count = len(json.dumps(content, indent=2).split('\n'))

                # Enforce line limit
                if line_count > MAX_EXPERTISE_LINES:
                    logger.warning(f"Expertise for '{domain}' exceeds {MAX_EXPERTISE_LINES} lines, pruning...")
                    content = self._prune_expertise_to_limit(content)
                    line_count = len(json.dumps(content, indent=2).split('\n'))
                    changes_made.append(f"Pruned to {MAX_EXPERTISE_LINES} line limit")

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
                    session_id=None,
                    change_type='self_improved',
                    summary=f"Self-improvement scan: {len(changes_made)} changes",
                    diff='\n'.join(changes_made)
                )

                logger.info(f"Self-improvement scan for '{domain}' complete: {len(changes_made)} changes")

                return {
                    'status': 'success',
                    'domain': domain,
                    'files_scanned': file_scan_limit,
                    'files_added': len(discovered_files),
                    'patterns_added': len([c for c in changes_made if 'pattern' in c.lower()]),
                    'changes': changes_made,
                    'line_count': line_count
                }
            else:
                logger.info(f"Self-improvement scan for '{domain}' found no new insights")
                return {
                    'status': 'no_changes',
                    'domain': domain,
                    'files_scanned': file_scan_limit
                }

        except Exception as e:
            logger.error(f"Failed to self-improve for domain '{domain}': {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _scan_relevant_files(self, domain: str, limit: int = 50) -> List[str]:
        """
        Scan codebase for files relevant to domain.

        Args:
            domain: Domain name
            limit: Maximum number of files to return

        Returns:
            List of file paths relevant to the domain
        """
        from pathlib import Path
        import os

        relevant_files = []
        search_patterns = DOMAIN_FILE_PATTERNS.get(domain, [])

        try:
            # Walk project directory
            project_root = Path.cwd()

            # Directories to skip
            skip_dirs = {
                '.git', '__pycache__', 'node_modules', '.venv', 'venv',
                'dist', 'build', '.pytest_cache', '.mypy_cache', '.tox',
                '.worktrees', '.expertise', 'logs'
            }

            for root, dirs, files in os.walk(project_root):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for filename in files:
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, project_root)

                    # Check if file matches domain patterns
                    file_lower = filename.lower()
                    path_lower = rel_path.lower()

                    # Check file extension and path patterns
                    matches_pattern = any(
                        pattern in file_lower or pattern in path_lower
                        for pattern in search_patterns
                    )

                    if matches_pattern:
                        relevant_files.append(rel_path)

                        if len(relevant_files) >= limit:
                            return relevant_files

            return relevant_files

        except Exception as e:
            logger.error(f"Failed to scan files for domain '{domain}': {e}")
            return []

    def _extract_libraries(self, file_content: str, file_path: str) -> set:
        """
        Extract library/package imports from file content.

        Args:
            file_content: Content of the file
            file_path: Path to the file (for language detection)

        Returns:
            Set of library names
        """
        import re

        libraries = set()

        try:
            # Python imports
            if file_path.endswith('.py'):
                # import statements: import foo, from foo import bar
                for match in re.finditer(r'^\s*(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*)', file_content, re.MULTILINE):
                    lib_name = match.group(1)
                    # Skip standard library and local imports
                    if lib_name not in {'os', 'sys', 're', 'json', 'time', 'datetime', 'pathlib', 'typing', 'logging'}:
                        libraries.add(lib_name)

            # JavaScript/TypeScript imports
            elif file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                # import statements: import foo from 'bar'
                for match in re.finditer(r'import\s+.*?\s+from\s+[\'"]([^\'\"]+)[\'"]', file_content):
                    lib_name = match.group(1)
                    # Skip relative imports
                    if not lib_name.startswith('.'):
                        # Extract package name (before /)
                        package = lib_name.split('/')[0]
                        if package.startswith('@'):
                            # Scoped package like @react/foo
                            package = '/'.join(lib_name.split('/')[:2])
                        libraries.add(package)

                # require statements: const foo = require('bar')
                for match in re.finditer(r'require\s*\(\s*[\'"]([^\'\"]+)[\'"]\s*\)', file_content):
                    lib_name = match.group(1)
                    if not lib_name.startswith('.'):
                        package = lib_name.split('/')[0]
                        if package.startswith('@'):
                            package = '/'.join(lib_name.split('/')[:2])
                        libraries.add(package)

        except Exception as e:
            logger.debug(f"Failed to extract libraries from {file_path}: {e}")

        return libraries

    def _extract_code_patterns(self, file_content: str, file_path: str, domain: str) -> List[Dict[str, Any]]:
        """
        Extract code patterns and conventions from file content.

        Args:
            file_content: Content of the file
            file_path: Path to the file
            domain: Domain being scanned

        Returns:
            List of pattern dictionaries
        """
        import re

        patterns = []

        try:
            # Python patterns
            if file_path.endswith('.py'):
                # Async function pattern
                if 'async def' in file_content:
                    async_funcs = re.findall(r'async def (\w+)\(', file_content)
                    if async_funcs:
                        patterns.append({
                            'name': 'Async functions pattern',
                            'language': 'python',
                            'description': f'Uses async/await pattern for {", ".join(async_funcs[:3])}',
                            'when_to_use': 'For I/O-bound operations like database queries, API calls'
                        })

                # Class-based pattern
                class_match = re.search(r'class\s+(\w+)', file_content)
                if class_match:
                    class_name = class_match.group(1)
                    patterns.append({
                        'name': f'{class_name} class pattern',
                        'language': 'python',
                        'description': f'Class-based architecture using {class_name}',
                        'when_to_use': f'For {domain} operations'
                    })

                # Decorator pattern
                if '@' in file_content:
                    decorators = re.findall(r'@(\w+)', file_content)
                    if decorators:
                        patterns.append({
                            'name': 'Decorator pattern',
                            'language': 'python',
                            'description': f'Uses decorators: {", ".join(set(decorators[:5]))}',
                            'when_to_use': 'For cross-cutting concerns like logging, auth, caching'
                        })

            # JavaScript/TypeScript patterns
            elif file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                # React component pattern
                if 'export' in file_content and ('function' in file_content or 'const' in file_content):
                    component_match = re.search(r'export\s+(?:default\s+)?(?:function|const)\s+(\w+)', file_content)
                    if component_match:
                        comp_name = component_match.group(1)
                        patterns.append({
                            'name': f'{comp_name} component pattern',
                            'language': 'typescript' if file_path.endswith(('.ts', '.tsx')) else 'javascript',
                            'description': f'React component: {comp_name}',
                            'when_to_use': 'For UI components in frontend'
                        })

                # Hook usage pattern
                if 'useState' in file_content or 'useEffect' in file_content:
                    hooks = []
                    if 'useState' in file_content:
                        hooks.append('useState')
                    if 'useEffect' in file_content:
                        hooks.append('useEffect')
                    # Look for custom hooks
                    custom_hooks = re.findall(r'use[A-Z]\w+', file_content)
                    hooks.extend(list(set(custom_hooks))[:3])

                    patterns.append({
                        'name': 'React Hooks pattern',
                        'language': 'typescript' if file_path.endswith(('.ts', '.tsx')) else 'javascript',
                        'description': f'Uses React hooks: {", ".join(hooks[:5])}',
                        'when_to_use': 'For state management and side effects in functional components'
                    })

            # SQL patterns
            elif file_path.endswith('.sql'):
                # DDL pattern
                if 'CREATE TABLE' in file_content.upper():
                    patterns.append({
                        'name': 'DDL schema definition',
                        'language': 'sql',
                        'description': 'Database schema definitions with CREATE TABLE',
                        'when_to_use': 'For database migrations and schema setup'
                    })

                # Trigger pattern
                if 'CREATE TRIGGER' in file_content.upper():
                    patterns.append({
                        'name': 'Database triggers',
                        'language': 'sql',
                        'description': 'Uses database triggers for automated operations',
                        'when_to_use': 'For automatic timestamp updates, validation, audit trails'
                    })

        except Exception as e:
            logger.debug(f"Failed to extract patterns from {file_path}: {e}")

        return patterns

    def _enforce_line_limit(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce MAX_EXPERTISE_LINES limit with intelligent pruning.

        Strategy (applied in order until under limit):
        1. Remove failure learnings older than 30 days
        2. Trim oldest patterns (keep newest 20)
        3. Limit core files to most relevant (keep 30)
        4. Trim techniques (keep 15)
        5. Trim remaining learnings (keep newest 20)

        Args:
            content: Expertise content dict

        Returns:
            Pruned content dict that fits within MAX_EXPERTISE_LINES
        """
        from datetime import datetime, timedelta

        def get_line_count(content_dict: Dict[str, Any]) -> int:
            """Calculate line count for content."""
            return len(json.dumps(content_dict, indent=2).split('\n'))

        current_lines = get_line_count(content)

        # If already under limit, return as-is
        if current_lines <= MAX_EXPERTISE_LINES:
            return content

        logger.info(
            f"Expertise exceeds {MAX_EXPERTISE_LINES} lines ({current_lines} lines), "
            f"applying intelligent pruning..."
        )

        # Step 1: Remove failure learnings older than 30 days
        if 'learnings' in content and current_lines > MAX_EXPERTISE_LINES:
            cutoff_date = datetime.now() - timedelta(days=30)
            original_count = len(content['learnings'])
            fresh_learnings = []

            for learning in content['learnings']:
                # Keep successes and recent failures
                if learning.get('type') != 'failure':
                    fresh_learnings.append(learning)
                else:
                    # Check age of failure
                    learning_date_str = learning.get('date')
                    if learning_date_str:
                        try:
                            learning_date = datetime.fromisoformat(
                                learning_date_str.replace('Z', '+00:00')
                            )
                            if learning_date > cutoff_date:
                                fresh_learnings.append(learning)
                        except (ValueError, AttributeError):
                            # Keep if date parsing fails (safer)
                            fresh_learnings.append(learning)
                    else:
                        # Keep if no date
                        fresh_learnings.append(learning)

            if len(fresh_learnings) < original_count:
                content['learnings'] = fresh_learnings
                current_lines = get_line_count(content)
                logger.debug(
                    f"Removed {original_count - len(fresh_learnings)} old failures, "
                    f"now {current_lines} lines"
                )

        # Step 2: Trim oldest patterns (keep newest 20)
        if 'patterns' in content and current_lines > MAX_EXPERTISE_LINES:
            if len(content['patterns']) > 20:
                content['patterns'] = content['patterns'][:20]
                current_lines = get_line_count(content)
                logger.debug(f"Trimmed patterns to 20, now {current_lines} lines")

        # Step 3: Limit core files to 30 most relevant
        if 'core_files' in content and current_lines > MAX_EXPERTISE_LINES:
            if len(content['core_files']) > 30:
                content['core_files'] = content['core_files'][:30]
                current_lines = get_line_count(content)
                logger.debug(f"Trimmed core files to 30, now {current_lines} lines")

        # Step 4: Trim techniques (keep 15)
        if 'techniques' in content and current_lines > MAX_EXPERTISE_LINES:
            if len(content['techniques']) > 15:
                content['techniques'] = content['techniques'][:15]
                current_lines = get_line_count(content)
                logger.debug(f"Trimmed techniques to 15, now {current_lines} lines")

        # Step 5: Trim remaining learnings (keep newest 20)
        if 'learnings' in content and current_lines > MAX_EXPERTISE_LINES:
            if len(content['learnings']) > 20:
                # Sort by date (newest first)
                learnings_sorted = sorted(
                    content['learnings'],
                    key=lambda x: x.get('date', ''),
                    reverse=True
                )
                content['learnings'] = learnings_sorted[:20]
                current_lines = get_line_count(content)
                logger.debug(f"Trimmed learnings to 20, now {current_lines} lines")

        # Step 6: If still over limit, aggressively trim all sections
        if current_lines > MAX_EXPERTISE_LINES:
            logger.warning(
                f"Still over limit after standard pruning ({current_lines} lines), "
                f"applying aggressive pruning..."
            )

            # Aggressively trim each section
            if 'core_files' in content:
                content['core_files'] = content['core_files'][:15]
            if 'patterns' in content:
                content['patterns'] = content['patterns'][:10]
            if 'techniques' in content:
                content['techniques'] = content['techniques'][:8]
            if 'learnings' in content:
                content['learnings'] = sorted(
                    content['learnings'],
                    key=lambda x: x.get('date', ''),
                    reverse=True
                )[:10]

            current_lines = get_line_count(content)
            logger.info(f"After aggressive pruning: {current_lines} lines")

        logger.info(
            f"Line limit enforcement complete: {current_lines} lines "
            f"({MAX_EXPERTISE_LINES - current_lines} under limit)"
        )

        return content

    def _prune_expertise_to_limit(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy pruning method - delegates to _enforce_line_limit.

        Args:
            content: Expertise content dict

        Returns:
            Pruned content dict
        """
        return self._enforce_line_limit(content)

    async def format_for_prompt(self, domain: str) -> str:
        """
        Format expertise as markdown for prompt injection.

        Produces readable markdown with sections for:
        - Core Files (relevant files to reference)
        - Patterns (code patterns and conventions)
        - Techniques (successful workflows)
        - Recent Learnings (failures and successes)

        Args:
            domain: Domain name

        Returns:
            Formatted markdown string (limited to MAX_EXPERTISE_LINES)
        """
        try:
            # Get expertise for domain
            expertise = await self.get_expertise(domain)
            if not expertise:
                logger.debug(f"No expertise found for domain '{domain}', returning empty string")
                return ""

            content = expertise.content
            lines = []

            # Header
            lines.append(f"# Expertise: {domain.title()} Domain")
            lines.append("")
            lines.append(f"*Version {expertise.version} - Accumulated knowledge from past sessions*")
            lines.append("")

            # Section 1: Core Files
            if content.get('core_files'):
                lines.append("## Core Files")
                lines.append("")
                lines.append("Key files to reference for this domain:")
                lines.append("")

                # Limit to top 15 most relevant files
                for file_path in content['core_files'][:15]:
                    lines.append(f"- `{file_path}`")

                if len(content['core_files']) > 15:
                    lines.append(f"- ... and {len(content['core_files']) - 15} more files")

                lines.append("")

            # Section 2: Code Patterns
            if content.get('patterns'):
                lines.append("## Code Patterns & Conventions")
                lines.append("")

                # Limit to top 10 patterns
                for i, pattern in enumerate(content['patterns'][:10], 1):
                    pattern_name = pattern.get('name', 'Unnamed pattern')
                    pattern_desc = pattern.get('description', '')
                    pattern_when = pattern.get('when_to_use', '')
                    pattern_lang = pattern.get('language', '')

                    lines.append(f"### {i}. {pattern_name}")
                    if pattern_lang:
                        lines.append(f"*Language: {pattern_lang}*")
                    if pattern_desc:
                        lines.append(f"- **Description:** {pattern_desc}")
                    if pattern_when:
                        lines.append(f"- **When to use:** {pattern_when}")
                    lines.append("")

                if len(content['patterns']) > 10:
                    lines.append(f"*... and {len(content['patterns']) - 10} more patterns*")
                    lines.append("")

            # Section 3: Techniques & Workflows
            if content.get('techniques'):
                lines.append("## Successful Techniques")
                lines.append("")

                # Limit to top 8 techniques
                for i, technique in enumerate(content['techniques'][:8], 1):
                    tech_name = technique.get('name', 'Unnamed technique')
                    tech_steps = technique.get('steps', [])

                    lines.append(f"### {i}. {tech_name}")
                    if tech_steps:
                        lines.append("")
                        for step in tech_steps:
                            lines.append(f"- {step}")
                    lines.append("")

                if len(content['techniques']) > 8:
                    lines.append(f"*... and {len(content['techniques']) - 8} more techniques*")
                    lines.append("")

            # Section 4: Recent Learnings (successes and failures)
            if content.get('learnings'):
                # Separate by type
                failures = [l for l in content['learnings'] if l.get('type') == 'failure']
                successes = [l for l in content['learnings'] if l.get('type') == 'success']

                if failures:
                    lines.append("## Known Issues & Failures")
                    lines.append("")
                    lines.append("*Learn from past mistakes:*")
                    lines.append("")

                    # Show most recent 5 failures
                    for failure in failures[:5]:
                        lesson = failure.get('lesson', 'No details')
                        lines.append(f"- {lesson}")

                    if len(failures) > 5:
                        lines.append(f"- ... and {len(failures) - 5} more known issues")

                    lines.append("")

                if successes:
                    lines.append("## Success Insights")
                    lines.append("")

                    # Show most recent 5 successes
                    for success in successes[:5]:
                        lesson = success.get('lesson', 'No details')
                        lines.append(f"- {lesson}")

                    if len(successes) > 5:
                        lines.append(f"- ... and {len(successes) - 5} more insights")

                    lines.append("")

            # Join all lines
            formatted = '\n'.join(lines)

            # Enforce line limit
            formatted_lines = formatted.split('\n')
            if len(formatted_lines) > MAX_EXPERTISE_LINES:
                logger.warning(
                    f"Formatted expertise for '{domain}' exceeds {MAX_EXPERTISE_LINES} lines "
                    f"({len(formatted_lines)} lines), truncating..."
                )
                # Truncate and add notice
                formatted_lines = formatted_lines[:MAX_EXPERTISE_LINES - 2]
                formatted_lines.append("")
                formatted_lines.append(f"*[Truncated at {MAX_EXPERTISE_LINES} line limit]*")
                formatted = '\n'.join(formatted_lines)

            logger.debug(
                f"Formatted expertise for '{domain}': {len(formatted_lines)} lines, "
                f"{len(formatted)} characters"
            )

            return formatted

        except Exception as e:
            logger.error(f"Failed to format expertise for domain '{domain}': {e}")
            return ""

    # =========================================================================
    # File-Based Expertise Routing (ADWS Pattern)
    # =========================================================================

    async def route_to_expert(
        self,
        query: str,
        context: Dict[str, Any],
        project_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Route a query to the appropriate domain expert.

        Priority:
        1. Check .claude/skills/ for native skills
        2. Check .claude/commands/experts/ for file expertise
        3. Fall back to DB-stored expertise

        Args:
            query: The query or task description
            context: Context dict with file paths, task info, etc.
            project_path: Path to project root (for file-based lookup)

        Returns:
            Formatted expertise string or None if no match
        """
        # Classify the domain from query
        domain = self.classify_domain_from_task(query, context.get('files', []))

        if not domain or domain == 'general':
            return None

        # Priority 1: Check for native skill
        if project_path:
            skill_content = self._find_native_skill(domain, project_path)
            if skill_content:
                logger.info(f"Routed to native skill for domain '{domain}'")
                return skill_content

        # Priority 2: Check file-based expertise
        if project_path:
            file_expertise = await self.get_expertise_from_files(domain, project_path)
            if file_expertise:
                logger.info(f"Routed to file expertise for domain '{domain}'")
                return file_expertise

        # Priority 3: Fall back to DB expertise
        formatted = await self.format_for_prompt(domain)
        if formatted:
            logger.info(f"Routed to DB expertise for domain '{domain}'")
            return formatted

        return None

    async def get_expertise_from_files(
        self,
        domain: str,
        project_path: str
    ) -> Optional[str]:
        """
        Load expertise from file system.

        Args:
            domain: Domain name
            project_path: Path to project root

        Returns:
            Formatted expertise string or None
        """
        from pathlib import Path

        try:
            experts_dir = Path(project_path) / ".claude" / "commands" / "experts" / domain
            yaml_path = experts_dir / "expertise.yaml"

            if not yaml_path.exists():
                return None

            content = yaml_path.read_text(encoding='utf-8')

            # Format the file content as expertise
            lines = [
                f"# {domain.title()} Domain Expertise",
                "",
                f"*Loaded from project expertise files*",
                "",
                "---",
                "",
                content
            ]

            return '\n'.join(lines)

        except Exception as e:
            logger.error(f"Failed to load file expertise for '{domain}': {e}")
            return None

    def _find_native_skill(
        self,
        domain: str,
        project_path: str
    ) -> Optional[str]:
        """
        Check if a native skill exists for this domain.

        Args:
            domain: Domain name
            project_path: Path to project root

        Returns:
            Skill content or None
        """
        from pathlib import Path

        try:
            skill_path = Path(project_path) / ".claude" / "skills" / f"{domain}-expert" / "SKILL.md"

            if skill_path.exists():
                return skill_path.read_text(encoding='utf-8')

            return None

        except Exception as e:
            logger.debug(f"No native skill found for '{domain}': {e}")
            return None

    def classify_domain_from_task(
        self,
        task_description: str,
        file_paths: List[str] = None
    ) -> str:
        """
        Classify which domain a task belongs to.

        Uses keyword matching and file patterns to determine
        the most appropriate domain.

        Args:
            task_description: Description of the task
            file_paths: List of file paths involved

        Returns:
            Domain name (or 'general' if no match)
        """
        task_lower = task_description.lower()
        file_paths = file_paths or []

        domain_scores = {domain: 0 for domain in DOMAINS}

        # Score based on keywords in task description
        for domain, keywords in DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in task_lower:
                    domain_scores[domain] += 1

        # Score based on file patterns
        for file_path in file_paths:
            file_lower = file_path.lower()
            for domain, patterns in DOMAIN_FILE_PATTERNS.items():
                for pattern in patterns:
                    if pattern in file_lower:
                        domain_scores[domain] += 2  # File patterns are stronger signals

        # Find highest scoring domain
        best_domain = max(domain_scores, key=domain_scores.get)
        best_score = domain_scores[best_domain]

        if best_score > 0:
            logger.debug(f"Classified task as '{best_domain}' (score: {best_score})")
            return best_domain

        return 'general'

    async def save_expertise(
        self,
        domain: str,
        content: Dict[str, Any]
    ) -> bool:
        """
        Save expertise to database.

        Args:
            domain: Domain name
            content: Expertise content dict

        Returns:
            True if saved successfully
        """
        try:
            # Check if expertise exists
            existing = await self.get_expertise(domain)

            if existing:
                # Update existing
                version = existing.version + 1
                await self.db.update_expertise(
                    self.project_id,
                    domain,
                    content,
                    version
                )
            else:
                # Create new
                await self.db.create_expertise(
                    self.project_id,
                    domain,
                    content
                )

            logger.info(f"Saved expertise for domain '{domain}'")
            return True

        except Exception as e:
            logger.error(f"Failed to save expertise for '{domain}': {e}")
            return False
