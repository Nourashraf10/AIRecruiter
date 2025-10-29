import re
from typing import Dict, Optional
from django.utils import timezone
from .models import Interview, ManagerFeedback

class ManagerFeedbackParser:
    """
    Parses manager feedback emails and extracts structured data
    """
    
    def __init__(self):
        self.rating_patterns = [
            r'rating[:\s]*(\d+)',
            r'score[:\s]*(\d+)',
            r'(\d+)/5',
            r'(\d+)/10'
        ]
        
        self.recommendation_patterns = [
            r'recommend[:\s]*(yes|no|true|false)',
            r'hire[:\s]*(yes|no|true|false)',
            r'proceed[:\s]*(yes|no|true|false)'
        ]
    
    def parse_feedback_email(self, email_subject: str, email_body: str) -> Dict:
        """
        Parse manager feedback email and extract structured data
        """
        result = {
            'feedback_text': email_body.strip(),
            'rating': None,
            'recommended': None
        }
        
        # Extract rating
        for pattern in self.rating_patterns:
            match = re.search(pattern, email_body.lower())
            if match:
                rating = int(match.group(1))
                if 1 <= rating <= 5:
                    result['rating'] = rating
                elif 1 <= rating <= 10:
                    result['rating'] = (rating + 1) // 2  # Convert 1-10 to 1-5
                break
        
        # Extract recommendation
        for pattern in self.recommendation_patterns:
            match = re.search(pattern, email_body.lower())
            if match:
                value = match.group(1).lower()
                result['recommended'] = value in ['yes', 'true']
                break
        
        return result
    
    def find_interview_by_candidate_name(self, candidate_name: str) -> Optional[Interview]:
        """
        Find interview by candidate name in feedback email
        """
        # Try exact match first
        interview = Interview.objects.filter(
            candidate__full_name__iexact=candidate_name
        ).first()
        
        if not interview:
            # Try partial match
            interview = Interview.objects.filter(
                candidate__full_name__icontains=candidate_name
            ).first()
        
        return interview
    
    def save_manager_feedback(self, interview: Interview, parsed_data: Dict) -> ManagerFeedback:
        """
        Save manager feedback to database
        """
        feedback, created = ManagerFeedback.objects.get_or_create(
            interview=interview,
            defaults={
                'feedback_text': parsed_data['feedback_text'],
                'rating': parsed_data['rating'],
                'recommended': parsed_data['recommended'],
                'received_at': timezone.now()
            }
        )
        
        if not created:
            # Update existing feedback
            feedback.feedback_text = parsed_data['feedback_text']
            feedback.rating = parsed_data['rating']
            feedback.recommended = parsed_data['recommended']
            feedback.save()
        
        # Also update the CandidateVacancyProfile
        self.update_candidate_vacancy_profile(interview, parsed_data)
        
        return feedback
    
    def update_candidate_vacancy_profile(self, interview: Interview, parsed_data: Dict):
        """
        Update the candidate vacancy profile with manager feedback
        """
        try:
            from candidates.models import CandidateVacancyProfile
            
            profile, created = CandidateVacancyProfile.objects.get_or_create(
                candidate=interview.candidate,
                vacancy=interview.vacancy,
                defaults={
                    'application_status': 'interview_done',
                    'interview_scheduled': True,
                    'interview_date': interview.scheduled_at,
                    'interview_duration': interview.duration_minutes,
                    'manager_feedback': parsed_data['feedback_text'],
                    'manager_rating': parsed_data['rating'],
                    'manager_recommendation': parsed_data['recommended'],
                    'feedback_received_date': timezone.now()
                }
            )
            
            if not created:
                # Update existing profile
                profile.manager_feedback = parsed_data['feedback_text']
                profile.manager_rating = parsed_data['rating']
                profile.manager_recommendation = parsed_data['recommended']
                profile.feedback_received_date = timezone.now()
                profile.application_status = 'interview_done'
                profile.save()
                
        except Exception as e:
            print(f"⚠️ Error updating candidate vacancy profile: {e}")
