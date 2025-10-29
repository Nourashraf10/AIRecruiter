from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from interviews.services import InterviewSchedulingService
from interviews.models import Interview, InterviewFeedback

class Command(BaseCommand):
    help = 'Send feedback request email to interviews whose end time has passed and not yet requested.'

    def add_arguments(self, parser):
        parser.add_argument('--lookback-hours',type=int, default=24, help='Scan window into the past (hours)')

    def handle(self, *args, **options):
        lookback_hours = options['lookback_hours']
        now = timezone.now()
        window_start = now - timedelta(hours=lookback_hours)    


        due_interviews = []
        qs = Interview.objects.select_related('candidate', 'manager', 'vacancy') \
                              .filter(status='scheduled',
                                      scheduled_at__gte=window_start)
        for iv in qs:
            end_time = iv.scheduled_at + timedelta(minutes=iv.duration_minutes)
            if end_time <= now and not iv.feedback_request_sent:
                # ensure not already provided feedback
                has_feedback = InterviewFeedback.objects.filter(interview=iv).exists()
                if not has_feedback:
                    due_interviews.append(iv)

        if not due_interviews:
            self.stdout.write(self.style.WARNING("No due feedback requests found."))
            return

        svc = InterviewSchedulingService()
        sent_count = 0
        for iv in due_interviews:
            result = svc.send_feedback_request(iv)
            if result.get('success'):
                sent_count += 1
            else:
                self.stdout.write(self.style.ERROR(f"Error for Interview {iv.id}: {result.get('error')}"))

        self.stdout.write(self.style.SUCCESS(f"Feedback requests sent: {sent_count}"))

