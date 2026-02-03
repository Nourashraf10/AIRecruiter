"""
Diagnostic script to list ALL emails in Fahmy's inbox
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
    
    # Get ALL emails in inbox
    print("📬 Fetching ALL emails in INBOX...")
    status, messages = mail.search(None, 'ALL')
    all_ids = messages[0].split() if messages[0] else []
    print(f"   Total emails in inbox: {len(all_ids)}\n")
    
    # Show the last 10 emails
    print("📧 Last 10 emails in inbox:\n")
    for email_id in all_ids[-10:]:
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
            
            # Check if subject contains "vacancy" (case insensitive)
            if 'vacancy' in subject.lower() or 'open' in subject.lower():
                print(f"⚠️  CONTAINS 'vacancy' or 'open'!")
                print(f"   Exact subject bytes: {subject.encode()}")
    
    print(f"\n{'='*60}")
    
    mail.close()
    mail.logout()
    print("\n✅ Diagnostic complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
