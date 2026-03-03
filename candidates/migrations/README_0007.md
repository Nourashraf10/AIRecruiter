# Migration 0007: questionnaire_email_sent_at

This migration adds `questionnaire_email_sent_at` to `CandidateVacancyProfile`.

**If you see errors on the dashboard or candidate profiles** (e.g. "no such column: candidates_candidatevacancyprofile.questionnaire_email_sent_at"), run:

```bash
python manage.py migrate candidates
```

(or `python3 manage.py migrate candidates`)

Then reload the dashboard and candidate profile pages.
