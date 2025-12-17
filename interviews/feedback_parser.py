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
        profile_updated = self.update_candidate_vacancy_profile(interview, parsed_data)
        
        # Send hiring recommendation email only if:
        # 1. This is the first time feedback is being saved (created=True)
        # 2. OR the profile was just updated with new feedback and email hasn't been sent yet
        if created or (profile_updated and not profile_updated.recommendation_email_sent):
            self.send_hiring_recommendation(interview)
        
        return feedback
    
    def send_hiring_recommendation(self, interview: Interview):
        """
        Generate and send AI-powered hiring recommendation email to manager
        Only sends if it hasn't been sent before
        """
        try:
            from .hiring_recommendation_service import HiringRecommendationService
            from candidates.models import CandidateVacancyProfile
            
            # Get the candidate vacancy profile
            profile = CandidateVacancyProfile.objects.filter(
                candidate=interview.candidate,
                vacancy=interview.vacancy
            ).first()
            
            if not profile:
                print(f"⚠️ No candidate vacancy profile found for {interview.candidate.full_name} - {interview.vacancy.title}")
                return
            
            # Check if recommendation email has already been sent
            if profile.recommendation_email_sent:
                print(f"ℹ️ Hiring recommendation email already sent for {interview.candidate.full_name} - {interview.vacancy.title}. Skipping.")
                return
            
            # Generate hiring recommendation
            recommendation_service = HiringRecommendationService()
            recommendation = recommendation_service.generate_hiring_recommendation(profile)
            
            # Send email to manager
            success = recommendation_service.send_recommendation_email(profile, recommendation)
            
            if success:
                # Mark as sent
                profile.recommendation_email_sent = True
                profile.recommendation_email_sent_at = timezone.now()
                profile.save(update_fields=['recommendation_email_sent', 'recommendation_email_sent_at'])
                print(f"✅ Hiring recommendation email sent to {interview.vacancy.manager.email}")
            else:
                print(f"❌ Failed to send hiring recommendation email")
                
        except Exception as e:
            print(f"❌ Error sending hiring recommendation: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def update_candidate_vacancy_profile(self, interview: Interview, parsed_data: Dict):
        """
        Update the candidate vacancy profile with manager feedback
        Returns the profile object if it was updated, None otherwise
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
                # Check if feedback is actually new (not just a re-processing)
                feedback_changed = (
                    profile.manager_feedback != parsed_data['feedback_text'] or
                    profile.manager_rating != parsed_data['rating'] or
                    profile.manager_recommendation != parsed_data['recommended']
                )
                
                # Update existing profile
                profile.manager_feedback = parsed_data['feedback_text']
                profile.manager_rating = parsed_data['rating']
                profile.manager_recommendation = parsed_data['recommended']
                profile.feedback_received_date = timezone.now()
                profile.application_status = 'interview_done'
                profile.save()
                
                # Only return profile if feedback actually changed
                if feedback_changed:
                    return profile
                else:
                    return None
            else:
                # New profile created, return it
                return profile
                
        except Exception as e:
            print(f"⚠️ Error updating candidate vacancy profile: {e}")
            return None
