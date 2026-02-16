# LinkedIn Automation - Final Setup Checklist

## Current Status

✅ **Code Integration**: LinkedIn automation is properly integrated into Django
✅ **Dependencies**: All packages installed (Playwright, OpenAI, Pillow)
✅ **Settings**: OPENAI_API_KEY added to settings.py
❌ **Configuration**: Environment variables not loaded yet

## What You Need to Do

### Step 1: Update Your `.env` File

Make sure your `.env` file (NOT `.env.example`) contains:

```bash
# OpenAI API Key (required for job post generation)
OPENAI_API_KEY=sk-your-actual-key-here

# LinkedIn Credentials
LINKEDIN_EMAIL=your-linkedin-email@company.com
LINKEDIN_PASSWORD="your-password-with-special-chars"
LINKEDIN_COMPANY_PAGE=https://www.linkedin.com/company/your-company

# Enable LinkedIn Automation
LINKEDIN_POSTING_ENABLED=True

# Browser Mode (False = visible browser for debugging)
LINKEDIN_HEADLESS=False
```

**Important Notes:**
- Use quotes around password if it contains special characters (#, $, !, etc.)
- Set `LINKEDIN_HEADLESS=False` for first test (to see what's happening)
- Set `LINKEDIN_POSTING_ENABLED=True` to enable automation

### Step 2: Restart Django Server

After updating `.env`, you MUST restart Django:

```bash
# Stop Django (Ctrl+C in the terminal where it's running)

# Then restart
python manage.py runserver
```

### Step 3: Verify Configuration

Run the verification script to confirm everything is loaded:

```bash
python verify_linkedin_integration.py
```

You should see:
```
[OK] OPENAI_API_KEY is set
[OK] LINKEDIN_EMAIL is set
[OK] LINKEDIN_PASSWORD is set
[OK] LINKEDIN_POSTING_ENABLED = True
```

### Step 4: Test with Real Vacancy

1. **Create a test vacancy** (via email or admin)
2. **Approve the vacancy** (click approval link in email)
3. **Watch Django terminal** for automation messages:
   ```
   🤖 Starting automated LinkedIn posting for: [Job Title]
   📝 Generating LinkedIn job post content...
   ✅ Generated job post (XXX characters)
   🔐 Logging into LinkedIn...
   ✅ Login successful
   📤 Posting job to LinkedIn...
   ✅ Job posted successfully: [LinkedIn URL]
   ```

4. **Check screenshots** in `screenshots/vacancy_[id]/`
5. **Check email** - HR will receive LinkedIn URL

## How the Automation Works

When a manager approves a vacancy:

1. **Check**: Is `LINKEDIN_POSTING_ENABLED=True`?
   - If No → Send email to HR asking them to post manually
   - If Yes → Continue to step 2

2. **Generate**: Create job post content with GPT-4

3. **Login**: Open browser and login to LinkedIn

4. **Post**: Fill job posting form and submit

5. **Save**: Extract LinkedIn URL and save to database

6. **Update**: Change vacancy status to `collecting_applications`

7. **Notify**: Email HR with LinkedIn URL

## Debugging

### If Automation Fails

Check Django terminal output for error messages:

- **"LinkedIn credentials not configured"** → Add credentials to `.env`
- **"OPENAI_API_KEY not configured"** → Add API key to `.env`
- **"LinkedIn login failed"** → Check credentials, may need 2FA
- **"Job posting error"** → Check screenshots to see what went wrong

### View Screenshots

All automation steps are captured:
```
screenshots/vacancy_[id]/
  - login_page.png
  - login_successful.png
  - job_posting_page.png
  - job_form_filled.png
  - job_posted.png
```

### Test Without Django

Use the standalone test to verify credentials work:
```bash
python test_linkedin_standalone.py
```

This tests:
- OpenAI API connection
- LinkedIn login
- Browser automation
- Form filling

## Production Checklist

Before enabling in production:

- [ ] Test with dummy vacancy first
- [ ] Verify LinkedIn URL is saved correctly
- [ ] Check email notifications work
- [ ] Test with 2FA enabled (if applicable)
- [ ] Set `LINKEDIN_HEADLESS=True` for production
- [ ] Monitor first few automated posts
- [ ] Have fallback plan (manual posting) ready

## Troubleshooting

### Environment Variables Not Loading

**Problem**: Verification shows variables not set
**Solution**: 
1. Check `.env` file exists in project root
2. Restart Django server
3. Run verification again

### Password with Special Characters

**Problem**: Password contains #, $, !, etc.
**Solution**: Wrap in quotes
```bash
LINKEDIN_PASSWORD="MyPass#2024!"
```

### 2FA Challenge

**Problem**: LinkedIn asks for 2FA code
**Solution**: 
- Automation will pause for 30 seconds
- Complete 2FA manually in browser
- Automation continues automatically

### Browser Not Visible

**Problem**: Can't see what's happening
**Solution**: Set `LINKEDIN_HEADLESS=False` in `.env`

## Next Steps

1. ✅ Update `.env` file with all credentials
2. ✅ Restart Django server
3. ✅ Run `python verify_linkedin_integration.py`
4. ✅ Create and approve test vacancy
5. ✅ Monitor Django logs
6. ✅ Check screenshots
7. ✅ Verify LinkedIn URL saved
8. ✅ Enable headless mode for production

## Support Files Created

- `test_linkedin_standalone.py` - Test automation without Django
- `verify_linkedin_integration.py` - Check Django integration
- `LINKEDIN_DIAGNOSIS.md` - Troubleshooting guide
- `TEST_LINKEDIN.md` - Standalone test instructions
- `LINKEDIN_SETUP_GUIDE.md` - Complete setup guide

All automation code is in:
- `ai/linkedin_poster.py` - Main automation service
- `ai/browser_agent.py` - Browser automation
- `ai/vision_helper.py` - GPT-4 Vision for UI detection
- `ai/linkedin_job_post_prompt.py` - Job post generation
- `comms/views.py` - Django integration (lines 680-760)
