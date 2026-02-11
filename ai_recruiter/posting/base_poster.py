from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class JobPosting:
    """
    Simple, framework-agnostic representation of a vacancy that we want to post.

    Later you can add a helper that converts from your Django Vacancies model
    into this dataclass.
    """

    title: str
    description: str
    location: str

    employment_type: Optional[str] = None  # e.g. "Full-time"
    salary: Optional[str] = None
    company_name: Optional[str] = None

    # Free-form payload for platform-specific extras
    extra: Dict[str, Any] = field(default_factory=dict)


class BasePoster(ABC):
    """
    Base class for all platform-specific posters.

    Each concrete implementation should:
    - encapsulate its own Playwright logic
    - read selectors/URLs from a JSON config file
    - implement `post_job` as the main entrypoint
    """

    platform: str = "base"

    def __init__(self, email: str, password: str, headless: bool = True) -> None:
        self.email = email
        self.password = password
        self.headless = headless

    @abstractmethod
    def post_job(self, job: JobPosting) -> None:
        """
        High-level operation: log in (if needed), navigate to the job posting
        flow, fill in the form from `job`, and publish.

        Implementations should raise an exception on failure so callers
        (e.g. Celery tasks) can record the error.
        """

