from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from playwright.sync_api import (
    sync_playwright,
    Page,
    TimeoutError as PlaywrightTimeout,
    Error as PlaywrightError,
)

from .base_poster import BasePoster, JobPosting


def _load_selectors() -> Dict[str, Any]:
    """Load Facebook selectors/URLs from the local JSON file."""
    current_dir = Path(__file__).resolve().parent
    selectors_path = current_dir / "selectors" / "facebook.json"
    with selectors_path.open("r", encoding="utf-8") as f:
        return json.load(f)


_CONFIG = _load_selectors()
_STORAGE_STATE_PATH = Path(__file__).resolve().parent / "facebook_storage_state.json"


class FacebookPoster(BasePoster):
    platform = "facebook"

    def _login(self, page: Page) -> None:
        selectors = _CONFIG["selectors"]

        # Use domcontentloaded so Facebook's endless background requests don't abort navigation.
        page.goto(_CONFIG["login_url"], wait_until="domcontentloaded", timeout=30_000)
        page.fill(selectors["email_input"], self.email)
        page.fill(selectors["password_input"], self.password)
        page.click(selectors["login_button"])

        # Wait for navigation after login (looser than networkidle for SPAs).
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_load_state("load", timeout=15_000)

    def _navigate_to_job_posting(self, page: Page) -> None:
        """
        Navigate to the Facebook Page and open the regular post composer.
        """
        selectors = _CONFIG["selectors"]
        page_url = _CONFIG.get("page_url")
        if not page_url or "your-page-slug-here" in page_url:
            raise RuntimeError(
                "Facebook Page URL is not configured. Set 'page_url' in "
                "ai_recruiter/posting/selectors/facebook.json to your Page URL "
                "(e.g. https://www.facebook.com/your-page-slug)."
            )

        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightError as exc:
            print(
                f"[FacebookPoster] Navigation to {page_url!r} aborted: {exc}. "
                f"Continuing with current URL: {page.url!r}"
            )
        # Let the feed/Page finish rendering.
        page.wait_for_timeout(3000)

        # Click the "Create post" / composer button if present.
        create_sel = selectors.get("create_post_button")
        if create_sel:
            try:
                page.locator(create_sel).first.wait_for(state="visible", timeout=10_000)
                page.click(create_sel)
            except PlaywrightTimeout:
                print("[FacebookPoster] 'Create post' button not found, will try clicking placeholder text.")

        # Fallback: many UIs use a "What's on your mind, {name}?" area to open the composer.
        clicked_placeholder = False
        for text in ["What's on your mind, Nour?", "What's on your mind?"]:
            try:
                page.get_by_text(text, exact=False).first.click()
                clicked_placeholder = True
                break
            except PlaywrightTimeout:
                continue
        if not clicked_placeholder:
            # If that also fails, _fill_job_form will surface a clearer error.
            print("[FacebookPoster] 'What's on your mind' area not found by text.")

        # Give the composer time to open.
        page.wait_for_timeout(2000)

    def _fill_job_form(self, page: Page, job: JobPosting) -> None:
        """
        For a regular Page post, we just compose a text block that includes
        title, location and description, then paste it into the composer.
        """
        selectors = _CONFIG["selectors"]
        json_path = Path(__file__).resolve().parent / "selectors" / "facebook.json"

        content_lines = [
            job.title,
            "",
            f"Location: {job.location}",
            "",
            job.description,
        ]
        content = "\n".join(line for line in content_lines if line is not None)

        try:
            # Prefer the main composer textbox with an aria-label containing
            # "Write something" (typical for group posts). This avoids picking
            # up the comment box (aria-label "Write a public comment…").
            try:
                locator = page.locator("div[role='textbox'][aria-label*='Write something']").first
                locator.wait_for(state="visible", timeout=5_000)
            except PlaywrightTimeout:
                # Exclude comment box: use textbox that does NOT have aria-label containing "comment".
                try:
                    locator = page.locator(
                        "div[role='textbox']:not([aria-label*='comment'])"
                    ).first
                    locator.wait_for(state="visible", timeout=5_000)
                except PlaywrightTimeout:
                    textbox_sel = selectors.get("composer_textbox")
                    if textbox_sel:
                        locator = page.locator(textbox_sel).first
                    else:
                        locator = page.get_by_role("textbox").first
                    try:
                        locator.wait_for(state="visible", timeout=10_000)
                    except PlaywrightTimeout:
                        # Last resort: contenteditable but exclude comment box.
                        locator = page.locator(
                            "div[contenteditable='true']:not([aria-label*='comment'])"
                        ).first
                        locator.wait_for(state="visible", timeout=10_000)

            locator.fill("")  # clear if any default
            locator.type(content, delay=10)
        except PlaywrightTimeout:
            raise RuntimeError(
                "Could not find the Facebook post composer textbox. "
                f"Update 'composer_textbox' in {json_path} after inspecting the page "
                "(run with POSTING_HEADLESS=false)."
            )

    def _submit_job_form(self, page: Page) -> None:
        selectors = _CONFIG["selectors"]
        json_path = Path(__file__).resolve().parent / "selectors" / "facebook.json"
        publish_sel = selectors.get("publish_button")
        try:
            if publish_sel:
                page.locator(publish_sel).first.wait_for(state="visible", timeout=10_000)
                page.click(publish_sel)
            else:
                page.get_by_role("button", name="Post").first.click()
        except PlaywrightTimeout:
            raise RuntimeError(
                "Could not find the publish/post button. Update 'publish_button' in "
                f"{json_path} after inspecting the composer (run with POSTING_HEADLESS=false)."
            )
        page.wait_for_load_state("load", timeout=15_000)

    def _navigate_to_group_post_composer(self, page: Page, group_name: str) -> None:
        """
        Navigate: Home → Groups → Your groups → [group by name] → Write something
        → Create public post, so the group composer is open.
        """
        json_path = Path(__file__).resolve().parent / "selectors" / "facebook.json"
        gsel = _CONFIG.get("group_selectors") or {}
        page_url = _CONFIG.get("page_url", "https://www.facebook.com/")

        page.goto(page_url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(2000)

        # Click "Groups" in the left sidebar
        groups_sel = gsel.get("groups_link")
        if groups_sel:
            try:
                page.locator(groups_sel).first.wait_for(state="visible", timeout=10_000)
                page.locator(groups_sel).first.click()
            except PlaywrightTimeout:
                page.get_by_role("link", name="Groups").first.click()
        else:
            page.get_by_role("link", name="Groups").first.click()
        page.wait_for_timeout(2000)

        # Click "Your groups"
        your_groups_sel = gsel.get("your_groups_link")
        if your_groups_sel:
            try:
                page.locator(your_groups_sel).first.wait_for(state="visible", timeout=10_000)
                page.locator(your_groups_sel).first.click()
            except PlaywrightTimeout:
                page.get_by_text("Your groups", exact=True).first.click()
        else:
            page.get_by_text("Your groups", exact=True).first.click()
        page.wait_for_timeout(3000)

        # Open the group by name (e.g. "Test Posting")
        try:
            page.get_by_role("link", name=group_name).first.click()
        except PlaywrightTimeout:
            page.get_by_text(group_name, exact=True).first.click()
        page.wait_for_timeout(3000)

        # Focus the main group composer textbox (not the comment box).
        # Prefer a contenteditable div with an aria-label containing "Write something".
        try:
            composer = page.locator("div[role='textbox'][aria-label*='Write something']").first
            composer.wait_for(state="visible", timeout=10_000)
            composer.click()
        except PlaywrightTimeout:
            # Fallback: click by visible text, may still work if DOM differs.
            page.get_by_text("Write something...", exact=False).first.click()
        page.wait_for_timeout(2000)

    def post_job_to_groups(self, job: JobPosting, group_names: Optional[List[str]] = None) -> None:
        """
        Post the job to each of the given groups (or to groups from config if
        group_names is None). Uses the same login/session as post_job.
        Flow: Groups → Your groups → [group] → Write something → Create public post
        → fill text → Post.
        """
        names = group_names if group_names is not None else _CONFIG.get("groups") or []
        if not names:
            return

        headless_env = os.getenv("POSTING_HEADLESS")
        headless = self.headless if headless_env is None else headless_env.lower() != "false"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                context_kwargs: Dict[str, Any] = {}
                use_storage = _STORAGE_STATE_PATH.exists()
                if use_storage:
                    context_kwargs["storage_state"] = str(_STORAGE_STATE_PATH)

                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                page.set_default_navigation_timeout(30_000)

                if not use_storage:
                    self._login(page)

                for group_name in names:
                    self._navigate_to_group_post_composer(page, group_name)
                    self._fill_job_form(page, job)
                    self._submit_job_form(page)
                    page.wait_for_timeout(2000)
            finally:
                browser.close()

    def post_job(self, job: JobPosting) -> None:
        """
        Main high-level flow:
        - Start a browser
        - Log in
        - Navigate to posting flow
        - Fill form
        - Submit
        """
        # Allow overriding headless mode via env for easy debugging.
        headless_env = os.getenv("POSTING_HEADLESS")
        headless = self.headless if headless_env is None else headless_env.lower() != "false"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                context_kwargs: Dict[str, Any] = {}
                use_storage = _STORAGE_STATE_PATH.exists()
                if use_storage:
                    context_kwargs["storage_state"] = str(_STORAGE_STATE_PATH)

                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                page.set_default_navigation_timeout(30_000)

                # If we don't have a saved session yet, fall back to form login once.
                if not use_storage:
                    self._login(page)

                self._navigate_to_job_posting(page)
                self._fill_job_form(page, job)
                self._submit_job_form(page)
            finally:
                browser.close()

