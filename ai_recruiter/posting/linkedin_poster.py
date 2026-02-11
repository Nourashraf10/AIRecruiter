from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from playwright.sync_api import sync_playwright, Page

from .base_poster import BasePoster, JobPosting


def _load_selectors() -> Dict[str, Any]:
    """Load LinkedIn selectors/URLs from the local JSON file."""
    current_dir = Path(__file__).resolve().parent
    selectors_path = current_dir / "selectors" / "linkedin.json"
    with selectors_path.open("r", encoding="utf-8") as f:
        return json.load(f)


_CONFIG = _load_selectors()


class LinkedInPoster(BasePoster):
    platform = "linkedin"

    def _login(self, page: Page) -> None:
        selectors = _CONFIG["selectors"]

        page.goto(_CONFIG["login_url"], wait_until="networkidle")
        page.fill(selectors["email_input"], self.email)
        page.fill(selectors["password_input"], self.password)
        page.click(selectors["login_button"])
        page.wait_for_load_state("networkidle")

    def _navigate_to_job_posting(self, page: Page) -> None:
        page.goto(_CONFIG["job_post_url"], wait_until="networkidle")

    def _fill_job_form(self, page: Page, job: JobPosting) -> None:
        selectors = _CONFIG["selectors"]

        # These are intentionally simple placeholders. Once you know the
        # exact DOM structure for your account's job-posting flow, update
        # the selectors JSON and this logic if needed.
        page.fill(selectors["job_title_input"], job.title)
        page.fill(selectors["job_location_input"], job.location)
        page.fill(selectors["job_description_textarea"], job.description)

        # TODO: Map employment_type, salary, and any other fields to the
        # corresponding LinkedIn inputs, using additional selectors.

    def _submit_job_form(self, page: Page) -> None:
        selectors = _CONFIG["selectors"]
        page.click(selectors["submit_button"])
        page.wait_for_load_state("networkidle")

    def post_job(self, job: JobPosting) -> None:
        """
        High-level flow for LinkedIn:
        - Start a browser
        - Log in
        - Navigate to job posting page
        - Fill the job form
        - Submit
        """
        headless_env = os.getenv("POSTING_HEADLESS")
        headless = self.headless if headless_env is None else headless_env.lower() != "false"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                context = browser.new_context()
                page = context.new_page()

                self._login(page)
                self._navigate_to_job_posting(page)
                self._fill_job_form(page, job)
                self._submit_job_form(page)
            finally:
                browser.close()

