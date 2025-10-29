from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import CV, Application, Candidate
from ai.services import AIService


@receiver(post_save, sender=CV)
def extract_cv_data_on_upload(sender, instance, created, **kwargs):
    """Automatically extract CV data and create Candidate when a CV is uploaded"""
    if created and instance.raw_file:
        try:
            print(f"🔄 Processing CV file: {instance.raw_file.name}...")
            
            # Initialize AI service
            ai_service = AIService()
            
            # Extract text from CV file
            cv_text = ai_service._extract_text_from_cv_file(instance.raw_file)
            
            # Extract structured data using AI
            extracted_data = ai_service.extract_cv_data(cv_text, instance.raw_file)
            
            # Create or get candidate from extracted data
            personal_info = extracted_data.get('personal_info', {})
            
            # Get email (required field). If AI missed it, try regex from raw text.
            email = personal_info.get('email', '')
            if not email:
                import re
                match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", cv_text or '')
                email = match.group(0) if match else ''
            if not email:
                print(f"❌ No email found in CV, cannot create candidate")
                return
            
            # Create candidate with extracted data or sane defaults
            candidate, candidate_created = Candidate.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': personal_info.get('full_name') or personal_info.get('name') or 'Not Stated',
                    'phone': personal_info.get('phone') or 'Not Stated',
                    'nationality': personal_info.get('nationality') or 'Not Stated',
                    'date_of_birth': personal_info.get('date_of_birth'),
                }
            )
            
            # Update CV to link to the candidate
            instance.candidate = candidate
            instance.save()
            
            # Store AI-extracted data
            candidate.ai_extracted_data = extracted_data
            candidate.ai_extraction_date = timezone.now()
            candidate.ai_summary = extracted_data.get('summary', '')
            
            # Store the extracted text for later use in scoring
            instance.extracted_text = cv_text
            
            # Save candidate and CV
            candidate.save()
            instance.save()
            
            if candidate_created:
                print(f"✅ New candidate created: {candidate.full_name} ({candidate.email})")
            else:
                print(f"✅ Existing candidate updated: {candidate.full_name} ({candidate.email})")
            
        except Exception as e:
            print(f"❌ AI extraction failed for CV {instance.raw_file.name}: {str(e)}")
            # Fallback: try to create a minimal candidate from raw bytes
            try:
                raw_bytes = instance.raw_file.read() if instance.raw_file else b''
                text_guess = ''
                try:
                    text_guess = raw_bytes.decode('utf-8', errors='ignore')
                except Exception:
                    text_guess = ''
                import re
                email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text_guess)
                if email_match:
                    email = email_match.group(0)
                    candidate, _ = Candidate.objects.get_or_create(
                        email=email,
                        defaults={
                            'full_name': 'Not Stated',
                            'phone': 'Not Stated',
                            'nationality': 'Not Stated'
                        }
                    )
                    instance.candidate = candidate
                    instance.save(update_fields=['candidate'])
                    print(f"✅ Fallback candidate created from CV: {candidate.email}")
            except Exception as _e:
                print(f"⚠️ Fallback candidate creation also failed: {_e}")
            # Don't raise the exception to avoid breaking the CV upload


@receiver(post_save, sender=Application)
def score_candidate_on_application(sender, instance, created, **kwargs):
    """Automatically score candidate using AI when an Application is created"""
    if created and instance.cv and instance.cv.candidate:
        try:
            candidate = instance.cv.candidate
            
            # Skip if candidate already has a score for this vacancy
            if candidate.ai_score_out_of_10 is not None and candidate.latest_vacancy_scored == instance.vacancy:
                print(f"⏭️ Candidate {candidate.full_name} already scored for this vacancy, updating shortlist only...")
                # Still update shortlist even if already scored
                try:
                    update_shortlist_for_vacancy(instance.vacancy)
                except Exception as shortlist_error:
                    print(f"⚠️ Shortlist update failed: {str(shortlist_error)}")
                return
            
            print(f"🔄 Scoring candidate {candidate.full_name} for vacancy {instance.vacancy.title}...")
            
            # Initialize AI service
            ai_service = AIService()
            
            # Get CV text - use extracted_text if available, otherwise try to extract from raw_file
            cv_text = instance.cv.extracted_text
            if not cv_text and instance.cv.raw_file:
                cv_text = ai_service._extract_text_from_cv_file(instance.cv.raw_file)
                # Store the extracted text for future use
                instance.cv.extracted_text = cv_text
                instance.cv.save()
            
            if not cv_text:
                print(f"⚠️ No CV text available for scoring {candidate.full_name}")
                return
            
            analysis_result = ai_service.analyze_cv_for_vacancy(instance.cv, instance.vacancy, cv_text)
            
            # Update candidate with AI scoring results
            candidate.ai_score_out_of_10 = analysis_result.get('overall_score', 0)
            candidate.ai_analysis = analysis_result.get('reasoning', '')
            candidate.ai_score_breakdown = analysis_result.get('score_breakdown', {})
            candidate.ai_scoring_date = timezone.now()
            candidate.latest_vacancy_scored = instance.vacancy
            
            # Save candidate
            candidate.save()
            
            print(f"✅ AI scoring completed for {candidate.full_name}: {candidate.ai_score_out_of_10}/10")
            
            # Automatically update shortlist for this vacancy
            try:
                update_shortlist_for_vacancy(instance.vacancy)
            except Exception as shortlist_error:
                print(f"⚠️ Shortlist update failed: {str(shortlist_error)}")
                # Don't fail the application creation if shortlist update fails
            
        except Exception as e:
            print(f"❌ AI scoring failed for application {instance.id}: {str(e)}")
            # Don't raise the exception to avoid breaking the Application creation


