"""
Final diagnostic - show ALL unread emails regardless of subject
"""
import imaplib
import email as email_lib

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
    
    # Get ALL UNSEEN emails
    print("📬 Fetching ALL UNREAD emails in INBOX...")
    status, messages = mail.search(None, 'UNSEEN')
    unseen_ids = messages[0].split() if messages[0] else []
    print(f"   Total UNREAD emails: {len(unseen_ids)}\n")
    
    if unseen_ids:
        print("📧 UNREAD emails:\n")
        for email_id in unseen_ids:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                email_message = email_lib.message_from_bytes(msg_data[0][1])
                from_addr = email_message.get('From', '')
                subject = email_message.get('Subject', '')
                date = email_message.get('Date', '')
                
                print(f"{'='*70}")
                print(f"ID: {email_id.decode()}")
                print(f"From: {from_addr}")
                print(f"Subject: '{subject}'")
                print(f"Subject (repr): {repr(subject)}")
                print(f"Date: {date}")
                
                # Check exact match
                if subject == "Open Vacancy":
                    print(f"✅ EXACT MATCH for 'Open Vacancy'!")
                elif "open" in subject.lower() and "vacancy" in subject.lower():
                    print(f"⚠️  Contains 'open' and 'vacancy' but not exact match")
                    print(f"   Subject bytes: {subject.encode()}")
    else:
        print("❌ No UNREAD emails found in inbox!")
        print("\n   Checking if there are ANY emails at all...")
        status, messages = mail.search(None, 'ALL')
        all_ids = messages[0].split() if messages[0] else []
        print(f"   Total emails in inbox: {len(all_ids)}")
    
    print(f"\n{'='*70}")
    
    mail.close()
    mail.logout()
    print("\n✅ Diagnostic complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
