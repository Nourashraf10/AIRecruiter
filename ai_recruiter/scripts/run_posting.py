"""
Small CLI helper to manually trigger job posting for development.

Example usage (after setting the appropriate environment variables):

    POSTING_PLATFORM=facebook \\
    FACEBOOK_EMAIL='you@example.com' \\
    FACEBOOK_PASSWORD='...' \\
    python -m ai_recruiter.scripts.run_posting \\
        --title "Senior Python Engineer" \\
        --description "We build cool stuff." \\
        --location "Cairo, Egypt"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Type

from decouple import AutoConfig

from ai_recruiter.posting.base_poster import JobPosting, BasePoster
from ai_recruiter.posting.facebook_poster import FacebookPoster
from ai_recruiter.posting.linkedin_poster import LinkedInPoster


PLATFORM_POSTERS = {
    "facebook": FacebookPoster,
    "linkedin": LinkedInPoster,
}


# Configure python-decouple to read from the main project `.env` file so you
# can keep all secrets in one place instead of exporting them in the shell.
BASE_DIR = Path(__file__).resolve().parents[2]
config = AutoConfig(search_path=str(BASE_DIR))


def _get_poster_class(platform: str) -> Type[BasePoster]:
    try:
        return PLATFORM_POSTERS[platform]
    except KeyError as exc:
        raise SystemExit(f"Unsupported platform: {platform!r}. Supported: {', '.join(PLATFORM_POSTERS)}") from exc


def _resolve_credentials(platform: str) -> tuple[str, str]:
    # Prefer .env file over shell env so the project .env always wins (avoids old placeholders in shell).
    if platform == "facebook":
        email = config("FACEBOOK_EMAIL", default=None) or os.getenv("FACEBOOK_EMAIL")
        password = config("FACEBOOK_PASSWORD", default=None) or os.getenv("FACEBOOK_PASSWORD")
    elif platform == "linkedin":
        email = config("LINKEDIN_EMAIL", default=None) or os.getenv("LINKEDIN_EMAIL")
        password = config("LINKEDIN_PASSWORD", default=None) or os.getenv("LINKEDIN_PASSWORD")
    else:
        raise SystemExit(f"Unsupported platform: {platform}")

    if not email or not password:
        raise SystemExit(
            f"Missing credentials for {platform}. Please set "
            f"{platform.upper()}_EMAIL and {platform.upper()}_PASSWORD in your environment "
            f"(either in the shell or in {BASE_DIR / '.env'})."
        )

    return email, password


def main() -> None:
    parser = argparse.ArgumentParser(description="Post a job to a social platform using Playwright.")
    parser.add_argument("--platform", choices=list(PLATFORM_POSTERS.keys()), required=False,
                        help="Target platform (default: from POSTING_PLATFORM env).")
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--employment-type", dest="employment_type", required=False)
    parser.add_argument("--salary", required=False)

    args = parser.parse_args()

    # Prefer .env then shell env so project .env wins
    platform = args.platform or config("POSTING_PLATFORM", default=None) or os.getenv("POSTING_PLATFORM")
    if not platform:
        raise SystemExit("Please specify --platform or set POSTING_PLATFORM in the environment or .env.")

    platform = platform.lower()
    PosterClass = _get_poster_class(platform)
    email, password = _resolve_credentials(platform)

    # Debug: confirm credentials are loaded from .env
    print("USING PLATFORM:", platform)
    print("EMAIL:", email)

    job = JobPosting(
        title=args.title,
        description=args.description,
        location=args.location,
        employment_type=args.employment_type,
        salary=args.salary,
    )

    poster = PosterClass(email=email, password=password)
    poster.post_job(job)


if __name__ == "__main__":
    main()