def update_shortlist_for_vacancy(vacancy):
    """Update shortlist for a vacancy after new application is added"""
    try:
        from vacancies.models import Shortlist
        
        # Get all applications for this vacancy with AI scores
        # Support both helper method and direct relation access
        qs = getattr(vacancy, 'get_applied_candidates', None)
        applications_base = qs() if callable(qs) else vacancy.applications.all()

        applications = applications_base.filter(
            cv__candidate__ai_score_out_of_10__isnull=False
        ).select_related('cv__candidate').order_by('-cv__candidate__ai_score_out_of_10')[:5]
        
        # Clear existing shortlist
        vacancy.shortlists.all().delete()
        
        # Create new shortlist entries
        for rank, application in enumerate(applications, 1):
            candidate = application.cv.candidate
            Shortlist.objects.create(
                vacancy=vacancy,
                candidate=candidate,
                application=application,
                rank=rank,
                ai_score=candidate.ai_score_out_of_10,
                generated_at=timezone.now()
            )
        
        print(f"✅ Shortlist updated for vacancy '{vacancy.title}': {applications.count()} candidates shortlisted")
        
    except Exception as e:
        print(f"❌ Failed to update shortlist for vacancy {vacancy.id}: {str(e)}")
        # Do not propagate to avoid breaking admin save/transactions
        return False

@receiver(post_save, sender=Application)
def create_or_update_candidate_vacancy_profile(sender, instance, created, **kwargs):
    """
    Create or update CandidateVacancyProfile when an application is created or updated
    """
    try:
        from .models import CandidateVacancyProfile
        
        if not instance.cv or not instance.cv.candidate:
            return
            
        candidate = instance.cv.candidate
        vacancy = instance.vacancy
        
        profile, created = CandidateVacancyProfile.objects.get_or_create(
            candidate=candidate,
            vacancy=vacancy,
            defaults={
                'application_status': instance.status,
                'application_date': instance.created_at,
                'cv_file_name': instance.cv.raw_file.name if instance.cv.raw_file else '',
                'ai_extracted_data': candidate.ai_extracted_data,
                'ai_score': candidate.ai_score_out_of_10,
                'ai_analysis': candidate.ai_analysis,
                'ai_score_breakdown': candidate.ai_score_breakdown,
                'ai_analysis_date': candidate.ai_scoring_date,
            }
        )
        
        if not created:
            # Update existing profile
            profile.application_status = instance.status
            profile.application_date = instance.created_at
            profile.cv_file_name = instance.cv.raw_file.name if instance.cv.raw_file else ''
            profile.ai_extracted_data = candidate.ai_extracted_data
            profile.ai_score = candidate.ai_score_out_of_10
            profile.ai_analysis = candidate.ai_analysis
            profile.ai_score_breakdown = candidate.ai_score_breakdown
            profile.ai_analysis_date = candidate.ai_scoring_date
            profile.save()
            
        print(f"✅ Candidate vacancy profile {'created' if created else 'updated'} for {candidate.full_name} - {vacancy.title}")
        
    except Exception as e:
        print(f"❌ Failed to create/update candidate vacancy profile: {str(e)}")
        # Do not propagate to avoid breaking admin save/transactions
        return False
