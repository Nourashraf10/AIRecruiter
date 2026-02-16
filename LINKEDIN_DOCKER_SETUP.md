# LinkedIn Automation - Docker Setup Guide

## ✅ What I've Done

I've updated your Docker configuration to support LinkedIn automation:

### 1. Updated `Dockerfile`
- ✅ Added Playwright system dependencies (browsers, fonts, libraries)
- ✅ Installed Chromium browser
- ✅ Installed browser dependencies

### 2. Updated `docker-compose.yml`
- ✅ Added LinkedIn environment variables to `web` service
- ✅ Configured to pass credentials from `.env` to container

## 🚀 How to Enable LinkedIn Automation in Docker

### Step 1: Update Your `.env` File

Add these variables to your `.env` file:

```bash
# OpenAI API Key
OPENAI_API_KEY=sk-your-actual-key-here

# LinkedIn Credentials
LINKEDIN_EMAIL=your-linkedin-email@company.com
LINKEDIN_PASSWORD="your-password-here"
LINKEDIN_COMPANY_PAGE=https://www.linkedin.com/company/your-company

# LinkedIn Automation Settings
LINKEDIN_POSTING_ENABLED=True
LINKEDIN_HEADLESS=True
```

**Important Notes:**
- Use quotes around password if it contains special characters (#, $, !, etc.)
- `LINKEDIN_HEADLESS=True` is REQUIRED for Docker (no display available)
- Make sure these are in the main `.env` file (not `.env.example`)

### Step 2: Rebuild and Restart Docker Containers

Since we updated the Dockerfile, you need to rebuild:

```bash
# Stop current containers
docker-compose down

# Rebuild with new Dockerfile (includes Playwright)
docker-compose up -d --build

# Check logs to verify it's working
docker-compose logs -f web
```

**Note**: The rebuild will take a few minutes because it needs to:
- Install system dependencies
- Install Playwright
- Download Chromium browser (~170MB)

### Step 3: Verify Configuration

Check that environment variables are loaded in the container:

```bash
# Run verification inside the web container
docker-compose exec web python verify_linkedin_integration.py
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
2. **Approve the vacancy** (click approval link)
3. **Watch Docker logs**:
   ```bash
   docker-compose logs -f web
   ```

You should see:
```
🤖 Starting automated LinkedIn posting for: [Job Title]
📝 Generating LinkedIn job post content...
✅ Generated job post
🔐 Logging into LinkedIn...
✅ Login successful
📤 Posting job to LinkedIn...
✅ Job posted successfully: [URL]
```

## 📸 Accessing Screenshots in Docker

Screenshots are saved inside the container. To view them:

### Option 1: Copy from Container
```bash
# Copy screenshots from container to your local machine
docker cp airecruiter-web-1:/app/screenshots ./screenshots_from_docker
```

### Option 2: Add Volume Mount

Update `docker-compose.yml` to mount screenshots directory:

```yaml
web:
  volumes:
    - .:/app
    - ./screenshots:/app/screenshots  # Add this line
```

Then rebuild:
```bash
docker-compose down
docker-compose up -d --build
```

Now screenshots will be saved to `./screenshots` on your host machine.

## 🐛 Troubleshooting Docker-Specific Issues

### Issue: "Playwright not found"

**Cause**: Docker image not rebuilt after adding Playwright
**Solution**:
```bash
docker-compose down
docker-compose up -d --build
```

### Issue: "Browser launch failed"

**Cause**: Missing browser dependencies or headless mode not enabled
**Solution**:
1. Ensure `LINKEDIN_HEADLESS=True` in `.env`
2. Rebuild Docker image to install dependencies
3. Check logs: `docker-compose logs web`

### Issue: "Environment variables not loaded"

**Cause**: `.env` file not in the same directory as `docker-compose.yml`
**Solution**:
1. Verify `.env` is in project root
2. Restart containers: `docker-compose restart web`
3. Check loaded vars: `docker-compose exec web env | grep LINKEDIN`

### Issue: "Cannot connect to database"

**Cause**: Database container not ready
**Solution**: The `docker-compose.yml` already has health checks, but you can verify:
```bash
docker-compose ps  # Check all containers are healthy
docker-compose logs db  # Check database logs
```

## 📋 Docker Commands Reference

```bash
# View logs (follow mode)
docker-compose logs -f web

# View logs for specific service
docker-compose logs -f celeryworker

# Restart specific service
docker-compose restart web

# Run Django management command
docker-compose exec web python manage.py shell

# Access container shell
docker-compose exec web bash

# Check environment variables
docker-compose exec web env | grep LINKEDIN

# Run verification script
docker-compose exec web python verify_linkedin_integration.py

# Copy screenshots from container
docker cp airecruiter-web-1:/app/screenshots ./screenshots_local
```

## 🔍 Monitoring in Production

### Check Automation Status

```bash
# Watch logs in real-time
docker-compose logs -f web | grep -i linkedin

# Check recent LinkedIn posts
docker-compose exec web python -c "
import django; django.setup()
from vacancies.models import Vacancy
for v in Vacancy.objects.filter(linkedin_url__isnull=False).order_by('-linkedin_posted_at')[:5]:
    print(f'{v.title}: {v.linkedin_url}')
"
```

### Check Container Health

```bash
# View all containers status
docker-compose ps

# Check resource usage
docker stats

# View recent container logs
docker-compose logs --tail=100 web
```

## ⚙️ Performance Considerations

### Browser Memory Usage

Playwright + Chromium uses ~200-300MB RAM per instance. Consider:

1. **Limit concurrent posts**: Only one vacancy approval at a time
2. **Monitor memory**: `docker stats`
3. **Increase container limits** if needed:

```yaml
web:
  deploy:
    resources:
      limits:
        memory: 2G  # Increase if needed
```

### Headless Mode

Always use `LINKEDIN_HEADLESS=True` in Docker because:
- No display available in container
- Reduces memory usage
- Faster execution
- Required for production

## 🎯 Production Checklist

Before enabling in production:

- [ ] `.env` file has all LinkedIn credentials
- [ ] `LINKEDIN_HEADLESS=True` (required for Docker)
- [ ] Docker containers rebuilt with `--build` flag
- [ ] Verification script passes all checks
- [ ] Test vacancy posted successfully
- [ ] Screenshots accessible (via volume or docker cp)
- [ ] Logs monitored for errors
- [ ] Email notifications working
- [ ] Database saving LinkedIn URLs correctly

## 📊 Current Docker Setup

Your containers:
- `airecruiter-web-1`: Django web server (port 8040)
- `airecruiter-db-1`: PostgreSQL database
- `celeryworker`: Celery worker for async tasks
- `celerybeat`: Celery beat for scheduled tasks
- `mailmonitor`: Email monitoring service
- `airecruiter-redis-1`: Redis for Celery

LinkedIn automation runs in the `web` container when a vacancy is approved.

## 🔄 Next Steps

1. ✅ Update `.env` with LinkedIn credentials
2. ✅ Rebuild Docker containers: `docker-compose up -d --build`
3. ✅ Verify configuration: `docker-compose exec web python verify_linkedin_integration.py`
4. ✅ Test with vacancy approval
5. ✅ Monitor logs: `docker-compose logs -f web`
6. ✅ Check screenshots: `docker cp airecruiter-web-1:/app/screenshots ./screenshots`

The system is ready for Docker deployment! 🚀
