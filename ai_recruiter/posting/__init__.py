"""
Browser-based job posting automation.

This package provides a small abstraction over Playwright so that
different platforms (Facebook, LinkedIn, etc.) can share a common
interface while keeping selectors and flows isolated per platform.
"""

from .base_poster import JobPosting, BasePoster  # noqa: F401

