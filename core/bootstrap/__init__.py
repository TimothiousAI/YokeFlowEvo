"""
Project Bootstrap Module
========================

Bootstraps new projects with Claude SDK structure.

Key Components:
- DomainDetector: Detects domains from app_spec
- CLAUDEMDGenerator: Generates CLAUDE.md from spec
- ProjectBootstrapper: Orchestrates the bootstrap process
"""

from core.bootstrap.domain_detector import DomainDetector, DetectedDomain
from core.bootstrap.claude_md_generator import CLAUDEMDGenerator, GeneratedCLAUDEMD
from core.bootstrap.project_bootstrapper import ProjectBootstrapper, BootstrapResult

__all__ = [
    'DomainDetector',
    'DetectedDomain',
    'CLAUDEMDGenerator',
    'GeneratedCLAUDEMD',
    'ProjectBootstrapper',
    'BootstrapResult',
]
