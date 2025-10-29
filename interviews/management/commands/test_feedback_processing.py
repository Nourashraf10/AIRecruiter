from django.core.management.base import BaseCommand
from zoho_mail_monitor import ZohoMailMonitor

class Command(BaseCommand):
    help = 'Test manager feedback email processing'

    def handle(self, *args, **options):
        self.stdout.write('Testing manager feedback email processing...')
        
        monitor = ZohoMailMonitor()
        count = monitor.process_manager_feedback_emails_once()
        
        self.stdout.write(
            self.style.SUCCESS(f'Processed {count} manager feedback emails')
        )
