"""
Quick test script to check Zoho inbox for 'Open Vacancy' emails
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
    
    # Search for ALL emails with 'Open Vacancy' in subject (read or unread)
    print("🔍 Searching for ALL 'Open Vacancy' emails...")
    status, messages = mail.search(None, '(SUBJECT "Open Vacancy")')
    all_ids = messages[0].split() if messages[0] else []
    print(f"   Found {len(all_ids)} total 'Open Vacancy' emails\n")
    
    # Search for UNSEEN emails with 'Open Vacancy' in subject
    print("🔍 Searching for UNSEEN 'Open Vacancy' emails...")
    status, messages = mail.search(None, '(UNSEEN SUBJECT "Open Vacancy")')
    unseen_ids = messages[0].split() if messages[0] else []
    print(f"   Found {len(unseen_ids)} unread 'Open Vacancy' emails\n")
    
    # Show details of all 'Open Vacancy' emails
    if all_ids:
        print("📧 Email details:")
        for email_id in all_ids[-5:]:  # Show last 5
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                email_message = email_lib.message_from_bytes(msg_data[0][1])
                from_addr = email_message.get('From', '')
                subject = email_message.get('Subject', '')
                date = email_message.get('Date', '')
                
                # Check if seen
                status, flags = mail.fetch(email_id, '(FLAGS)')
                is_seen = b'\\Seen' in flags[0]
                
                print(f"\n   ID: {email_id.decode()}")
                print(f"   From: {from_addr}")
                print(f"   Subject: {subject}")
                print(f"   Date: {date}")
                print(f"   Status: {'READ' if is_seen else 'UNREAD'}")
    
    mail.close()
    mail.logout()
    print("\n✅ Test complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
