# 🤖 Automated Interview Scheduling System

This document explains the complete automation system for calendar checking and interview scheduling in your AI Recruiter.

## 🎯 **Overview**

The system automatically:
1. **Discovers manager's calendar** when a vacancy is approved
2. **Checks availability** for interview scheduling
3. **Schedules interviews** for shortlisted candidates
4. **Sends email notifications** to managers and candidates
5. **Manages the complete workflow** from approval to interview

## 🔄 **Complete Workflow**

### **Step 1: Vacancy Creation**
```
User sends "Open Vacancy" email → AI creates vacancy → Sends approval email to manager
```

### **Step 2: Vacancy Approval (Triggers Automation)**
```
Manager clicks approval link → Vacancy approved → Automation starts
```

### **Step 3: Calendar Discovery**
```
System discovers manager's Zoho calendar → Sets up integration → Sends confirmation
```

### **Step 4: Application Collection**
```
Candidates apply → AI scores candidates → Generates shortlist (top 5)
```

### **Step 5: Interview Scheduling**
```
System checks calendar availability → Schedules interviews → Sends notifications
```

## 🛠️ **Key Components**

### **1. Automation Service (`comms/automation_service.py`)**
- **`AutomatedInterviewScheduler`** - Main automation class
- **`process_vacancy_approval()`** - Complete workflow automation
- **`check_manager_availability()`** - Calendar availability checking
- **`schedule_interviews_for_approved_vacancy()`** - Interview scheduling
- **`send_interview_reminder()`** - Reminder notifications

### **2. Calendar Integration (`interviews/zoho_api_service.py`)**
- **`CalendarDiscoveryService`** - Discovers manager calendars
- **`ZohoAPIService`** - Simulates Zoho API calls
- **Dynamic calendar discovery** based on manager email

### **3. Interview Services (`interviews/services.py`)**
- **`InterviewSchedulingService`** - Handles interview scheduling
- **`ZohoCalendarService`** - Calendar integration service
- **Email notification system**

### **4. Email Processing (`comms/views.py`)**
- **`InboundEmailView`** - Processes "Open Vacancy" emails
- **`ManagerApprovalView`** - Handles vacancy approval (triggers automation)
- **`ApplicationCollectionView`** - Processes candidate applications

## 🚀 **How to Use**

### **Method 1: Automatic (Recommended)**
1. **Send "Open Vacancy" email** to `fahmy@bit68.com`
2. **Manager receives approval email** and clicks approve
3. **System automatically**:
   - Discovers manager's calendar
   - Sends calendar setup confirmation
   - Waits for applications
   - Schedules interviews when shortlist is ready
   - Sends notifications to all parties

### **Method 2: Manual Testing**
```bash
# Test the complete workflow
python test_automated_scheduling.py

# Schedule interviews for a specific vacancy
python manage.py schedule_interviews --vacancy-id 1

# Check manager availability
curl "http://localhost:8040/api/admin/users/1/check-availability/?start_date=2024-01-15&end_date=2024-01-20&duration_minutes=60"
```

### **Method 3: Django Admin**
1. **Go to Django Admin** → Vacancies → Select vacancy
2. **Use "Interview Scheduling" section**:
   - Check availability
   - Schedule interviews
   - Send notifications

## 📧 **Email Templates**

### **Calendar Setup Confirmation**
```
Subject: 📅 Calendar Integration Confirmed - AI Recruiter

Dear [Manager Name],

Your calendar has been successfully integrated with the AI Recruiting System.

Calendar Details:
- Email: [manager@bit68.com]
- Calendar ID: [zz0801123036...]
- Timezone: [Africa/Cairo]

The system will now automatically:
1. Check your availability for interview scheduling
2. Find suitable time slots for candidate interviews
3. Send you interview notifications with candidate details
4. Manage the complete interview workflow

Best regards,
AI Recruiting System
fahmy@bit68.com
```

### **Interview Notification (Manager)**
```
Subject: Interview Scheduled: [Candidate Name] - [Position Title]

Dear [Manager Name],

An interview has been scheduled for the position: [Position Title]

Candidate: [Candidate Name]
Email: [candidate@example.com]
Phone: [Phone Number]

Interview Details:
Date: [2024-01-15]
Time: [10:00] - [11:00]
Duration: 60 minutes

Best regards,
AI Recruiting System
```

