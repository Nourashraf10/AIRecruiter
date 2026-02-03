"""
Find emails from today (2026-02-02)
"""
import imaplib
import email as email_lib
from datetime import datetime

# Zoho credentials
ZOHO_EMAIL = "fahmy@bit68.com"
ZOHO_PASSWORD = "A2kK1rYB2Ns3"

try:
    # Connect to Zoho IMAP
    print("🔌 Connecting to Zoho Mail...")
    mail = imaplib.IMAP4_SSL("imap.zoho.com", 993)
    mail.login(ZOHO_EMAIL, ZOHO_PASSWORD)
    mail.select('INBOX')
    print("✅ Connected successfully!\n")
    
    # Search for emails from today (2-Feb-2026)
    print("🔍 Searching for emails from today (2-Feb-2026)...")
    status, messages = mail.search(None, '(SINCE "2-Feb-2026")')
    today_ids = messages[0].split() if messages[0] else []
    print(f"   Found {len(today_ids)} emails from today\n")
    
    # Show all emails from today
    if today_ids:
        print("📧 Emails from today:\n")
        for email_id in today_ids:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                email_message = email_lib.message_from_bytes(msg_data[0][1])
                from_addr = email_message.get('From', '')
                subject = email_message.get('Subject', '')
                date = email_message.get('Date', '')
                
                # Check if seen
                status, flags = mail.fetch(email_id, '(FLAGS)')
                is_seen = b'\\Seen' in flags[0]
                
                print(f"{'='*60}")
                print(f"ID: {email_id.decode()}")
                print(f"From: {from_addr}")
                print(f"Subject: '{subject}'")
                print(f"Date: {date}")
                print(f"Status: {'READ ✓' if is_seen else 'UNREAD ✉'}")
                
                # Check if it's about vacancy
                if 'vacancy' in subject.lower() or 'open' in subject.lower():
                    print(f"⚠️  THIS IS A VACANCY EMAIL!")
                    
                    # Get body preview
                    body = ''
                    if email_message.is_multipart():
                        for part in email_message.walk():
                            if part.get_content_type() == 'text/plain':
                                try:
                                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                except:
                                    pass
                                break
                    else:
                        try:
                            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass
                    
                    if body:
                        print(f"\n   Body preview (first 300 chars):")
                        print(f"   {body[:300]}")
    else:
        print("❌ No emails found from today!")
    
    print(f"\n{'='*60}")
    
    mail.close()
    mail.logout()
    print("\n✅ Search complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
