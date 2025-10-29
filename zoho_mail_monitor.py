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
        # Zoho Mail IMAP settings
        self.imap_server = "imap.zoho.com"
        self.imap_port = 993
        
        # AI Recruiter email credentials
        self.email_address = "fahmy@bit68.com"
        self.email_password = "A2kK1rYB2Ns3"  # Your app password
        
        # Django API endpoint (local, no ngrok)
        # Use localhost when running outside Docker, web:8000 when inside Docker
        import os
        if os.environ.get('DOCKER_CONTAINER'):
            self.django_api_url = "http://web:8000/api/inbound/email/"
        else:
            self.django_api_url = "http://127.0.0.1:8040/api/inbound/email/"
        
        # Track processed emails
        self.processed_emails = set()

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
        """Search for emails with 'Open Vacancy' subject"""
        try:
            # Search for unread emails with 'Open Vacancy' in subject
            search_criteria = '(UNSEEN SUBJECT "Open Vacancy")'
            status, messages = mail.search(None, search_criteria)
            
            if status == 'OK':
                email_ids = messages[0].split()
                logger.info(f"Found {len(email_ids)} unread 'Open Vacancy' emails")
                return email_ids
            else:
                logger.error("Failed to search emails")
                return []
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}")
            return []

    def get_email_content(self, mail, email_id):
        """Get email content by ID"""
        try:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Extract email details
                from_address = email_message.get('From', '')
                subject = email_message.get('Subject', '')
                
                # Get email body
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                else:
                    body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                
                return {
                    'from_address': from_address,
                    'subject': subject,
                    'body': body,
                    'email_id': email_id.decode('utf-8')
                }
            else:
                logger.error(f"Failed to fetch email {email_id}")
                return None
        except Exception as e:
            logger.error(f"Error getting email content: {str(e)}")
            return None

    def send_to_django_api(self, email_data):
        """Send email data to Django API"""
        try:
            headers = {
                'Content-Type': 'application/json',
            }
            
            response = requests.post(
                self.django_api_url,
                json=email_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                logger.info("✅ Email sent to Django API successfully")
                return True
            else:
                logger.error(f"❌ Django API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending to Django API: {str(e)}")
            return False

    def mark_email_as_read(self, mail, email_id):
        """Mark email as read"""
        try:
            mail.store(email_id, '+FLAGS', '\\Seen')
            logger.info(f"✅ Marked email {email_id} as read")
        except Exception as e:
            logger.error(f"❌ Failed to mark email as read: {str(e)}")

    def process_vacancy_emails(self):
        """Process all new vacancy emails"""
        mail = self.connect_to_mailbox()
        if not mail:
            return 0
        
        try:
            # Search for new vacancy emails
            email_ids = self.search_vacancy_emails(mail)
            processed_count = 0
            
            for email_id in email_ids:
                # Skip if already processed
                if email_id.decode('utf-8') in self.processed_emails:
                    continue
                
                # Get email content
                email_data = self.get_email_content(mail, email_id)
                if not email_data:
                    continue
                
                logger.info(f"Processing email from: {email_data['from_address']}")
                logger.info(f"Subject: {email_data['subject']}")
                
                # Send to Django API
                success = self.send_to_django_api(email_data)
                if success:
                    # Mark as read and track as processed
                    self.mark_email_as_read(mail, email_id)
                    self.processed_emails.add(email_id.decode('utf-8'))
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

    def run_continuous_monitoring(self, interval_minutes=5):
        """Run continuous email monitoring"""
        logger.info(f"🚀 Starting Zoho Mail monitoring every {interval_minutes} minutes")
        logger.info(f"📧 Monitoring: {self.email_address}")
        logger.info(f"🔗 Django API: {self.django_api_url}")
        
        while True:
            try:
                processed = self.process_vacancy_emails()
                if processed > 0:
                    logger.info(f"📬 Processed {processed} new emails")
                
                # Wait for next check
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("🛑 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying

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
                    logger.error(f"❌ Django LinkedIn inbound error: {resp.status_code} - {resp.text} via {url}")
                except Exception as e:
                    last_err = e
                    continue
            if last_err:
                raise last_err
            return False
        except Exception as e:
            logger.error(f"❌ Error posting LinkedIn application: {e}")
            return False

    def process_linkedin_applications_once(self):
        mail = self.connect_to_mailbox()
        if not mail:
            return 0
        processed = 0
        try:
            status, msg_ids = mail.search(None, '(UNSEEN SUBJECT "LinkedIn Application")')
            if status != 'OK':
                return 0
            ids = msg_ids[0].split()
            logger.info(f"Found {len(ids)} unread 'LinkedIn Application' emails")
            for msg_id in ids:
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status != 'OK' or not msg_data or not isinstance(msg_data, list) or not msg_data[0] or len(msg_data[0]) < 2:
                    logger.warning(f"Skipping email {msg_id.decode('utf-8')} - fetch returned no data")
                    continue
                raw = msg_data[0][1]
                if not raw:
                    logger.warning(f"Skipping email {msg_id.decode('utf-8')} - empty payload")
                    continue
                msg = email.message_from_bytes(raw)
                subject = msg.get('Subject', '')
                body = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            try:
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
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
                if not filename or not file_bytes or not vacancy_title:
                    logger.warning(f"Skipping email {msg_id.decode('utf-8')} - missing vacancy or CV")
                    self.mark_email_as_read(mail, msg_id)
                    continue

                ok = self.send_linkedin_application_to_django(vacancy_title, filename, file_bytes)
                if ok:
                    self.mark_email_as_read(mail, msg_id)
                    processed += 1
            return processed
        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass

    def search_manager_feedback_emails(self, mail):
        """
        Search for manager feedback reply emails
        """
        try:
            # Search for emails with 'Re:' in subject and from manager emails
            search_criteria = '(SUBJECT "Re: Feedback Request")'
            status, messages = mail.search(None, search_criteria)
            
            if status != 'OK':
                print(f"❌ Error searching feedback emails: {messages}")
                return []
            
            return messages[0].split() if messages[0] else []
        except Exception as e:
            print(f"❌ Error in search_manager_feedback_emails: {e}")
            return []

    def process_manager_feedback_emails_once(self):
        """
        Process manager feedback emails and save to database
        """
        try:
            from interviews.feedback_parser import ManagerFeedbackParser
            
            # Connect to mailbox
            mail = self.connect_to_mailbox()
            if not mail:
                print("❌ Failed to connect to mailbox")
                return 0
            
            try:
                feedback_emails = self.search_manager_feedback_emails(mail)
                if not feedback_emails:
                    print("📧 No manager feedback emails found")
                    return 0
                
                print(f"📧 Found {len(feedback_emails)} manager feedback emails")
                
                parser = ManagerFeedbackParser()
                processed_count = 0
                
                for msg_id in feedback_emails:
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
                        
                        # Extract candidate name from subject or body
                        candidate_name = self._extract_candidate_name_from_feedback(subject, body)
                        if not candidate_name:
                            continue
                        
                        # Find corresponding interview
                        interview = parser.find_interview_by_candidate_name(candidate_name)
                        if not interview:
                            print(f"⚠️ No interview found for candidate: {candidate_name}")
                            continue
                        
                        # Parse feedback data
                        parsed_data = parser.parse_feedback_email(subject, body)
                        
                        # Save feedback
                        feedback = parser.save_manager_feedback(interview, parsed_data)
                        
                        print(f"✅ Saved feedback for {candidate_name}: Rating={parsed_data['rating']}, Recommended={parsed_data['recommended']}")
                        processed_count += 1
                        
                    except Exception as e:
                        print(f"❌ Error processing feedback email {msg_id}: {e}")
                        continue
                
                return processed_count
                
            finally:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
            
        except Exception as e:
            print(f"❌ Error in process_manager_feedback_emails_once: {e}")
            return 0

    def _extract_candidate_name_from_feedback(self, subject: str, body: str) -> str:
        """
        Extract candidate name from feedback email subject or body
        """
        # Look for patterns like "Re: Feedback Request: Vacancy - John Doe"
        patterns = [
            r'Re:\s*Feedback Request:\s*[^-]+\s*-\s*(.+)',
            r'Feedback for\s*(.+)',
            r'Interview with\s*(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If not found in subject, try body
        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
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
                        
                        # Find corresponding candidate vacancy profile by email
                        from candidates.models import CandidateVacancyProfile
                        profile = CandidateVacancyProfile.objects.filter(
                            candidate__email__iexact=candidate_email
                        ).first()
                        
                        if not profile:
                            print(f"⚠️ No profile found for candidate email: {candidate_email}")
                            continue
                        
                        # Update profile with questionnaire response
                        profile.questionnaire_response = body
                        profile.questionnaire_response_date = timezone.now()
                        profile.save()
                        
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
                        
                        # Find corresponding candidate vacancy profile by email
                        from candidates.models import CandidateVacancyProfile
                        profile = CandidateVacancyProfile.objects.filter(
                            candidate__email__iexact=candidate_email
                        ).first()
                        
                        if not profile:
                            print(f"⚠️ No profile found for candidate email: {candidate_email}")
                            continue
                        
                        # Update profile with questionnaire response
                        profile.questionnaire_response = body
                        profile.questionnaire_response_date = timezone.now()
                        profile.save()
                        
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
        
        # Start monitoring
        print("\n🚀 Starting continuous monitoring...")
        print("Press Ctrl+C to stop")
        monitor.run_continuous_monitoring()
    else:
        print("❌ Connection failed. Please check your credentials.")

if __name__ == "__main__":
    main()