### **Interview Notification (Candidate)**
```
Subject: Interview Invitation: [Position Title]

Dear [Candidate Name],

Congratulations! You have been shortlisted for an interview for the position: [Position Title]

Interview Details:
Date: [2024-01-15]
Time: [10:00] - [11:00]
Duration: 60 minutes

Interviewer: [Manager Name]

Please prepare for the interview and arrive on time.

Best regards,
[Manager Name]
[Position Title] - Hiring Manager
```

## 🔧 **Configuration**

### **Environment Variables**
```bash
# Zoho Mail Configuration
EMAIL_HOST=smtppro.zoho.com
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=fahmy@bit68.com
EMAIL_HOST_PASSWORD=A2kK1rYB2Ns3
DEFAULT_FROM_EMAIL=fahmy@bit68.com

# OpenAI Configuration
OPENAI_API_KEY=sk-proj-...

# Django Configuration
DJANGO_DEBUG=True
```

### **Calendar Settings**
- **Default Manager**: `noureldin.ashraf@bit68.com`
- **AI Recruiter Email**: `fahmy@bit68.com`
- **Interview Duration**: 60 minutes (configurable)
- **Scheduling Window**: 7 days from approval (configurable)

## 📊 **Monitoring & Logs**

### **Check Automation Status**
```bash
# Check Django logs
tail -f logs/django.log

# Check Zoho Mail Monitor logs
tail -f logs/zoho_monitor.log

# Check automation service logs
python manage.py shell
>>> from comms.automation_service import AutomatedInterviewScheduler
>>> service = AutomatedInterviewScheduler()
>>> # Test methods
```

### **Django Admin Monitoring**
1. **Vacancies** → Check vacancy status and shortlist
2. **Interviews** → View scheduled interviews
3. **Calendar Integrations** → Check manager calendar setup
4. **Outgoing Emails** → Monitor email notifications

## 🐛 **Troubleshooting**

### **Common Issues**

#### **1. Calendar Discovery Fails**
```
Error: Failed to discover calendar for manager@bit68.com
Solution: Check manager email format and Zoho account access
```

#### **2. No Available Slots**
```
Error: Not enough available slots
Solution: Extend scheduling window or check manager's calendar
```

#### **3. Email Notifications Fail**
```
Error: Failed to send email notifications
Solution: Check Zoho Mail SMTP settings and credentials
```

#### **4. Shortlist Empty**
```
Error: No candidates in shortlist
Solution: Ensure candidates have been added and scored
```

### **Debug Commands**
```bash
# Test email sending
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'fahmy@bit68.com', ['test@example.com'])

# Test calendar discovery
python manage.py shell
>>> from interviews.zoho_api_service import CalendarDiscoveryService
>>> service = CalendarDiscoveryService()
>>> result = service.discover_manager_calendar('noureldin.ashraf@bit68.com')
>>> print(result)

# Test automation service
python manage.py shell
>>> from comms.automation_service import AutomatedInterviewScheduler
>>> from vacancies.models import Vacancy
>>> service = AutomatedInterviewScheduler()
>>> vacancy = Vacancy.objects.get(id=1)
>>> result = service.process_vacancy_approval(vacancy)
>>> print(result)
```

## 🎯 **Production Deployment**

### **1. Background Tasks**
For production, consider using:
- **Celery** for background task processing
- **Redis** for task queue
- **Cron jobs** for periodic tasks

### **2. Error Handling**
- **Retry mechanisms** for failed API calls
- **Fallback options** for calendar integration
- **Comprehensive logging** for debugging

### **3. Security**
- **API key management** for Zoho integration
- **Email authentication** with proper credentials
- **Rate limiting** for API calls

## 📈 **Future Enhancements**

1. **Real Zoho API Integration** (currently simulated)
2. **Multiple calendar support** (Google, Outlook)
3. **Interview rescheduling** capabilities
4. **Video interview integration** (Zoom, Teams)
5. **Automated feedback collection**
6. **Interview analytics** and reporting

## 🎉 **Success Metrics**

The automation system is working correctly when:
- ✅ Vacancy approval triggers calendar discovery
- ✅ Manager receives calendar setup confirmation
- ✅ Applications are automatically scored and shortlisted
- ✅ Interviews are scheduled based on availability
- ✅ All parties receive proper notifications
- ✅ Interview details are stored in database

---

**🚀 Your AI Recruiter is now fully automated! The system will handle the complete workflow from vacancy creation to interview scheduling with minimal manual intervention.**
