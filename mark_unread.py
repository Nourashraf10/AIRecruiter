"""
Mark the 'Open Vacancy' email as UNREAD so it gets processed
"""
import imaplib

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
    
    # Find the 'Open Vacancy' email (ID 116)
    email_id = b'116'
    
    print(f"📧 Marking email {email_id.decode()} as UNREAD...")
    mail.store(email_id, '-FLAGS', '\\Seen')
    print("✅ Email marked as UNREAD!\n")
    
    # Verify it's unread
    status, flags = mail.fetch(email_id, '(FLAGS)')
    is_seen = b'\\Seen' in flags[0]
    print(f"   Status: {'READ' if is_seen else 'UNREAD ✓'}")
    
    mail.close()
    mail.logout()
    print("\n✅ Done! The email should be processed within 5 seconds.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
