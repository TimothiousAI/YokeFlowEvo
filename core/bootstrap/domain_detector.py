"""
Domain Detector
===============

Detects domains from app_spec to pre-create expert stubs.

Key Features:
- Parse app_spec.txt for technology keywords
- Detect domains: frontend, backend, database, api, testing, devops
- Return list of detected domains with confidence scores
- Support common tech stacks (React, FastAPI, PostgreSQL, etc.)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class DetectedDomain:
    """A detected domain from app specification."""
    name: str
    confidence: float
    keywords_found: List[str] = field(default_factory=list)
    suggested_files: List[str] = field(default_factory=list)
    description: str = ""
    stack: Dict[str, str] = field(default_factory=dict)


class DomainDetector:
    """
    Detects domains from app specification text.

    Scans for technology keywords and patterns to identify
    which domains will be relevant for the project.
    """

    # Domain keyword mappings
    DOMAIN_KEYWORDS = {
        'frontend': {
            'keywords': [
                'react', 'vue', 'angular', 'svelte', 'next.js', 'nextjs',
                'nuxt', 'frontend', 'ui', 'user interface', 'css', 'tailwind',
                'styled-components', 'material-ui', 'chakra', 'bootstrap',
                'html', 'jsx', 'tsx', 'component', 'spa', 'single page',
                'web app', 'client-side', 'browser'
            ],
            'file_patterns': ['src/components/', 'src/pages/', 'src/app/', 'public/'],
            'description': 'Frontend UI components and user interface'
        },
        'backend': {
            'keywords': [
                'fastapi', 'django', 'flask', 'express', 'node', 'nestjs',
                'backend', 'server', 'api', 'rest', 'graphql', 'endpoint',
                'route', 'controller', 'service', 'middleware', 'python',
                'node.js', 'nodejs', 'java', 'spring', 'golang', 'go'
            ],
            'file_patterns': ['api/', 'src/api/', 'server/', 'app/', 'core/'],
            'description': 'Backend services and API implementation'
        },
        'database': {
            'keywords': [
                'postgresql', 'postgres', 'mysql', 'mongodb', 'sqlite',
                'database', 'db', 'sql', 'nosql', 'redis', 'elasticsearch',
                'prisma', 'sqlalchemy', 'orm', 'migration', 'schema',
                'table', 'collection', 'query', 'crud', 'data model'
            ],
            'file_patterns': ['db/', 'database/', 'models/', 'schema/', 'migrations/'],
            'description': 'Database schema and data access patterns'
        },
        'api': {
            'keywords': [
                'api', 'rest', 'restful', 'graphql', 'grpc', 'endpoint',
                'webhook', 'oauth', 'jwt', 'authentication', 'authorization',
                'openapi', 'swagger', 'postman', 'http', 'request', 'response'
            ],
            'file_patterns': ['api/', 'routes/', 'endpoints/', 'handlers/'],
            'description': 'API design and endpoint patterns'
        },
        'testing': {
            'keywords': [
                'test', 'testing', 'pytest', 'jest', 'mocha', 'cypress',
                'playwright', 'selenium', 'unit test', 'integration test',
                'e2e', 'end-to-end', 'coverage', 'mock', 'fixture', 'tdd'
            ],
            'file_patterns': ['tests/', 'test/', '__tests__/', 'spec/'],
            'description': 'Testing strategies and test patterns'
        },
        'devops': {
            'keywords': [
                'docker', 'kubernetes', 'k8s', 'ci', 'cd', 'ci/cd',
                'github actions', 'gitlab', 'jenkins', 'deployment',
                'nginx', 'aws', 'azure', 'gcp', 'terraform', 'ansible',
                'container', 'helm', 'prometheus', 'grafana', 'monitoring'
            ],
            'file_patterns': ['docker/', '.github/', 'deploy/', 'infra/', 'k8s/'],
            'description': 'DevOps, deployment, and infrastructure'
        },
        'auth': {
            'keywords': [
                'authentication', 'authorization', 'oauth', 'jwt', 'login',
                'signup', 'register', 'password', 'token', 'session',
                'rbac', 'permission', 'role', 'user management', 'sso'
            ],
            'file_patterns': ['auth/', 'security/', 'middleware/auth/'],
            'description': 'Authentication and authorization patterns'
        },
    }

    # Tech stack detection
    TECH_STACK = {
        'frontend': {
            'react': ['react', 'jsx', 'create-react-app', 'next.js', 'nextjs'],
            'vue': ['vue', 'vuex', 'nuxt', 'vuetify'],
            'angular': ['angular', '@angular', 'ng-'],
            'svelte': ['svelte', 'sveltekit'],
        },
        'backend': {
            'fastapi': ['fastapi', 'uvicorn', 'starlette'],
            'django': ['django', 'django-rest-framework', 'drf'],
            'flask': ['flask', 'flask-restful'],
            'express': ['express', 'express.js'],
            'nestjs': ['nestjs', '@nestjs'],
        },
        'database': {
            'postgresql': ['postgresql', 'postgres', 'pg', 'psycopg'],
            'mysql': ['mysql', 'mariadb'],
            'mongodb': ['mongodb', 'mongoose', 'mongo'],
            'sqlite': ['sqlite', 'sqlite3'],
            'redis': ['redis', 'redis-py'],
        },
    }

    def __init__(self):
        """Initialize domain detector."""
        pass

    def detect_domains(self, app_spec: str) -> List[DetectedDomain]:
        """
        Detect domains from app specification text.

        Args:
            app_spec: The application specification text

        Returns:
            List of detected domains with confidence scores
        """
        if not app_spec:
            return []

        text_lower = app_spec.lower()
        detected = []

        for domain_name, config in self.DOMAIN_KEYWORDS.items():
            result = self._detect_domain(
                domain_name,
                text_lower,
                config['keywords'],
                config['file_patterns'],
                config['description']
            )
            if result:
                # Detect specific tech stack for this domain
                result.stack = self._detect_stack(domain_name, text_lower)
                detected.append(result)

        # Sort by confidence (highest first)
        detected.sort(key=lambda x: x.confidence, reverse=True)

        logger.info(f"Detected {len(detected)} domains from app_spec")
        for d in detected:
            logger.debug(f"  - {d.name}: {d.confidence:.2f} ({', '.join(d.keywords_found[:3])})")

        return detected

    def _detect_domain(
        self,
        domain_name: str,
        text: str,
        keywords: List[str],
        file_patterns: List[str],
        description: str
    ) -> Optional[DetectedDomain]:
        """
        Detect a specific domain from text.

        Args:
            domain_name: Name of the domain
            text: Lowercased app_spec text
            keywords: Keywords to search for
            file_patterns: Suggested file patterns
            description: Domain description

        Returns:
            DetectedDomain if found, None otherwise
        """
        found_keywords = []

        for keyword in keywords:
            # Use word boundary matching for better accuracy
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text):
                found_keywords.append(keyword)

        if not found_keywords:
            return None

        # Calculate confidence based on keyword count
        # More keywords = higher confidence, but cap at 0.9
        confidence = min(0.9, 0.3 + (len(found_keywords) * 0.1))

        return DetectedDomain(
            name=domain_name,
            confidence=confidence,
            keywords_found=found_keywords,
            suggested_files=file_patterns,
            description=description
        )

    def _detect_stack(self, domain: str, text: str) -> Dict[str, str]:
        """
        Detect specific technologies for a domain.

        Args:
            domain: Domain name
            text: Lowercased app_spec text

        Returns:
            Dict mapping category to detected technology
        """
        stack = {}

        if domain not in self.TECH_STACK:
            return stack

        for tech_name, keywords in self.TECH_STACK[domain].items():
            for keyword in keywords:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text):
                    stack[domain] = tech_name
                    break
            if domain in stack:
                break

        return stack

    def get_all_detected_stack(self, app_spec: str) -> Dict[str, str]:
        """
        Get complete detected tech stack.

        Args:
            app_spec: The application specification text

        Returns:
            Dict mapping layer to technology
        """
        text_lower = app_spec.lower()
        stack = {}

        for layer, techs in self.TECH_STACK.items():
            for tech_name, keywords in techs.items():
                for keyword in keywords:
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, text_lower):
                        stack[layer] = tech_name
                        break
                if layer in stack:
                    break

        return stack

    def classify_project_type(self, app_spec: str) -> str:
        """
        Classify the overall project type.

        Args:
            app_spec: The application specification text

        Returns:
            Project type string (e.g., "fullstack", "api", "frontend")
        """
        domains = self.detect_domains(app_spec)
        domain_names = {d.name for d in domains if d.confidence >= 0.4}

        if 'frontend' in domain_names and 'backend' in domain_names:
            return 'fullstack'
        elif 'frontend' in domain_names:
            return 'frontend'
        elif 'backend' in domain_names or 'api' in domain_names:
            return 'api'
        elif 'database' in domain_names:
            return 'data'
        else:
            return 'general'
