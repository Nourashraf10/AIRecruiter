"""
One-time helper to create a persistent Facebook session for Playwright.

Usage:

    source venv/bin/activate
    python -m ai_recruiter.scripts.facebook_login_once

This will:
  - open a visible browser
  - navigate to the Facebook login page
  - let you log in manually (including 2FA / checkpoints)
  - when you're fully logged in and see your feed/Page, press ENTER in the terminal
  - the session cookies are saved to facebook_storage_state.json

After that, the FacebookPoster will reuse this session instead of re-logging in
each time, which avoids repeated login redirects / checkpoints.
"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    selectors_path = base_dir / "ai_recruiter" / "posting" / "selectors" / "facebook.json"
    storage_path = base_dir / "ai_recruiter" / "posting" / "facebook_storage_state.json"

    with selectors_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    login_url = cfg.get("login_url", "https://www.facebook.com/login")

    print(f"[facebook_login_once] Using login URL: {login_url}")
    print(f"[facebook_login_once] Storage state will be saved to: {storage_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(login_url)

            print(
                "\nPlease log into Facebook in the opened browser window.\n"
                "- Complete email/password\n"
                "- Complete any 2FA / checkpoints / 'Was this you?' prompts\n"
                "When you are fully logged in and see your feed/Page, "
                "return here and press ENTER.\n"
            )
            input("Press ENTER to save the current session... ")

            storage_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=storage_path)
            print(f"[facebook_login_once] Session saved to {storage_path}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()

