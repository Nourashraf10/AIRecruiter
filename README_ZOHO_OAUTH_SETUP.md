# 🔐 Zoho OAuth Setup Guide

This guide explains how to set up real Zoho Calendar OAuth integration for your AI Recruiter system.

## 🎯 **What You Need**

### **1. Zoho API Console Registration**
You need to register your application in Zoho's API Console to get:
- **Client ID** (public identifier)
- **Client Secret** (keep secure!)
- **Authorized Redirect URI** (where Zoho sends auth code)

### **2. Required Scopes**
Your application needs these permissions:
- `ZohoCalendar.calendar.READ` - Read calendar events
- `ZohoCalendar.calendar.CREATE` - Create calendar events  
- `ZohoCalendar.calendar.ALL` - Full calendar access (recommended)

## 🚀 **Step-by-Step Setup**

### **Step 1: Register Your Application**

1. **Go to Zoho API Console**
   - Visit: https://accounts.zoho.com/developerconsole
   - Or region-specific: https://accounts.zoho.eu (Europe) or https://accounts.zoho.in (India)

2. **Create New Client**
   - Click "Add Client" or "Get Started"
   - Choose **"Server-based (Web)"** client type
   - Fill in the details:
     ```
     Client Name: AI Recruiter Calendar Integration
     Client Domain: localhost (for development)
     Authorized Redirect URI: http://localhost:8040/api/oauth/callback/
     ```

3. **Get Your Credentials**
   - Copy the **Client ID** and **Client Secret**
   - Keep these secure - never commit them to version control

### **Step 2: Configure Environment Variables**

Update your `docker-compose.yml` with real values:

```yaml
environment:
  # Zoho OAuth Configuration
  ZOHO_CLIENT_ID: "1000.ABC123DEF456GHI789JKL012MNO345PQR678STU901VWX234YZ567890"
  ZOHO_CLIENT_SECRET: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6"
  ZOHO_REDIRECT_URI: "http://localhost:8040/api/oauth/callback/"
```

### **Step 3: Update Settings**

Add to your Django settings (`recruiter/settings.py`):

```python
# Zoho OAuth Configuration
ZOHO_CLIENT_ID = os.environ.get('ZOHO_CLIENT_ID')
ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET')
ZOHO_REDIRECT_URI = os.environ.get('ZOHO_REDIRECT_URI', 'http://localhost:8040/api/oauth/callback/')
```

### **Step 4: Test OAuth Flow**

1. **Start your application**
   ```bash
   docker-compose up -d
   ```

2. **Initiate OAuth setup for a manager**
   ```bash
   curl -X POST "http://localhost:8040/api/admin/oauth/setup/" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "manager_email=noureldin.ashraf@bit68.com"
   ```

3. **Manager authorizes access**
   - The response will include an `authorization_url`
   - Manager visits this URL and grants permission
   - Zoho redirects back to your callback URL with authorization code

4. **Check OAuth status**
   ```bash
   curl "http://localhost:8040/api/admin/oauth/status/?manager_email=noureldin.ashraf@bit68.com"
   ```

## 🔄 **OAuth Flow Explained**

### **1. Authorization Request**
```
User → Your App → Zoho Authorization URL → User grants permission → Zoho redirects back
```

### **2. Token Exchange**
```
Your App → Zoho Token Endpoint (with auth code) → Access Token + Refresh Token
```

### **3. API Access**
```
Your App → Zoho Calendar API (with access token) → Calendar data
```

### **4. Token Refresh**
```
Your App → Zoho Token Endpoint (with refresh token) → New access token
```

## 📋 **API Endpoints**

### **OAuth Setup**
```bash
POST /api/admin/oauth/setup/
Content-Type: application/x-www-form-urlencoded

manager_email=noureldin.ashraf@bit68.com
```

**Response:**
```json
{
  "success": false,
  "requires_authorization": true,
  "authorization_url": "https://accounts.zoho.com/oauth/v2/auth?scope=ZohoCalendar.calendar.ALL&client_id=...",
  "message": "Manager noureldin.ashraf@bit68.com needs to authorize calendar access"
}
```

### **OAuth Callback**
```
GET /api/oauth/callback/?code=AUTH_CODE&state=MANAGER_EMAIL
```

### **OAuth Status Check**
```bash
GET /api/admin/oauth/status/?manager_email=noureldin.ashraf@bit68.com
```

