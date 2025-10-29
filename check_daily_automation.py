#!/usr/bin/env python3
"""
Script to check if daily automation ran and handle missed days
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruiter.settings')
django.setup()

from comms.daily_automation_service import DailyAutomationService
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def check_and_run_automation():
    """Check if automation ran today, if not, run it"""
    print("🔍 Checking Daily Automation Status")
    print("=" * 40)
    
    # Check if cron.log exists and was updated today
    log_file = "/Users/NourSereg/Desktop/AI_Agent/cron.log"
    
    if os.path.exists(log_file):
        # Get file modification time
        mod_time = datetime.fromtimestamp(os.path.getmtime(log_file))
        today = datetime.now().date()
        
        print(f"📅 Last cron run: {mod_time}")
        print(f"📅 Today's date: {today}")
        
        if mod_time.date() == today:
            print("✅ Daily automation already ran today!")
            return
        else:
            print("⚠️ Daily automation hasn't run today. Running now...")
    else:
        print("⚠️ No cron log found. Running daily automation...")
    
    # Run the automation
    try:
        automation_service = DailyAutomationService()
        result = automation_service.process_daily_interview_scheduling()
        
        if result['success']:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ Automation failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error running automation: {str(e)}")

if __name__ == '__main__':
    check_and_run_automation()

