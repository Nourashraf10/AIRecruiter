from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from interviews.models import Interview
from interviews.services import InterviewSchedulingService

class Command(BaseCommand):
    help = "Test feedback request scheduling for interviews"

    def add_arguments(self, parser):
        parser.add_argument('--interview-id', type=int, help='Specific interview ID to test')
        parser.add_argument('--schedule-in-minutes', type=int, default=2, 
                          help='Schedule feedback request in X minutes (default: 2)')

    def handle(self, *args, **options):
        interview_id = options.get('interview_id')
        schedule_in_minutes = options.get('schedule_in_minutes')
        
        if interview_id:
            # Test specific interview
            try:
                interview = Interview.objects.get(id=interview_id)
                self.stdout.write(f"Testing feedback scheduling for interview {interview_id}")
                self.stdout.write(f"Interview: {interview.candidate.full_name} - {interview.vacancy.title}")
                self.stdout.write(f"Scheduled at: {interview.scheduled_at}")
                
                # Temporarily modify the interview time for testing
                test_time = timezone.now() + timedelta(minutes=schedule_in_minutes)
                interview.scheduled_at = test_time
                interview.save()
                
                # Schedule feedback request
                service = InterviewSchedulingService()
                result = service.schedule_feedback_request(interview)
                
                if result.get('success'):
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Feedback request scheduled successfully!")
                    )
                    self.stdout.write(f"Task ID: {result.get('task_id')}")
                    self.stdout.write(f"Scheduled for: {result.get('scheduled_for')}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Failed to schedule feedback request: {result.get('error')}")
                    )
                    
            except Interview.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"❌ Interview with ID {interview_id} not found")
                )
        else:
            # Show all interviews
            interviews = Interview.objects.all().order_by('-created_at')[:10]
            if interviews:
                self.stdout.write("Recent interviews:")
                for interview in interviews:
                    self.stdout.write(f"ID: {interview.id} - {interview.candidate.full_name} - {interview.vacancy.title} - {interview.scheduled_at}")
            else:
                self.stdout.write("No interviews found. Create some interviews first.")
