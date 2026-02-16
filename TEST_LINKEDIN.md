# Quick Test Guide - LinkedIn Automation

## Run the Standalone Test

This test runs the complete LinkedIn automation flow **without Django/database**, with a **visible browser** and **screenshots** for debugging.

### Command

```bash
cd "c:\Users\T.M\Desktop\Bit 68\AI\ai recruiter\AIRecruiter"
venv\Scripts\activate.ps1
python test_linkedin_standalone.py
```

### What It Does

The test will:

1. ✅ **Check environment variables** (LinkedIn credentials, OpenAI API key)
2. ✅ **Generate job post** using GPT-4 (shows preview)
3. ✅ **Open visible browser** (you'll see Chrome/Chromium window)
4. ✅ **Login to LinkedIn** (fills email/password, clicks sign in)
5. ✅ **Navigate to job posting page**
6. ✅ **Test form filling** (fills job title field)
7. 📸 **Take screenshots** at each step
8. 🛑 **Stops before submitting** (won't post test job)

### What You'll See

- **Browser window opens** - you can watch the automation in real-time
- **Pauses for inspection** - you can check the page state
- **Screenshots saved** to `screenshots/linkedin_test/`
- **Step-by-step progress** in terminal

### If 2FA is Enabled

The test will pause and ask you to:
1. Complete 2FA in the browser window
2. Press Enter to continue

### Debugging

If something fails:
1. **Check terminal output** - shows exactly where it failed
2. **Check screenshots** - visual record of each step
3. **Browser stays open** - you can inspect the page manually

### Expected Output

```
================================================================================
LINKEDIN AUTOMATION - STANDALONE TEST
================================================================================

[1/6] Checking environment variables...
   ✅ LINKEDIN_EMAIL: your-email@company...
   ✅ LINKEDIN_PASSWORD: **********
   ✅ OPENAI_API_KEY: sk-proj-...

[2/6] Testing GPT-4 job post generation...
   ✅ Generated job post (450 characters)

[3/6] Initializing browser automation...
   ✅ Browser agent initialized
   📁 Screenshots will be saved to: screenshots/linkedin_test/

[4/6] Starting browser and logging into LinkedIn...
   👀 Browser window will open - watch the automation!
   🔗 Navigating to LinkedIn login page...
   ⌨️  Filling email...
   ⌨️  Filling password...
   🖱️  Clicking sign in button...
   ✅ Login successful!

[5/6] Navigating to job posting page...
   🔗 Going to LinkedIn job posting page...
   ✅ Job posting page loaded
   
   👀 BROWSER PAUSED - Inspect the page
   Press Enter to continue...

[6/6] Testing form filling...
   📝 Attempting to fill job title...
   ✅ Job title filled
   📸 Screenshots saved
   
   🛑 STOPPING HERE - Not submitting
   Press Enter to close browser...

================================================================================
TEST COMPLETE!
================================================================================

📁 Check screenshots in: screenshots/linkedin_test/
```

### Common Issues

**Issue: "LINKEDIN_EMAIL not found"**
- Solution: Add credentials to `.env` file

**Issue: "Login failed"**
- Check: Password has special characters? Use quotes in `.env`
- Check: 2FA enabled? Complete it when prompted

**Issue: "Job title field not found"**
- LinkedIn may have changed their UI
- Check screenshots to see actual page structure

### After Successful Test

If all steps pass:
1. ✅ Credentials are correct
2. ✅ Browser automation works
3. ✅ LinkedIn login works
4. ✅ Ready for production use

Then enable in Django:
```bash
# In .env
LINKEDIN_POSTING_ENABLED=True
```

Restart Django and test with real vacancy approval.