**Response:**
```json
{
  "success": true,
  "has_integration": true,
  "has_valid_token": true,
  "calendar_id": "primary",
  "expires_at": "2024-01-15T10:30:00Z",
  "is_active": true
}
```

### **Token Refresh**
```bash
POST /api/admin/oauth/refresh/
Content-Type: application/x-www-form-urlencoded

manager_email=noureldin.ashraf@bit68.com
```

## 🛠️ **Integration with Automation**

The OAuth service integrates seamlessly with your existing automation:

### **1. Automatic Calendar Discovery**
When a vacancy is approved, the system:
1. Checks if manager has OAuth integration
2. If not, initiates OAuth setup
3. If yes, uses existing tokens to access calendar

### **2. Real Calendar Access**
```python
from interviews.zoho_oauth_service import ZohoOAuthService

oauth_service = ZohoOAuthService()

# Get manager's calendars
calendars = oauth_service.get_calendar_list("manager@bit68.com")

# Get calendar events
events = oauth_service.get_calendar_events(
    "manager@bit68.com", 
    "calendar_id", 
    start_date, 
    end_date
)

# Create interview event
event_data = {
    "title": "Interview with John Doe",
    "start": "2024-01-15T10:00:00",
    "end": "2024-01-15T11:00:00",
    "description": "Technical interview for Python Developer position"
}
oauth_service.create_calendar_event("manager@bit68.com", "calendar_id", event_data)
```

## 🔒 **Security Best Practices**

### **1. Environment Variables**
- Never hardcode credentials in source code
- Use environment variables for all sensitive data
- Keep `.env` files out of version control

### **2. Token Storage**
- Store refresh tokens securely in database
- Encrypt sensitive data if possible
- Implement token rotation

### **3. HTTPS in Production**
- Use HTTPS for all OAuth redirects
- Update redirect URI for production domain
- Use secure cookie settings

## 🐛 **Troubleshooting**

### **Common Issues**

#### **1. Invalid Redirect URI**
```
Error: redirect_uri_mismatch
Solution: Ensure redirect URI in Zoho console matches exactly
```

#### **2. Invalid Client Credentials**
```
Error: invalid_client
Solution: Check Client ID and Client Secret are correct
```

#### **3. Expired Tokens**
```
Error: invalid_grant
Solution: Refresh token may be expired, re-authorize
```

#### **4. Insufficient Scopes**
```
Error: insufficient_scope
Solution: Request additional scopes in authorization URL
```

### **Debug Commands**

```bash
# Check OAuth status
curl "http://localhost:8040/api/admin/oauth/status/?manager_email=manager@bit68.com"

# Test token refresh
curl -X POST "http://localhost:8040/api/admin/oauth/refresh/" \
     -d "manager_email=manager@bit68.com"

# Check calendar integration
docker-compose exec web python manage.py shell -c "
from interviews.models import CalendarIntegration
from core.models import User
manager = User.objects.get(email='manager@bit68.com')
calendar = CalendarIntegration.objects.get(manager=manager)
print(f'Calendar ID: {calendar.calendar_id}')
print(f'Has Access Token: {bool(calendar.access_token)}')
print(f'Expires At: {calendar.token_expires_at}')
"
```

## 🚀 **Production Deployment**

### **1. Update Redirect URI**
For production, update your Zoho app settings:
```
Authorized Redirect URI: https://yourdomain.com/api/oauth/callback/
```

### **2. Environment Variables**
```bash
# Production environment
ZOHO_CLIENT_ID=your_production_client_id
ZOHO_CLIENT_SECRET=your_production_client_secret
ZOHO_REDIRECT_URI=https://yourdomain.com/api/oauth/callback/
```

### **3. Database Security**
- Use encrypted database connections
- Implement proper backup strategies
- Monitor token usage and expiry

## 📈 **Monitoring & Maintenance**

### **1. Token Monitoring**
- Monitor token expiry dates
- Implement automatic refresh
- Alert on failed token refreshes

### **2. API Usage**
- Monitor API rate limits
- Implement retry logic
- Log API errors for debugging

### **3. User Experience**
- Provide clear authorization instructions
- Handle authorization failures gracefully
- Implement re-authorization flows

---

## 🎉 **You're Ready!**

Once you complete this setup:

1. ✅ **Real calendar access** for any manager
2. ✅ **Automatic OAuth flow** integration
3. ✅ **Secure token management**
4. ✅ **Production-ready** implementation

Your AI Recruiter will have **full access** to manager calendars for automatic interview scheduling! 🚀
