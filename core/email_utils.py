"""
Subject format for all outgoing emails (Fahmy / AI Recruiter).
IT policy: subject must be in the form [bit68 - <subject>] to avoid 554 policy violation.
Subject text must be ASCII-safe (non-ASCII replaced) to prevent policy rejection.
"""


def email_subject(text: str) -> str:
    """Return subject in required form: [bit68 - <text>]. Sanitizes text to ASCII to avoid 554."""
    if not text:
        safe = "Notification"
    else:
        # Keep only ASCII to satisfy strict mail policy; replace other chars with space
        safe = "".join(c if ord(c) < 128 else " " for c in str(text)).strip()
        # Collapse multiple spaces and limit length (some servers limit subject length)
        safe = " ".join(safe.split())[:200] or "Notification"
    return f"[bit68 - {safe}]"
