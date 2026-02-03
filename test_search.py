"""
Test the exact IMAP search that the system uses
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
    
    # Test the EXACT search criteria used by the system
    search_criteria = '(UNSEEN SUBJECT "Open Vacancy")'
    print(f"🔍 Testing search: {search_criteria}")
    status, messages = mail.search(None, search_criteria)
    
    print(f"   Status: {status}")
    print(f"   Messages: {messages}")
    
    if status == 'OK':
        email_ids = messages[0].split()
        print(f"   Found {len(email_ids)} emails")
        print(f"   IDs: {email_ids}")
    else:
        print(f"   ❌ Search failed!")
    
    # Try alternative search
    print(f"\n🔍 Trying alternative: UNSEEN + manual filter")
    status, messages = mail.search(None, 'UNSEEN')
    if status == 'OK':
        all_unseen = messages[0].split()
        print(f"   Total UNSEEN: {len(all_unseen)}")
        
        # Now filter by subject manually
        import email as email_lib
        matching = []
        for email_id in all_unseen:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                email_message = email_lib.message_from_bytes(msg_data[0][1])
                subject = email_message.get('Subject', '')
                if subject == "Open Vacancy":
                    matching.append(email_id)
                    print(f"   ✅ Found match: ID {email_id.decode()}")
        
        print(f"\n   Manual filter found: {len(matching)} 'Open Vacancy' emails")
    
    mail.close()
    mail.logout()
    print("\n✅ Test complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
