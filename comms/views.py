"""
Minimal working version of comms/views.py
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from .models import IncomingEmail, OutgoingEmail
from core.models import User
from vacancies.models import Vacancy
import re
import uuid
from django.shortcuts import render, redirect
from django.views import View
from django.urls import reverse
from candidates.models import Application, CV
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.mail import send_mail



def _extract_clean_email(email_str):
    """Extract clean email address from email string"""
    if not email_str:
        return ""
    # Extract email from format like "Name <email@domain.com>" or just "email@domain.com"
    match = re.search(r'<([^>]+)>', email_str)
    if match:
        return match.group(1).strip()
    return email_str.strip()


class InboundEmailView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data or {}
        from_addr = data.get('from_address')
        subject = data.get('subject', '')
        body = data.get('body', '')
        
        if not from_addr or not body:
            return Response({"detail": "from_address and body are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Persist the raw email
        incoming = IncomingEmail.objects.create(
            from_address=from_addr,
            subject=subject,
            body=body,
            received_at=timezone.now(),
            processed=False,
            meta=data.get('meta') if isinstance(data.get('meta'), dict) else None,
        )

        # If HR confirms posting (subject/body contains "Posted"), flip vacancy to collecting_applications
        combined = f"{subject}\n{body}".lower() if (subject or body) else ''
        if 'posted' in combined:
            # Try to get title from subject like: "Re: New Vacancy Approved: Fullstack Developer"
            title = self._parse_vacancy_title_from_subject(subject)
            if not title:
                # Fallback to body lines (Vacancy: X)
                title = self._parse_vacancy_title_from_reply(body)
            vacancy_qs = Vacancy.objects.all()
            vacancy = None
            if title:
                # First try to find an approved vacancy with this title
                vacancy = vacancy_qs.filter(title__iexact=title, status='approved').first()
                # If no approved vacancy found, get any vacancy with this title
                if not vacancy:
                    vacancy = vacancy_qs.filter(title__iexact=title).first()
            # Fallback: try to extract from quoted previous subject
            if not vacancy:
                import re
                m = re.search(r"New\s+Vacancy\s+Approved:\s*(.+)", body)
                if m:
                    # First try to find an approved vacancy with this title
                    vacancy = vacancy_qs.filter(title__iexact=m.group(1).strip(), status='approved').first()
                    # If no approved vacancy found, get any vacancy with this title
                    if not vacancy:
                        vacancy = vacancy_qs.filter(title__iexact=m.group(1).strip()).first()
            if vacancy and vacancy.status == 'approved':
                vacancy.status = 'collecting_applications'
                vacancy.linkedin_posted_at = timezone.now()
                vacancy.save(update_fields=['status', 'linkedin_posted_at'])
                incoming.processed = True
                incoming.save(update_fields=['processed'])
                return Response({
                    'message': 'Vacancy moved to collecting_applications',
                    'vacancy_id': vacancy.id,
                    'title': vacancy.title
                }, status=status.HTTP_200_OK)

        # Parse email body for vacancy details
        payload = self._parse_vacancy_email(body)
        
        # Create or get the user who sent the email
        created_by = User.objects.filter(email=from_addr).first()
        if not created_by:
            created_by = User.objects.create(
                email=from_addr,
                username=from_addr.split('@')[0]
            )

        # Manager must exist or be created as minimal user
        manager_email = _extract_clean_email(payload['manager_email'])
        
        # If no manager email provided, use default manager
        if not manager_email or manager_email.strip() == '':
            manager_email = 'noureldin.ashraf@bit68.com'
            print(f"⚠️ No manager email provided, using default: {manager_email}")
        
        manager = User.objects.filter(email=manager_email).first()
        if not manager:
            manager = User.objects.create(
                email=manager_email,
                username=manager_email.split('@')[0]
            )
            print(f"✅ Created new manager user: {manager_email}")

        # Create vacancy
        vacancy = Vacancy.objects.create(
            created_by=created_by,
            title=payload['title'],
            department=payload['department'],
            manager=manager,
            keywords=payload['keywords'],
            require_dob_in_cv=payload.get('require_dob', False),
            require_egyptian=payload.get('require_egyptian', False),
            require_relevant_university=payload.get('require_relevant_university', False),
            require_relevant_major=payload.get('require_relevant_major', False),
            questionnaire_template=payload.get('questionnaire', ''),
            status='awaiting_approval'
        )

        # Generate approval token
        approval_token = str(uuid.uuid4())
        vacancy.meta = {"approval_token": approval_token}
        vacancy.save(update_fields=['meta'])

        # Send approval email to manager
        self._send_approval_email(vacancy, manager, approval_token)

        # Mark as processed
        incoming.processed = True
        incoming.save(update_fields=['processed'])

        return Response({
            "incoming_email_id": incoming.id,
            "vacancy": {
                "id": vacancy.id,
                "status": vacancy.status,
                "title": vacancy.title,
                "department": vacancy.department,
                "manager": manager.email,
                "keywords": vacancy.keywords,
            }
        }, status=status.HTTP_201_CREATED)

    def _parse_vacancy_title_from_reply(self, body: str) -> str:
        """Extract vacancy title from an HR reply body.
        Looks for lines like 'Title: X' or 'Vacancy: X'. Includes quoted content.
        """
        try:
            for line in (body or '').splitlines():
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    k = key.strip().lower()
                    if k in ('title', 'vacancy'):
                        return value.strip()
            return ''
        except Exception:
            return ''

    def _parse_vacancy_title_from_subject(self, subject: str) -> str:
        """Extract title from subjects like 'Re: New Vacancy Approved: Fullstack Developer'"""
        try:
            s = (subject or '').strip()
            # Remove common prefixes
            if s.lower().startswith('re:'):
                s = s[3:].strip()
            if s.lower().startswith('fwd:'):
                s = s[4:].strip()
            import re
            m = re.search(r"New\s+Vacancy\s+Approved:\s*(.+)$", s)
            if m:
                return m.group(1).strip()
            return ''
        except Exception:
            return ''

    def _parse_vacancy_email(self, body):
        """Parse email body to extract vacancy details"""
        lines = body.strip().split('\n')
        payload = {}
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                if key == 'title':
                    payload['title'] = value
                elif key == 'department':
                    payload['department'] = value
                elif key == 'manager_email':
                    payload['manager_email'] = value
                elif key == 'keywords':
                    payload['keywords'] = value
                elif key == 'requiredob':
                    payload['require_dob'] = value.lower() == 'true'
                elif key == 'require_egyptian':
                    payload['require_egyptian'] = value.lower() == 'true'
                elif key == 'relevant_university':
                    payload['require_relevant_university'] = value.lower() == 'true'
                elif key == 'relevant_major':
                    payload['require_relevant_major'] = value.lower() == 'true'
                elif key == 'questionnaire':
                    payload['questionnaire'] = value
        
        # Set defaults
        payload.setdefault('title', 'New Vacancy')
        payload.setdefault('department', 'General')
        payload.setdefault('manager_email', '')
        payload.setdefault('keywords', '')
        payload.setdefault('require_dob', False)
        payload.setdefault('require_egyptian', False)
        payload.setdefault('require_relevant_university', False)
        payload.setdefault('require_relevant_major', False)
        payload.setdefault('questionnaire', '')
        
        return payload

    def _send_approval_email(self, vacancy, manager, approval_token):
        """Send approval email to manager"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Use local URL with a simple landing page containing nice buttons
        # Get base URL from settings or environment
        import os
        base_url = os.environ.get('DJANGO_BASE_URL', 'http://localhost:8040')
        approval_url = f"{base_url}/approve/{approval_token}/"
        
        email_body = f"""
Dear {manager.get_full_name() or manager.username},

A new vacancy has been created and requires your approval:

Title: {vacancy.title}
Department: {vacancy.department}
Created by: {vacancy.created_by.get_full_name() or vacancy.created_by.username}

Please review and approve/reject using the following link:
{approval_url}

Best regards,
Fahmy
fahmy@bit68.com
        """.strip()

        # Store outgoing email record
        outgoing_email = OutgoingEmail.objects.create(
            to_address=manager.email,
            subject=f"Vacancy Approval Required: {vacancy.title}",
            body=email_body,
            meta={"vacancy_id": vacancy.id, "approval_token": approval_token}
        )

        # Send the approval email via SMTP
        try:
            from django.core.mail import send_mail
            # Check if email credentials are configured
            email_user = settings.EMAIL_HOST_USER
            email_password = settings.EMAIL_HOST_PASSWORD
            
            logger.info(f"📧 Attempting to send approval email to: {manager.email}")
            logger.info(f"📧 Email config - Host: {settings.EMAIL_HOST}, User: {email_user}, Password set: {bool(email_password)}")
            
            if email_user and email_password and email_user.strip():
                # Send HTML email with nicer link
                from django.core.mail import EmailMultiAlternatives
                text_content = email_body
                html_content = f"""
                <p>Dear {manager.get_full_name() or manager.username},</p>
                <p>A new vacancy has been created and requires your approval.</p>
                <p><strong>Title:</strong> {vacancy.title}<br/>
                   <strong>Department:</strong> {vacancy.department}<br/>
                   <strong>Created by:</strong> {vacancy.created_by.get_full_name() or vacancy.created_by.username}</p>
                <p>
                  <a href=\"{approval_url}\" style=\"display:inline-block;padding:12px 18px;background:#007cba;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;\">Review & Approve</a>
                </p>
                <p style=\"color:#6b7280;font-size:12px\">If the button doesn't work, copy this URL: {approval_url}</p>
                <p>Best regards,<br/>Fahmy</p>
                """.strip()

                msg = EmailMultiAlternatives(
                    subject=outgoing_email.subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[manager.email],
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=False)
                outgoing_email.sent_at = timezone.now()
                outgoing_email.save(update_fields=['sent_at'])
                logger.info(f"✅ Approval email sent successfully to: {manager.email}")
                print(f"✅ Approval email sent to: {manager.email}")
            else:
                error_msg = f"⚠️ Email credentials not configured. EMAIL_HOST_USER: {bool(email_user)}, EMAIL_HOST_PASSWORD: {bool(email_password)}"
                logger.warning(error_msg)
                print(error_msg)
                print(f"EMAIL TO SEND:")
                print(f"To: {manager.email}")
                print(f"Subject: {outgoing_email.subject}")
                print(f"Body: {email_body}")
        except Exception as e:
            error_msg = f"❌ Failed to send email to {manager.email}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(error_msg)
            import traceback
            traceback.print_exc()
            # Still log the email for debugging
            print(f"EMAIL TO SEND:")
            print(f"To: {manager.email}")
            print(f"Subject: {outgoing_email.subject}")
            print(f"Body: {email_body}")


