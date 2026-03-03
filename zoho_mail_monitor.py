"""
Simple Zoho Mail Monitor for AI Recruiter
This script checks Zoho Mail for new "Open Vacancy" emails and forwards them to Django
"""

import imaplib
import email
import json
import requests
import time
import logging
import re
from datetime import datetime, timedelta
from django.utils import timezone

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoMailMonitor:
    def __init__(self):
        import os
        import sys
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Setup Django environment if not already set up
        try:
            import django
            if 'DJANGO_SETTINGS_MODULE' not in os.environ:
                os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruiter.settings')
                # Add project root to path
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                django.setup()
        except Exception as e:
            # Django might already be configured, continue
            pass
        
        # Load Zoho credentials from .env if not in environment (e.g. when running locally)
        if not os.environ.get('ZOHO_EMAIL') or not os.environ.get('ZOHO_EMAIL_PASSWORD'):
            # Try to load from .env: first in project root (same dir as this script), then parent, then cwd
            for candidate in [
                os.path.join(script_dir, '.env'),
                os.path.join(os.path.dirname(script_dir), '.env'),
                os.path.join(os.getcwd(), '.env'),
            ]:
                if os.path.isfile(candidate):
                    env_file = candidate
                    break
            else:
                env_file = None
            
            if env_file and os.path.exists(env_file):
                try:
                    with open(env_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                if key == 'ZOHO_EMAIL' and not os.environ.get('ZOHO_EMAIL'):
                                    os.environ['ZOHO_EMAIL'] = value
                                elif key == 'ZOHO_EMAIL_PASSWORD' and not os.environ.get('ZOHO_EMAIL_PASSWORD'):
                                    os.environ['ZOHO_EMAIL_PASSWORD'] = value
                except Exception as e:
                    logger.warning(f"Could not load Zoho credentials from .env file: {e}")
            else:
                # Fallback: try decouple if available
                try:
                    from decouple import config
                    zoho_email = config('ZOHO_EMAIL', default='')
                    zoho_password = config('ZOHO_EMAIL_PASSWORD', default='')
                    if zoho_email:
                        os.environ['ZOHO_EMAIL'] = zoho_email
                    if zoho_password:
                        os.environ['ZOHO_EMAIL_PASSWORD'] = zoho_password
                except ImportError:
                    pass
        
        # Zoho Mail IMAP settings
        self.imap_server = "imap.zoho.com"
        self.imap_port = 993
        
        # AI Recruiter email credentials from environment variables
        self.email_address = os.environ.get('ZOHO_EMAIL')
        self.email_password = os.environ.get('ZOHO_EMAIL_PASSWORD')
        
        if not self.email_address or not self.email_password:
            raise ValueError("ZOHO_EMAIL and ZOHO_EMAIL_PASSWORD must be set in environment variables")
        
        # Django API endpoint
        # Check if URL is explicitly set
        if os.environ.get('DJANGO_API_URL'):
            self.django_api_url = os.environ.get('DJANGO_API_URL')
            self.fallback_url = None
        # Try to detect the best URL based on environment
        elif os.environ.get('DOCKER_CONTAINER') or os.path.exists('/.dockerenv'):
            # Running in Docker - try web service first, fallback to host.docker.internal
            self.django_api_url = "http://web:8000/api/inbound/email/"
            # On Linux, host.docker.internal might not work, so try 172.17.0.1 (default Docker bridge)
            import platform
            if platform.system() == 'Linux':
                self.fallback_url = "http://172.17.0.1:8040/api/inbound/email/"
            else:
                self.fallback_url = "http://host.docker.internal:8040/api/inbound/email/"
        else:
            # Running outside Docker
            self.django_api_url = "http://127.0.0.1:8040/api/inbound/email/"
            self.fallback_url = None
        
        # Track processed emails by IMAP UID (stable across sessions); persist to file so restarts don't reprocess
        self._processed_uids_file = os.path.join(script_dir, '.zoho_processed_vacancy_uids.txt')
        self.processed_emails = self._load_processed_uids_from_file(self._processed_uids_file)
        self._processed_linkedin_uids_file = os.path.join(script_dir, '.zoho_processed_linkedin_uids.txt')
        self.processed_linkedin_uids = self._load_processed_uids_from_file(self._processed_linkedin_uids_file)
        self._processed_feedback_uids_file = os.path.join(script_dir, '.zoho_processed_feedback_uids.txt')
        self.processed_feedback_uids = self._load_processed_uids_from_file(self._processed_feedback_uids_file)
        self._processed_questionnaire_uids_file = os.path.join(script_dir, '.zoho_processed_questionnaire_uids.txt')
        self.processed_questionnaire_uids = self._load_processed_uids_from_file(self._processed_questionnaire_uids_file)

        # Test Django API connection on startup
        self._test_django_connection()

    def _test_django_connection(self):
        """Test connection to Django API on startup"""
        import time
        import socket
        
        urls_to_try = [self.django_api_url]
        if hasattr(self, 'fallback_url') and self.fallback_url:
            urls_to_try.append(self.fallback_url)
        
        max_retries = 10
        retry_delay = 3
        
        logger.info(f"🔍 Testing Django API connection...")
        logger.info(f"📋 URLs to try: {urls_to_try}")
        
        for attempt in range(max_retries):
            for url in urls_to_try:
                try:
                    # Extract host and port from URL
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    host = parsed.hostname
                    port = parsed.port or (80 if parsed.scheme == 'http' else 443)
                    
                    # First try socket connection
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2)
                        result = sock.connect_ex((host, port))
                        sock.close()
                        if result != 0:
                            logger.debug(f"⚠️ Socket connection to {host}:{port} failed")
                            continue
                    except Exception as sock_err:
                        logger.debug(f"⚠️ Socket test error for {host}:{port}: {sock_err}")
                        continue
                    
                    # Then try HTTP request
                    test_url = url.replace('/api/inbound/email/', '/admin/')
                    response = requests.get(test_url, timeout=5)
                    if response.status_code in [200, 302, 404]:  # Any response means server is up
                        logger.info(f"✅ Django API is accessible at {url}")
                        self.django_api_url = url  # Use the working URL
                        return True
                except requests.exceptions.ConnectionError as e:
                    logger.debug(f"⚠️ Attempt {attempt + 1}/{max_retries}: Cannot connect to {url}: {e}")
                except Exception as e:
                    logger.debug(f"⚠️ Attempt {attempt + 1}/{max_retries}: Error testing {url}: {str(e)}")
            
            if attempt < max_retries - 1:
                logger.info(f"⏳ Waiting {retry_delay} seconds before retry ({attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
        
        logger.warning(f"⚠️ Could not connect to Django API after {max_retries} attempts. Will continue trying during email processing...")
        logger.info(f"💡 Tip: Make sure the web service is running and accessible")
        logger.info(f"💡 Tip: Check if you can access http://web:8000/admin/ from another container")
        return False

    def _load_processed_uids_from_file(self, path, max_uids=2000):
        """Load set of already-processed UIDs from file (so restarts don't reprocess)."""
        import os
        uids = set()
        if not path or not os.path.exists(path):
            return uids
        try:
            with open(path, 'r') as f:
                for line in f:
                    uid = line.strip()
                    if uid.isdigit():
                        uids.add(uid)
            if uids:
                logger.info(f"Loaded {len(uids)} previously processed UID(s) from {os.path.basename(path)}")
        except Exception as e:
            logger.warning(f"Could not load processed UIDs file: {e}")
        return uids

    def _save_processed_uid(self, uid_str, max_uids=2000):
        """Append one UID to the vacancy processed file; trim file if too long."""
        self._save_processed_uid_to_file(uid_str, getattr(self, '_processed_uids_file', None), max_uids)

    def _save_processed_uid_to_file(self, uid_str, path, max_uids=2000):
        """Append one UID to a processed-UIDs file; trim file if too long."""
        import os
        if not path:
            return
        try:
            with open(path, 'a') as f:
                f.write(uid_str + '\n')
                f.flush()
            if os.path.exists(path):
                with open(path, 'r') as f:
                    lines = f.readlines()
                if len(lines) > max_uids:
                    with open(path, 'w') as f:
                        f.writelines(lines[-max_uids:])
        except Exception as e:
            logger.warning(f"Could not save processed UID to file: {e}")

    def connect_to_mailbox(self):
        """Connect to Zoho Mail IMAP"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            mail.select('INBOX')
            logger.info("✅ Connected to Zoho Mail successfully")
            return mail
        except Exception as e:
            logger.error(f"❌ Failed to connect to Zoho Mail: {str(e)}")
            return None

    def search_vacancy_emails(self, mail):
        """Search for unread emails with 'Open Vacancy' in subject (case-insensitive).
        Uses IMAP UID so we track by stable id; only UNSEEN so each email is processed once.
        """
        try:
            # Only unread emails (UNSEEN); use UID for stable ids
            status, messages = mail.uid('SEARCH', None, 'UNSEEN')
            if status != 'OK':
                logger.error("Failed to search emails")
                return []
            
            uids = messages[0].split()
            if not uids:
                logger.info("Found 0 unread emails in INBOX")
                return []
            
            # Filter by subject containing "open vacancy" (case-insensitive)
            vacancy_key = "open vacancy"
            matched = []
            for uid in uids:
                uid_str = uid.decode('utf-8') if isinstance(uid, bytes) else str(uid)
                try:
                    status, msg_data = mail.uid('FETCH', uid_str, '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
                    if status != 'OK' or not msg_data:
                        continue
                    raw = None
                    for part in msg_data:
                        if isinstance(part, tuple) and len(part) == 2:
                            raw = part[1]
                            break
                        if isinstance(part, bytes) and b'Subject:' in part:
                            raw = part
                            break
                    if raw is None:
                        continue
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8', errors='ignore')
                    if vacancy_key in raw.lower():
                        matched.append(uid_str)
                except Exception:
                    continue
            
            logger.info(f"Found {len(matched)} unread 'Open Vacancy' email(s)")
            return matched
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}")
            return []

    def get_email_content(self, mail, uid_str):
        """Get email content by IMAP UID (string)."""
        try:
            status, msg_data = mail.uid('FETCH', uid_str, '(RFC822)')
            if status != 'OK' or not msg_data or not msg_data[0]:
                return None
            # msg_data[0] can be (b'1 (UID 123 RFC822 {size}', b'...body...') or tuple with body in [1]
            part = msg_data[0]
            if isinstance(part, tuple) and len(part) >= 2:
                email_body = part[1]
            else:
                return None
            email_message = email.message_from_bytes(email_body)
            
            from_address = email_message.get('From', '')
            subject = email_message.get('Subject', '')
            
            body = ""
            if email_message.is_multipart():
                for p in email_message.walk():
                    if p.get_content_type() == "text/plain":
                        body = p.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                # If no text/plain (HTML-only email), use text/html and strip tags so API can parse Manager Email etc.
                if not body or not body.strip():
                    for p in email_message.walk():
                        if p.get_content_type() == "text/html":
                            raw = p.get_payload(decode=True)
                            if raw:
                                import re
                                html = raw.decode('utf-8', errors='ignore')
                                body = re.sub(r'<[^>]+>', ' ', html)
                                body = re.sub(r'\s+', ' ', body).strip()
                            break
            else:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            return {
                'from_address': from_address,
                'subject': subject,
                'body': body,
                'email_id': str(uid_str)
            }
        except Exception as e:
            logger.error(f"Error getting email content: {str(e)}")
            return None

    def send_to_django_api(self, email_data):
        """Send email data to Django API with fallback URL support"""
        headers = {
            'Content-Type': 'application/json',
        }
        
        # Try primary URL first
        urls_to_try = [self.django_api_url]
        if hasattr(self, 'fallback_url') and self.fallback_url:
            urls_to_try.append(self.fallback_url)
        
        for url in urls_to_try:
            try:
                logger.info(f"🔗 Attempting to connect to: {url}")
                response = requests.post(
                    url,
                    json=email_data,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"✅ Email sent to Django API successfully at {url}")
                    return True
                else:
                    logger.warning(f"⚠️ Django API returned {response.status_code} at {url}: {response.text}")
                    # Continue to next URL if available
                    continue
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"⚠️ Connection failed to {url}: {str(e)}")
                # Try next URL if available
                continue
            except Exception as e:
                logger.warning(f"⚠️ Error sending to {url}: {str(e)}")
                # Try next URL if available
                continue
        
        # All URLs failed
        logger.error(f"❌ Failed to send email to Django API after trying {len(urls_to_try)} URL(s)")
        return False

    def mark_email_as_read(self, mail, uid_str):
        """Mark email as read by IMAP UID."""
        try:
            # Use numeric UID and flags in (\\Seen) form to avoid server syntax errors
            uid_val = int(uid_str) if isinstance(uid_str, str) and uid_str.isdigit() else uid_str
            mail.uid('STORE', uid_val, '+FLAGS', '(\\Seen)')
            logger.info(f"✅ Marked email (UID {uid_val}) as read")
        except Exception as e:
            logger.error(f"❌ Failed to mark email as read: {str(e)}")

    def process_vacancy_emails(self):
        """Process all new vacancy emails"""
        mail = self.connect_to_mailbox()
        if not mail:
            return 0
        
        try:
            # Search for unread "Open Vacancy" emails (returns list of UID strings)
            uid_list = self.search_vacancy_emails(mail)
            processed_count = 0
            
            for uid_str in uid_list:
                # Skip if already processed (in-memory or from file)
                if uid_str in self.processed_emails:
                    continue
                
                # Get email content by UID
                email_data = self.get_email_content(mail, uid_str)
                if not email_data:
                    continue
                
                logger.info(f"Processing email from: {email_data['from_address']}")
                logger.info(f"Subject: {email_data['subject']}")
                
                # Send to Django API
                success = self.send_to_django_api(email_data)
                if success:
                    # Mark as read, track in memory and persist to file
                    self.mark_email_as_read(mail, uid_str)
                    self.processed_emails.add(uid_str)
                    self._save_processed_uid(uid_str)
                    processed_count += 1
                    logger.info(f"✅ Successfully processed email from {email_data['from_address']}")
                else:
                    logger.error(f"❌ Failed to process email from {email_data['from_address']}")
            
            logger.info(f"Processed {processed_count} new vacancy emails")
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing emails: {str(e)}")
            return 0
        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass

    def process_hr_posted_replies_once(self):
        """Process UNSEEN emails where the BODY (or subject) contains 'Posted' (HR confirmation)."""
        mail = self.connect_to_mailbox()
        if not mail:
            return 0
        try:
            # Search all UNSEEN and then filter by body contains 'Posted'
            status, msg_ids = mail.search(None, '(UNSEEN)')
            if status != 'OK':
                return 0
            ids = msg_ids[0].split()
            processed = 0
            for email_id in ids:
                email_data = self.get_email_content(mail, email_id)
                if not email_data:
                    continue
                body_lower = (email_data.get('body') or '').lower()
                subject_lower = (email_data.get('subject') or '').lower()
                if 'posted' not in body_lower and 'posted' not in subject_lower:
                    continue
                # Forward to same inbound endpoint; server will flip vacancy status
                ok = self.send_to_django_api(email_data)
                if ok:
                    self.mark_email_as_read(mail, email_id)
                    processed += 1
            return processed
        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass

    def run_continuous_monitoring(self, interval_seconds=10):
        """Run continuous email monitoring"""
        logger.info(f"🚀 Starting Zoho Mail monitoring every {interval_seconds} second(s)")
        logger.info(f"📧 Monitoring: {self.email_address}")
        logger.info(f"🔗 Django API: {self.django_api_url}")
        
        while True:
            try:
                # Process "Open Vacancy" emails
                processed = self.process_vacancy_emails()
                if processed > 0:
                    logger.info(f"📬 Processed {processed} new vacancy emails")
                
                # Process "Posted" replies from HR
                posted_count = self.process_hr_posted_replies_once()
                if posted_count > 0:
                    logger.info(f"📬 Processed {posted_count} 'Posted' reply emails")
                
                # Wait for next check
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("🛑 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {str(e)}")
                time.sleep(interval_seconds)  # Wait before retrying

    def extract_first_cv_attachment(self, email_message):
        acceptable_exts = {'.pdf', '.doc', '.docx'}
        for part in email_message.walk():
            disp = part.get_content_disposition()
            ctype = part.get_content_type() or ''
            filename = part.get_filename() or ''
            lower = (filename or '').lower()
            has_cv_ext = any(lower.endswith(ext) for ext in acceptable_exts)
            is_cv_type = ctype in ('application/pdf',
                                   'application/msword',
                                   'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            if (disp == 'attachment' or filename or is_cv_type) and (has_cv_ext or is_cv_type):
                payload = part.get_payload(decode=True)
                if payload:
                    # Ensure a filename exists
                    if not filename:
                        filename = 'resume.pdf' if ctype == 'application/pdf' else 'resume.doc'
                    return filename, payload
        return None, None

    def parse_vacancy_from_email(self, subject, body):
        if ' - ' in subject:
            parts = subject.split(' - ', 1)
            if len(parts) == 2:
                return parts[1].strip()
        for line in body.splitlines():
            if line.lower().startswith('vacancy:'):
                return line.split(':', 1)[1].strip()
        return ''

    def send_linkedin_application_to_django(self, vacancy_title, filename, file_bytes):
        try:
            files = {
                'cv_file': (filename, file_bytes),
            }
            data = {
                'vacancy_title': vacancy_title,
                'source': 'linkedin',
            }
            urls = [
                # Inside container or docker network
                "http://web:8000/api/inbound/linkedin-application/",
                # Host-mapped dev server
                "http://127.0.0.1:8040/api/inbound/linkedin-application/",
                "http://localhost:8040/api/inbound/linkedin-application/",
            ]
            last_err = None
            for url in urls:
                try:
                    resp = requests.post(url, data=data, files=files, timeout=60)
                    if resp.status_code in (200, 201):
                        logger.info(f"✅ LinkedIn application posted to Django via {url}")
                        return True
                    logger.error(
                        f"❌ Django LinkedIn inbound error: {resp.status_code} - {resp.text} via {url} "
                        f"(vacancy_title={vacancy_title!r}; email not marked read, will retry)"
                    )
                except Exception as e:
                    last_err = e
                    continue
            if last_err:
                raise last_err
            return False
        except Exception as e:
            logger.error(f"❌ Error posting LinkedIn application: {e}")
            return False

    def _linkedin_lock_acquire(self, timeout_seconds=120):
        """Acquire exclusive lock for LinkedIn processing (avoid multiple workers processing same emails). Returns True if acquired."""
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.zoho_linkedin.lock')
        if os.path.exists(path):
            try:
                age = time.time() - os.path.getmtime(path)
                if age < timeout_seconds:
                    return False
                os.unlink(path)
            except Exception:
                pass
        try:
            with open(path, 'x') as f:
                f.write(str(time.time()))
            return True
        except FileExistsError:
            return False
        except Exception:
            return False

    def _linkedin_lock_release(self):
        """Release LinkedIn processing lock."""
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.zoho_linkedin.lock')
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass

    def process_linkedin_applications_once(self):
        """Fetch fahmy@bit68.com (ZOHO_EMAIL) for unread emails with 'LinkedIn Application' in subject and process CVs. One run at a time."""
        if not self._linkedin_lock_acquire():
            logger.debug("LinkedIn processing skipped (another run in progress)")
            return 0
        try:
            return self._process_linkedin_applications_impl()
        finally:
            self._linkedin_lock_release()

    def _process_linkedin_applications_impl(self):
        """Actual LinkedIn application processing (called with lock held)."""
        # Reload processed UIDs from file so we see latest (e.g. from a previous run that just finished)
        self.processed_linkedin_uids = self._load_processed_uids_from_file(
            getattr(self, '_processed_linkedin_uids_file', None)
        )
        mail = self.connect_to_mailbox()
        if not mail:
            logger.warning("LinkedIn applications: could not connect to mailbox (check ZOHO_EMAIL/ZOHO_EMAIL_PASSWORD)")
            return 0
        processed = 0
        try:
            # Use UID SEARCH for unread; filter by subject in Python (case-insensitive)
            status, messages = mail.uid('SEARCH', None, 'UNSEEN')
            if status != 'OK':
                return 0
            uids = messages[0].split()
            if not uids:
                return 0
            linkedin_key = "linkedin application"
            matched_uids = []
            for uid in uids:
                uid_str = uid.decode('utf-8') if isinstance(uid, bytes) else str(uid)
                try:
                    status, msg_data = mail.uid('FETCH', uid_str, '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
                    if status != 'OK' or not msg_data:
                        continue
                    raw = None
                    for part in msg_data:
                        if isinstance(part, tuple) and len(part) == 2:
                            raw = part[1]
                            break
                        if isinstance(part, bytes) and b'Subject:' in part:
                            raw = part
                            break
                    if raw is None:
                        continue
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8', errors='ignore')
                    if linkedin_key in raw.lower():
                        matched_uids.append(uid_str)
                except Exception:
                    continue
            logger.info(f"Found {len(matched_uids)} unread 'LinkedIn Application' email(s)")
            for uid_str in matched_uids:
                # Only process each UID once (unread only; skip if already processed)
                if uid_str in self.processed_linkedin_uids:
                    continue
                status, msg_data = mail.uid('FETCH', uid_str, '(RFC822)')
                if status != 'OK' or not msg_data or not msg_data[0]:
                    continue
                part = msg_data[0]
                raw = part[1] if isinstance(part, tuple) and len(part) >= 2 else None
                if not raw:
                    continue
                msg = email.message_from_bytes(raw)
                subject = msg.get('Subject', '')
                body = ''
                if msg.is_multipart():
                    for p in msg.walk():
                        if p.get_content_type() == 'text/plain':
                            try:
                                body = p.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except Exception:
                                body = ''
                            break
                else:
                    try:
                        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except Exception:
                        body = ''

                vacancy_title = self.parse_vacancy_from_email(subject, body)
                filename, file_bytes = self.extract_first_cv_attachment(msg)
                logger.info(f"LinkedIn email UID {uid_str}: subject={subject[:60]!r}, vacancy_title={vacancy_title!r}, has_cv={bool(filename and file_bytes)}")
                if not filename or not file_bytes or not vacancy_title:
                    logger.warning(
                        f"Skipping UID {uid_str} - missing vacancy or CV: subject={subject[:80]!r}, "
                        f"parsed_vacancy_title={vacancy_title!r}, has_attachment={bool(filename and file_bytes)}"
                    )
                    self.mark_email_as_read(mail, uid_str)
                    self.processed_linkedin_uids.add(uid_str)
                    self._save_processed_uid_to_file(uid_str, getattr(self, '_processed_linkedin_uids_file', None))
                    continue

                ok = self.send_linkedin_application_to_django(vacancy_title, filename, file_bytes)
                if ok:
                    self.mark_email_as_read(mail, uid_str)
                    self.processed_linkedin_uids.add(uid_str)
                    self._save_processed_uid_to_file(uid_str, getattr(self, '_processed_linkedin_uids_file', None))
                    processed += 1
            return processed
        finally:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass

    def search_manager_feedback_emails(self, mail):
        """
        Search for manager feedback reply emails (UNSEEN; subject contains 'feedback').
        Matches "Re: Feedback Request: {vacancy} - {candidate}" and similar.
        Returns list of UID strings.
        """
        try:
            status, messages = mail.uid('SEARCH', None, 'UNSEEN')
            if status != 'OK':
                logger.warning("Manager feedback search failed")
                return []
            uids = messages[0].split()
            if not uids:
                return []
            key = "feedback"
            matched = []
            for uid in uids:
                uid_str = uid.decode('utf-8') if isinstance(uid, bytes) else str(uid)
                try:
                    status, msg_data = mail.uid('FETCH', uid_str, '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
                    if status != 'OK' or not msg_data:
                        continue
                    raw = None
                    for part in msg_data:
                        if isinstance(part, tuple) and len(part) == 2:
                            raw = part[1]
                            break
                        if isinstance(part, bytes) and b'Subject:' in part:
                            raw = part
                            break
                    if raw is None:
                        continue
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8', errors='ignore')
                    if key in raw.lower():
                        matched.append(uid_str)
                except Exception:
                    continue
            logger.info(f"Found {len(matched)} manager feedback email(s)")
            return matched
        except Exception as e:
            logger.error(f"Error in search_manager_feedback_emails: {e}")
            return []

    def process_manager_feedback_emails_once(self):
        """
        Process manager feedback emails (UNSEEN, subject contains 'feedback') and save to database.
        Uses UID-based fetch, marks as read, and persists UIDs so restarts don't reprocess.
        """
        try:
            from interviews.feedback_parser import ManagerFeedbackParser

            self.processed_feedback_uids = self._load_processed_uids_from_file(
                getattr(self, '_processed_feedback_uids_file', None)
            )
            mail = self.connect_to_mailbox()
            if not mail:
                logger.warning("Manager feedback: could not connect to mailbox")
                return 0

            try:
                feedback_uids = self.search_manager_feedback_emails(mail)
                if not feedback_uids:
                    return 0

                parser = ManagerFeedbackParser()
                processed_count = 0

                for uid_str in feedback_uids:
                    if uid_str in self.processed_feedback_uids:
                        continue
                    try:
                        status, msg_data = mail.uid('FETCH', uid_str, '(RFC822)')
                        if status != 'OK' or not msg_data or not msg_data[0]:
                            continue
                        part = msg_data[0]
                        raw = part[1] if isinstance(part, tuple) and len(part) >= 2 else None
                        if not raw:
                            continue
                        email_message = email.message_from_bytes(raw)
                        subject = email_message.get('Subject', '')
                        from_email = email_message.get('From', '')

                        body = self._get_email_body(email_message)
                        if not body:
                            logger.warning(f"Manager feedback UID {uid_str}: no body")
                            continue

                        candidate_name = self._extract_candidate_name_from_feedback(subject, body)
                        if not candidate_name:
                            logger.warning(f"Manager feedback UID {uid_str}: could not extract candidate name from subject/body")
                            continue

                        interview = parser.find_interview_by_candidate_name(candidate_name)
                        if not interview:
                            logger.warning(f"No interview found for candidate: {candidate_name} (UID {uid_str})")
                            continue

                        parsed_data = parser.parse_feedback_email(subject, body)
                        parser.save_manager_feedback(interview, parsed_data)

                        self.mark_email_as_read(mail, uid_str)
                        self.processed_feedback_uids.add(uid_str)
                        self._save_processed_uid_to_file(uid_str, getattr(self, '_processed_feedback_uids_file', None))
                        processed_count += 1
                        logger.info(f"Saved manager feedback for {candidate_name} (UID {uid_str})")

                    except Exception as e:
                        logger.error(f"Error processing manager feedback UID {uid_str}: {e}")
                        continue

                return processed_count

            finally:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error in process_manager_feedback_emails_once: {e}")
            return 0

    def _extract_candidate_name_from_feedback(self, subject: str, body: str) -> str:
        """
        Extract candidate name from feedback email subject or body
        """
        # Look for patterns like "Re: Feedback Request: Vacancy - John Doe"
        # The subject format is: "Re: Feedback Request: {vacancy.title} - {candidate_name}"
        patterns = [
            r'Re:\s*Feedback Request:\s*[^-]+\s*-\s*(.+?)(?:\s*$|\s*\[|\s*\(|\s*<)',  # More specific pattern
            r'Re:\s*Feedback Request:\s*[^-]+\s*-\s*(.+)',  # Original pattern
            r'Feedback Request:\s*[^-]+\s*-\s*(.+)',  # Without "Re:"
            r'Feedback for\s*(.+)',
            r'Interview with\s*(.+)',
        ]
        
        # Try subject first
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                candidate_name = match.group(1).strip()
                # Clean up any trailing characters
                candidate_name = re.sub(r'[\s\[\]()<>]+$', '', candidate_name)
                if candidate_name:
                    print(f"📝 Extracted candidate name from subject: '{candidate_name}'")
                    return candidate_name
        
        # If not found in subject, try body
        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                candidate_name = match.group(1).strip()
                candidate_name = re.sub(r'[\s\[\]()<>]+$', '', candidate_name)
                if candidate_name:
                    print(f"📝 Extracted candidate name from body: '{candidate_name}'")
                    return candidate_name
        
        print(f"⚠️ Could not extract candidate name from subject: '{subject[:100]}'")
        return None

    def _get_email_body(self, email_message):
        """
        Extract email body from email message
        """
        body = ''
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == 'text/plain':
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except Exception:
                        body = ''
                    break
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except Exception:
                body = ''
        
        return body

    def search_questionnaire_reply_emails(self, mail):
        """
        Search for candidate questionnaire reply emails
        """
        try:
            # Search for emails with 'Re:' in subject containing questionnaire
            search_criteria = '(SUBJECT "Re: Questionnaire")'
            status, messages = mail.search(None, search_criteria)
            
            if status != 'OK':
                print(f"❌ Error searching questionnaire reply emails: {messages}")
                return []
            
            return messages[0].split() if messages[0] else []
        except Exception as e:
            print(f"❌ Error in search_questionnaire_reply_emails: {e}")
            return []

    def process_questionnaire_reply_emails_once(self):
        """
        Process candidate questionnaire reply emails and save to database
        """
        try:
            # Connect to mailbox
            mail = self.connect_to_mailbox()
            if not mail:
                print("❌ Failed to connect to mailbox")
                return 0
            
            try:
                reply_emails = self.search_questionnaire_reply_emails(mail)
                if not reply_emails:
                    print("📧 No questionnaire reply emails found")
                    return 0
                
                print(f"📧 Found {len(reply_emails)} questionnaire reply emails")
                
                processed_count = 0
                
                for msg_id in reply_emails:
                    try:
                        # Fetch email content
                        status, msg_data = mail.fetch(msg_id, '(RFC822)')
                        if status != 'OK' or not msg_data:
                            continue
                        
                        # Parse email
                        email_message = email.message_from_bytes(msg_data[0][1])
                        subject = email_message.get('Subject', '')
                        from_email = email_message.get('From', '')
                        
                        # Get email body
                        body = self._get_email_body(email_message)
                        
                        # Extract candidate email from "From" field
                        candidate_email = self._extract_candidate_email_from_reply(from_email)
                        if not candidate_email:
                            print(f"⚠️ Could not extract candidate email from: {from_email}")
                            continue
                        
                        # Find profile for this reply: match by vacancy from subject
                        # Normalize subject: replies may be "Re: [bit68 - Pre-Interview Questions - Title]"
                        from candidates.models import CandidateVacancyProfile
                        _subj = (subject or "").strip().replace("Re:", "").strip()
                        if _subj.startswith("[bit68 - ") and _subj.endswith("]"):
                            _subj = _subj[9:-1].strip()
                        vacancy_title = None
                        m = re.search(r'Pre-Interview\s+Questions\s*-\s*(.+)', _subj, re.IGNORECASE)
                        if m:
                            vacancy_title = m.group(1).strip().rstrip("]").strip()
                        if not vacancy_title:
                            m = re.search(r'Questionnaire\s*-\s*(.+)', _subj, re.IGNORECASE)
                            if m:
                                vacancy_title = m.group(1).strip().rstrip("]").strip()
                        if not vacancy_title:
                            m = re.search(r'Pre-Interview\s+Questionnaire\s*-\s*(.+)', _subj, re.IGNORECASE)
                            if m:
                                vacancy_title = m.group(1).strip().rstrip("]").strip()

                        base_qs = CandidateVacancyProfile.objects.filter(
                            candidate__email__iexact=candidate_email
                        ).select_related('vacancy').order_by('-created_at')
                        if not base_qs.exists():
                            print(f"⚠️ No profile found for candidate email: {candidate_email}")
                            continue

                        if vacancy_title:
                            profile = base_qs.filter(vacancy__title__iexact=vacancy_title).first()
                            if not profile:
                                print(f"⚠️ No profile for vacancy '{vacancy_title}' and {candidate_email} — skipping reply (wrong vacancy)")
                                continue
                        else:
                            profile = base_qs.first()
                            print(f"⚠️ Could not extract vacancy from subject, using most recent profile for {candidate_email}")

                        # Update profile with questionnaire response
                        profile.questionnaire_response = body
                        profile.questionnaire_response_date = timezone.now()
                        profile.save()
                        from candidates.signals import rescore_profile_after_questionnaire
                        rescore_profile_after_questionnaire(profile)
                        print(f"✅ Saved questionnaire response for {candidate_email}")
                        processed_count += 1
                        
                    except Exception as e:
                        print(f"❌ Error processing questionnaire reply email {msg_id}: {e}")
                        continue
                
                return processed_count
                
            finally:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
            
        except Exception as e:
            print(f"❌ Error in process_questionnaire_reply_emails_once: {e}")
            return 0

    def _extract_candidate_name_from_questionnaire_reply(self, subject: str) -> str:
        """
        Extract candidate name from questionnaire reply email subject
        """
        # Look for patterns like "Re: Questionnaire - John Doe"
        patterns = [
            r'Re:\s*Questionnaire\s*-\s*(.+)',
            r'Questionnaire\s*for\s*(.+)',
            r'Re:\s*Questionnaire\s*:\s*(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def search_questionnaire_reply_emails(self, mail):
        """
        Search for candidate questionnaire reply emails (unread).
        Matches subject containing:
          - "questionnaire" (e.g. "Re: Questionnaire - X"),
          - "pre-interview questions" (e.g. "Re: [bit68 - Pre-Interview Questions - Backend lead 9]"),
          - "[bit68" (any reply to our bit68-formatted questionnaire email).
        """
        try:
            status, messages = mail.uid('SEARCH', None, 'UNSEEN')
            if status != 'OK':
                return []
            uids = messages[0].split()
            if not uids:
                return []
            matched = []
            for uid in uids:
                uid_str = uid.decode('utf-8') if isinstance(uid, bytes) else str(uid)
                try:
                    status, msg_data = mail.uid('FETCH', uid_str, '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
                    if status != 'OK' or not msg_data:
                        continue
                    raw = None
                    for part in msg_data:
                        if isinstance(part, tuple) and len(part) == 2:
                            raw = part[1]
                            break
                        if isinstance(part, bytes) and b'Subject:' in part:
                            raw = part
                            break
                    if raw is None:
                        continue
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8', errors='ignore')
                    subj_lower = raw.lower()
                    if "questionnaire" in subj_lower or "pre-interview questions" in subj_lower or "[bit68" in subj_lower:
                        matched.append(uid_str)
                except Exception:
                    continue
            logger.info(f"Found {len(matched)} questionnaire reply email(s)")
            return matched
        except Exception as e:
            logger.error(f"Error searching questionnaire reply emails: {e}")
            return []

    def process_questionnaire_reply_emails_once(self):
        """
        Process candidate questionnaire reply emails and save to database.
        Matches replies to "Pre-Interview Questionnaire - X" and "Re: Questionnaire" etc.
        Tracks processed UIDs so the same reply is never applied more than once (avoids repeated score updates).
        """
        try:
            mail = self.connect_to_mailbox()
            if not mail:
                logger.warning("Questionnaire replies: could not connect to mailbox")
                return 0
            try:
                # Reload so we see UIDs already processed by another run
                self.processed_questionnaire_uids = self._load_processed_uids_from_file(
                    getattr(self, '_processed_questionnaire_uids_file', None)
                )
                reply_uids = self.search_questionnaire_reply_emails(mail)
                if not reply_uids:
                    return 0
                processed_count = 0
                for uid_str in reply_uids:
                    if uid_str in self.processed_questionnaire_uids:
                        continue
                    try:
                        status, msg_data = mail.uid('FETCH', uid_str, '(RFC822)')
                        if status != 'OK' or not msg_data or not msg_data[0]:
                            continue
                        part = msg_data[0]
                        raw = part[1] if isinstance(part, tuple) and len(part) >= 2 else None
                        if not raw:
                            continue
                        email_message = email.message_from_bytes(raw)
                        subject = email_message.get('Subject', '')
                        from_email = email_message.get('From', '')
                        body = self._get_email_body(email_message)
                        candidate_email = self._extract_candidate_email_from_reply(from_email)
                        if not candidate_email:
                            logger.warning(f"Could not extract candidate email from: {from_email}")
                            continue
                        from candidates.models import CandidateVacancyProfile

                        # Match by vacancy from subject (outgoing: [bit68 - Pre-Interview Questions - X]; reply: Re: [bit68 - ...] or Re : [...])
                        _subj = (subject or "").strip()
                        _subj = re.sub(r'^Re\s*:\s*', '', _subj, flags=re.IGNORECASE).strip()
                        if _subj.startswith("[bit68 - ") and _subj.endswith("]"):
                            _subj = _subj[9:-1].strip()
                        vacancy_title = None
                        m = re.search(r'Pre-Interview\s+Questions\s*-\s*(.+)', _subj, re.IGNORECASE)
                        if m:
                            vacancy_title = m.group(1).strip().rstrip("]").strip()
                        if not vacancy_title:
                            m = re.search(r'Questionnaire\s*-\s*(.+)', _subj, re.IGNORECASE)
                            if m:
                                vacancy_title = m.group(1).strip().rstrip("]").strip()
                        if not vacancy_title:
                            m = re.search(r'Pre-Interview\s+Questionnaire\s*-\s*(.+)', _subj, re.IGNORECASE)
                            if m:
                                vacancy_title = m.group(1).strip().rstrip("]").strip()

                        base_qs = CandidateVacancyProfile.objects.filter(
                            candidate__email__iexact=candidate_email
                        ).select_related('vacancy').order_by('-created_at')
                        if not base_qs.exists():
                            logger.warning(f"No CandidateVacancyProfile for {candidate_email} — ensure candidate applied and has a profile for the vacancy")
                            continue

                        if vacancy_title:
                            profile = base_qs.filter(vacancy__title__iexact=vacancy_title).first()
                            if not profile:
                                logger.warning(f"No profile for vacancy '{vacancy_title}' and {candidate_email} — skipping reply (wrong vacancy)")
                                continue
                        else:
                            profile = base_qs.first()
                            logger.info(f"Could not extract vacancy from subject, using most recent profile for {candidate_email}")

                        profile.questionnaire_response = body
                        profile.questionnaire_response_date = timezone.now()
                        profile.save()
                        from candidates.signals import rescore_profile_after_questionnaire
                        rescore_profile_after_questionnaire(profile)
                        self.mark_email_as_read(mail, uid_str)
                        self.processed_questionnaire_uids.add(uid_str)
                        self._save_processed_uid_to_file(uid_str, getattr(self, '_processed_questionnaire_uids_file', None))
                        processed_count += 1
                        logger.info(f"Saved questionnaire response for {candidate_email} (UID {uid_str}, will not reprocess)")
                    except Exception as e:
                        logger.error(f"Error processing questionnaire reply UID {uid_str}: {e}")
                return processed_count
            finally:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error in process_questionnaire_reply_emails_once: {e}")
            return 0

    def _extract_candidate_name_from_questionnaire_reply(self, subject: str) -> str:
        """
        Extract candidate name from questionnaire reply email subject
        """
        # Look for patterns like "Re: Questionnaire - John Doe" or "Re: Pre-Interview Questionnaire - John Doe"
        patterns = [
            r'Re:\s*Pre-Interview\s*Questionnaire\s*-\s*(.+)',
            r'Re:\s*Questionnaire\s*-\s*(.+)',
            r'Questionnaire\s*for\s*(.+)',
            r'Re:\s*Questionnaire\s*:\s*(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def _extract_candidate_email_from_reply(self, from_field: str) -> str:
        """
        Extract candidate email from the "From" field of reply email
        """
        try:
            # Handle formats like "Name <email@domain.com>" or just "email@domain.com"
            import re
            email_pattern = r'<([^>]+)>|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            match = re.search(email_pattern, from_field)
            
            if match:
                # Return the first non-None group (either from <email> or standalone email)
                return match.group(1) or match.group(2)
            
            return None
        except Exception as e:
            print(f"❌ Error extracting email from '{from_field}': {e}")
            return None

def main():
    """Main function"""
    print("🤖 AI Recruiter Zoho Mail Monitor")
    print("=" * 50)
    
    monitor = ZohoMailMonitor()
    
    # Test connection first
    print("🔍 Testing connection to Zoho Mail...")
    mail = monitor.connect_to_mailbox()
    if mail:
        print("✅ Connection successful!")
        mail.close()
        mail.logout()
        
        # Start monitoring (interval in seconds; default 10, override via ZOHO_CHECK_INTERVAL_SECONDS)
        import os
        interval_sec = 10
        try:
            env_interval = os.environ.get('ZOHO_CHECK_INTERVAL_SECONDS')
            if env_interval is not None:
                interval_sec = int(env_interval)
        except (TypeError, ValueError):
            pass
        print("\n🚀 Starting continuous monitoring...")
        print("Press Ctrl+C to stop")
        monitor.run_continuous_monitoring(interval_seconds=interval_sec)
    else:
        print("❌ Connection failed. Please check your credentials.")

if __name__ == "__main__":
    main()
