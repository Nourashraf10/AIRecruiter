from django.core.management.base import BaseCommand
from comms.models import OutgoingEmail
from vacancies.models import Vacancy
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Check and resend approval emails for vacancies awaiting approval'

    def add_arguments(self, parser):
        parser.add_argument(
            '--resend',
            action='store_true',
            help='Resend approval emails that were not sent',
        )

    def handle(self, *args, **options):
        # Find vacancies awaiting approval
        vacancies = Vacancy.objects.filter(status='awaiting_approval')
        
        self.stdout.write(f'Found {vacancies.count()} vacancies awaiting approval')
        
        for vacancy in vacancies:
            self.stdout.write(f'\n--- Vacancy: {vacancy.title} (ID: {vacancy.id}) ---')
            self.stdout.write(f'Manager: {vacancy.manager.email}')
            self.stdout.write(f'Status: {vacancy.status}')
            
            # Check for approval email
            approval_token = vacancy.meta.get('approval_token') if vacancy.meta else None
            if not approval_token:
                self.stdout.write(self.style.WARNING('  ⚠️ No approval token found'))
                continue
            
            # Find outgoing email
            outgoing_emails = OutgoingEmail.objects.filter(
                to_address=vacancy.manager.email,
                subject__icontains='Approval Required'
            ).order_by('-created_at')
            
            if outgoing_emails.exists():
                email = outgoing_emails.first()
                self.stdout.write(f'  📧 Email record found (ID: {email.id})')
                self.stdout.write(f'  📧 Subject: {email.subject}')
                self.stdout.write(f'  📧 Sent at: {email.sent_at or "NOT SENT"}')
                
                if not email.sent_at:
                    self.stdout.write(self.style.WARNING('  ⚠️ Email was NOT sent!'))
                    
                    if options['resend']:
                        self.stdout.write('  🔄 Attempting to resend...')
                        from comms.views import InboundEmailView
                        view = InboundEmailView()
                        view._send_approval_email(vacancy, vacancy.manager, approval_token)
                        self.stdout.write(self.style.SUCCESS('  ✅ Resend attempted'))
                else:
                    self.stdout.write(self.style.SUCCESS('  ✅ Email was sent'))
            else:
                self.stdout.write(self.style.WARNING('  ⚠️ No approval email record found'))
                
                if options['resend']:
                    self.stdout.write('  🔄 Attempting to send...')
                    from comms.views import InboundEmailView
                    view = InboundEmailView()
                    view._send_approval_email(vacancy, vacancy.manager, approval_token)
                    self.stdout.write(self.style.SUCCESS('  ✅ Send attempted'))