class ManagerApprovalView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, approval_token):
        try:
            # Find vacancy by approval token in meta field
            vacancy = Vacancy.objects.filter(meta__approval_token=approval_token).first()
            if not vacancy:
                return Response({"error": "Invalid approval token"}, status=status.HTTP_404_NOT_FOUND)

            action = request.GET.get('action', '')
            
            # Show approval page
            return render(request, 'admin/approval_page.html', {
                'vacancy': vacancy,
                'approval_token': approval_token
            })
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _automate_interview_scheduling(self, vacancy):
        """Automatically check calendar and schedule interviews when vacancy is approved"""
        try:
            from .automation_service import AutomatedInterviewScheduler
            
            print(f"🤖 Starting automated interview scheduling for vacancy: {vacancy.title}")
            
            # Use the new automation service
            automation_service = AutomatedInterviewScheduler()
            result = automation_service.process_vacancy_approval(vacancy)
            
            if result['success']:
                print(f"✅ Automated interview scheduling initiated successfully")
                print(f"📧 Manager notified: {result.get('manager_notified', False)}")
                print(f"📅 Calendar discovered: {result.get('calendar_discovered', False)}")
            else:
                print(f"❌ Automated interview scheduling failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error in automated interview scheduling: {str(e)}")
            import traceback
            traceback.print_exc()


