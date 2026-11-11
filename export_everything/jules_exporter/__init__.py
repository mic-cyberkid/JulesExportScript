"""Google Jules API Exporter Package.

A modular, robust exporter for Jules sessions, activities, plans, code patches,
bash logs, and media artifacts.
"""

from .client import JulesAPIError, JulesClient
from .models import (
    Activity,
    Artifact,
    BashOutput,
    ChangeSet,
    GitPatch,
    Media,
    Plan,
    PlanStep,
    PullRequest,
    Session,
    Source,
)

__all__ = [
    "JulesClient",
    "JulesAPIError",
    "Session",
    "Activity",
    "Artifact",
    "ChangeSet",
    "GitPatch",
    "Media",
    "BashOutput",
    "Plan",
    "PlanStep",
    "PullRequest",
    "Source",
]
