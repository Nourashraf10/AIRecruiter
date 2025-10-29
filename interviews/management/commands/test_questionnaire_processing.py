from django.core.management.base import BaseCommand
from zoho_mail_monitor import ZohoMailMonitor

class Command(BaseCommand):
    help = 'Test candidate questionnaire reply email processing'

    def handle(self, *args, **options):
        self.stdout.write('Testing candidate questionnaire reply email processing...')
        
        monitor = ZohoMailMonitor()
        count = monitor.process_questionnaire_reply_emails_once()
        
        self.stdout.write(
            self.style.SUCCESS(f'Processed {count} questionnaire reply emails')
        )