class ApplicationCollectionView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """Submit an application for a LinkedIn job posting"""
        data = request.data or {}
        
        # Extract application data
        candidate_name = data.get('candidate_name')
        candidate_email = data.get('candidate_email')
        vacancy_id = data.get('vacancy_id')
        cv_content = data.get('cv_content', '')
        
        if not all([candidate_name, candidate_email, vacancy_id]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id)
        except Vacancy.DoesNotExist:
            return Response({"error": "Vacancy not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Create candidate and application
        from candidates.models import Candidate, Application, CV
        from ai.services import AIService
        
        # Create CV
        cv = CV.objects.create(
            content=cv_content,
            file_type='text'
        )
        
        # Create candidate
        candidate = Candidate.objects.create(
            full_name=candidate_name,
            email=candidate_email,
            cv=cv
        )
        
        # Create application
        application = Application.objects.create(
            vacancy=vacancy,
            cv=cv
        )
        
        # AI analysis and scoring
        ai_service = AIService()
        ai_service.analyze_cv_and_score_candidate(cv, vacancy)
        
        return Response({
            "message": "Application submitted successfully",
            "candidate_id": candidate.id,
            "application_id": application.id
        })
        
    def get(self, request):
        """Get applications for a vacancy"""
        vacancy_id = request.GET.get('vacancy_id')
        if not vacancy_id:
            return Response({"error": "vacancy_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id)
        except Vacancy.DoesNotExist:
            return Response({"error": "Vacancy not found"}, status=status.HTTP_404_NOT_FOUND)
        
        applications = vacancy.applications.all()
        applications_data = []
        
        for app in applications:
            applications_data.append({
                "id": app.id,
                "candidate_name": app.cv.candidate.full_name if app.cv.candidate else "Unknown",
                "candidate_email": app.cv.candidate.email if app.cv.candidate else "Unknown",
                "status": app.status,
                "created_at": app.created_at
            })
        
        return Response({"applications": applications_data})


class EmailApplicationView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """Process an application received via email"""
        from_addr = request.data.get('from_address')
        subject = request.data.get('subject')
        body = request.data.get('body')

        if not all([from_addr, subject, body]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        # Parse email for vacancy reference
        vacancy_id = self._extract_vacancy_id(subject, body)
        if not vacancy_id:
            return Response({"error": "Could not identify vacancy from email"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vacancy = Vacancy.objects.get(id=vacancy_id)
        except Vacancy.DoesNotExist:
            return Response({"error": "Vacancy not found"}, status=status.HTTP_404_NOT_FOUND)

        # Create application
        from candidates.models import Candidate, Application, CV
        from ai.services import AIService

        # Create CV from email body
        cv = CV.objects.create(
            content=body,
            file_type='text'
        )

        # Create candidate
        candidate = Candidate.objects.create(
            full_name=from_addr.split('@')[0],  # Use email prefix as name
            email=from_addr,
            cv=cv
        )

        # Create application
        application = Application.objects.create(
            vacancy=vacancy,
            cv=cv
        )

        # AI analysis and scoring
        ai_service = AIService()
        ai_service.analyze_cv_and_score_candidate(cv, vacancy)

        return Response({
            "message": "Application processed successfully",
            "candidate_id": candidate.id,
            "application_id": application.id
        })

    def _extract_vacancy_id(self, subject, body):
        """Extract vacancy ID from email subject or body"""
        import re
        
        # Look for vacancy ID in subject
        match = re.search(r'vacancy[_\s]*id[_\s]*:?\s*(\d+)', subject, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Look for vacancy ID in body
        match = re.search(r'vacancy[_\s]*id[_\s]*:?\s*(\d+)', body, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        return None


class LinkedInApplicationInboundView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        vacancy_title = (request.data.get('vacancy_title') or '').strip()
        candidate_name = (request.data.get('candidate_name') or '').strip()
        candidate_email = (request.data.get('candidate_email') or '').strip()
        cv_file = request.FILES.get('cv_file')
        if not vacancy_title or not cv_file:
            return Response({'error': 'vacancy_title and cv_file are required'}, status=status.HTTP_400_BAD_REQUEST)
        vacancy = Vacancy.objects.filter(title__iexact=vacancy_title).first()
        if not vacancy:
            return Response({'error': f'Vacancy "{vacancy_title}" not found'}, status=status.HTTP_400_BAD_REQUEST)
        # Create CV
        cv = CV.objects.create(raw_file=cv_file)
        # Optionally create/link Candidate
        candidate_id = None
        if candidate_email:
            from candidates.models import Candidate
            candidate, _ = Candidate.objects.get_or_create(
                email=candidate_email,
                defaults={'full_name': candidate_name or candidate_email.split('@')[0]}
            )
            cv.candidate = candidate
            cv.save(update_fields=['candidate'])
            candidate_id = candidate.id
        # Create Application
        app = Application.objects.create(vacancy=vacancy, status='applied', cv=cv)
        return Response({'id': app.id, 'candidate_id': candidate_id}, status=status.HTTP_201_CREATED)


class ApprovalLandingView(View):
    def get(self, request, approval_token):
        # Render a simple approval page with buttons
        return render(request, 'approval_landing.html', {
            'approval_token': approval_token,
        })

    def post(self, request, approval_token):
        try:
            # Find vacancy by approval token in meta field
            vacancy = Vacancy.objects.filter(meta__approval_token=approval_token).first()
            if not vacancy:
                return render(request, 'admin/approval_page.html', {
                    'error': 'Invalid approval token'
                })

            action = request.POST.get('action')
            if action not in {'approve', 'reject'}:
                return render(request, 'admin/approval_page.html', {
                    'vacancy': vacancy,
                    'approval_token': approval_token,
                    'error': 'Invalid action'
                })

            if action == 'approve':
                vacancy.status = 'approved'
                vacancy.save(update_fields=['status'])
                
                # Send email to HR about approved vacancy
                subject = f"New Vacancy Approved: {vacancy.title}"
                message = f"""
Hello HR Team,

A new vacancy has been approved and is ready to be posted on LinkedIn:

Vacancy: {vacancy.title}
Department: {vacancy.department}
Keywords: {vacancy.keywords}
Manager: {vacancy.manager.get_full_name() or vacancy.manager.email}

Please post this vacancy on LinkedIn to start collecting applications.

Kindly reply with "Posted" to confirm posting. if you still didn't post it , don't reply.

Best regards,
Fahmy
"""

                # Send as HTML email to bold the instruction line
                from django.core.mail import EmailMultiAlternatives
                text_content = message
                html_content = f"""
                <p>Hello HR Team,</p>
                <p>A new vacancy has been approved and is ready to be posted on LinkedIn:</p>
                <ul>
                  <li><strong>Vacancy:</strong> {vacancy.title}</li>
                  <li><strong>Department:</strong> {vacancy.department}</li>
                  <li><strong>Keywords:</strong> {vacancy.keywords}</li>
                  <li><strong>Manager:</strong> {vacancy.manager.get_full_name() or vacancy.manager.email}</li>
                </ul>
                <p>Please post this vacancy on LinkedIn to start collecting applications.</p>
                <p><strong>Kindly reply with "Posted" to confirm posting. if you still didn't post it , don't reply.</strong></p>
                <p>Best regards,<br/>Fahmy</p>
                """
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=['noureldin.ashraf@bit68.com']
                )
                email.attach_alternative(html_content, "text/html")
                email.send(fail_silently=False)
                
                return render(request, 'admin/approval_page.html', {
                    'vacancy': vacancy,
                    'approval_token': approval_token,
                    'success': 'Vacancy approved successfully! HR has been notified.'
                })
                
            elif action == 'reject':
                vacancy.status = 'rejected'
                vacancy.save(update_fields=['status'])
                return render(request, 'admin/approval_page.html', {
                    'vacancy': vacancy,
                    'approval_token': approval_token,
                    'success': 'Vacancy rejected successfully!'
                })
                
        except Exception as e:
            return render(request, 'admin/approval_page.html', {
                'vacancy': vacancy if 'vacancy' in locals() else None,
                'approval_token': approval_token,
                'error': f'Error: {str(e)}'
            })
