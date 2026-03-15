from django.db.models.signals import post_save
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import CV, Application, Candidate, CandidateVacancyProfile
from ai.services import AIService
from core.email_utils import email_subject
from vacancies.models import Shortlist


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


def _send_questionnaire_email_for_application(application):
    """Send questionnaire email to the candidate for this application. No-op if no email or if already sent for this vacancy. Returns True if email was sent, False otherwise."""
    if not application.cv or not application.cv.candidate:
        return False
    candidate = application.cv.candidate
    vacancy = application.vacancy
    if not candidate.email:
        print(f"⚠️ Candidate {candidate.full_name} has no email; questionnaire not sent")
        return False
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None)
    if not from_email:
        print("⚠️ DEFAULT_FROM_EMAIL / EMAIL_HOST_USER not set; questionnaire email not sent")
        return False
    # Lock profile row and set sent-at BEFORE sending to prevent duplicate sends from race (e.g. Application + Shortlist)
    try:
        with transaction.atomic():
            profile, created = CandidateVacancyProfile.objects.select_for_update().get_or_create(
                candidate=candidate,
                vacancy=vacancy,
                defaults={
                    'application_status': application.status,
                    'application_date': application.created_at,
                    'cv_file_name': application.cv.raw_file.name if application.cv.raw_file else '',
                }
            )
            if profile.questionnaire_email_sent_at:
                print(f"⏭️ Questionnaire already sent to {candidate.email} for '{vacancy.title}' — skipping")
                return False
            profile.questionnaire_email_sent_at = timezone.now()
            profile.save(update_fields=['questionnaire_email_sent_at'])
    except Exception as e:
        print(f"⚠️ Failed to lock/set questionnaire sent flag: {e}")
        return False
    try:
        questionnaire = vacancy.questionnaire_template or (
            "1) Why are you interested in this role?\n"
            "2) When can you start?\n"
            "3) What is your expected salary?\n"
        )
        safe_title = "".join(c if ord(c) < 128 else " " for c in (vacancy.title or "")).strip() or "Position"
        subject = email_subject(f"Pre-Interview Questions - {safe_title}")
        message = (
            f"Dear {candidate.full_name},\n\n"
            f"Thank you for applying for the position '{vacancy.title}'.\n"
            f"Please reply to this email with answers to the following questions:\n\n"
            f"{questionnaire}\n\n"
            f"Best regards,\nFahmy"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[candidate.email],
            fail_silently=False,
        )
        print(f"✅ Questionnaire email sent to {candidate.email} for '{vacancy.title}' (Subject: {subject!r}, From: {from_email!r})")
        return True
    except Exception as e:
        print(f"⚠️ Failed to send questionnaire email: {e}")
        return False


def _send_shortlist_questionnaire_email(shortlist_entry):
    """Send 'You have been shortlisted... please complete questionnaire' when candidate is added to shortlist. Skips if already sent for this vacancy."""
    vacancy = shortlist_entry.vacancy
    candidate = shortlist_entry.candidate
    if not candidate or not candidate.email:
        return
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None)
    if not from_email:
        print("⚠️ DEFAULT_FROM_EMAIL / EMAIL_HOST_USER not set; shortlist questionnaire not sent")
        return
    # Lock profile and set sent-at BEFORE sending to prevent duplicate sends (race with application path)
    try:
        with transaction.atomic():
            profile = CandidateVacancyProfile.objects.select_for_update().filter(
                candidate=candidate, vacancy=vacancy
            ).first()
            if not profile:
                profile, _ = CandidateVacancyProfile.objects.get_or_create(
                    candidate=candidate,
                    vacancy=vacancy,
                    defaults={'application_status': 'shortlisted'},
                )
            if profile.questionnaire_email_sent_at:
                print(f"⏭️ Questionnaire already sent to {candidate.email} for '{vacancy.title}' — skipping shortlist send")
                return
            profile.questionnaire_email_sent_at = timezone.now()
            profile.save(update_fields=['questionnaire_email_sent_at'])
    except Exception as e:
        print(f"⚠️ Failed to lock/set shortlist questionnaire flag: {e}")
        return
    try:
        questionnaire = vacancy.questionnaire_template or (
            "1) Why are you interested in this role?\n"
            "2) When can you start?\n"
            "3) What is your expected salary?\n"
        )
        safe_title = "".join(c if ord(c) < 128 else " " for c in (vacancy.title or "")).strip() or "Position"
        subject = email_subject(f"Pre-Interview Questions - {safe_title}")
        message = (
            f"Dear {candidate.full_name},\n\n"
            f"You have been shortlisted for the position '{vacancy.title}'.\n"
            f"Please complete this quick questionnaire by replying to this email:\n\n"
            f"{questionnaire}\n\n"
            f"Best regards,\nFahmy"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[candidate.email],
            fail_silently=False,
        )
        print(f"✅ Shortlist questionnaire sent to {candidate.email} for '{vacancy.title}' (Subject: {subject!r})")
    except Exception as e:
        print(f"⚠️ Failed to send shortlist questionnaire: {e}")


@receiver(post_save, sender=Shortlist)
def send_questionnaire_on_shortlist(sender, instance, created, **kwargs):
    """When a candidate is added to the shortlist, send them the questionnaire email."""
    if created:
        _send_shortlist_questionnaire_email(instance)


@receiver(post_save, sender=Application)
def score_candidate_on_application(sender, instance, created, **kwargs):
    """
    Automatically score candidate using AI and send the questionnaire
    when an Application is created.
    """
    if not created or not instance.cv or not instance.cv.candidate:
        return

    candidate = instance.cv.candidate
    vacancy = instance.vacancy

    # Always send questionnaire on new application (even if we skip or fail scoring)
    _send_questionnaire_email_for_application(instance)

    # Skip if candidate already has a score for this vacancy
    if candidate.ai_score_out_of_10 is not None and candidate.latest_vacancy_scored == vacancy:
        print(f"⏭️ Candidate {candidate.full_name} already scored for this vacancy, updating shortlist only...")
        try:
            update_shortlist_for_vacancy(vacancy)
        except Exception as shortlist_error:
            print(f"⚠️ Shortlist update failed: {str(shortlist_error)}")
        return

    try:
        print(f"🔄 Scoring candidate {candidate.full_name} for vacancy {vacancy.title}...")
        ai_service = AIService()

        cv_text = instance.cv.extracted_text
        if not cv_text and instance.cv.raw_file:
            cv_text = ai_service._extract_text_from_cv_file(instance.cv.raw_file)
            instance.cv.extracted_text = cv_text
            instance.cv.save()

        if not cv_text:
            print(f"⚠️ No CV text available for scoring {candidate.full_name}")
            try:
                update_shortlist_for_vacancy(vacancy)
            except Exception as shortlist_error:
                print(f"⚠️ Shortlist update failed: {str(shortlist_error)}")
            return

        analysis_result = ai_service.analyze_cv_for_vacancy(instance.cv, vacancy, cv_text)
        candidate.ai_score_out_of_10 = analysis_result.get('overall_score', 0)
        candidate.ai_analysis = analysis_result.get('reasoning', '')
        candidate.ai_score_breakdown = analysis_result.get('score_breakdown', {})
        candidate.ai_scoring_date = timezone.now()
        candidate.latest_vacancy_scored = vacancy
        candidate.save()
        print(f"✅ AI scoring completed for {candidate.full_name}: {candidate.ai_score_out_of_10}/10")

        try:
            update_shortlist_for_vacancy(vacancy)
        except Exception as shortlist_error:
            print(f"⚠️ Shortlist update failed: {str(shortlist_error)}")
    except Exception as e:
        print(f"❌ AI scoring failed for application {instance.id}: {str(e)}")


def rescore_profile_after_questionnaire(profile):
    """
    Recompute AI score (CV + questionnaire) for a CandidateVacancyProfile and update shortlist.
    Call this after saving a questionnaire response on the profile.
    """
    try:
        from .models import CandidateVacancyProfile
        from vacancies.models import Shortlist

        result = AIService().compute_final_score_with_questionnaire(profile)
        score = result.get('overall_score')
        if score is None:
            return
        profile.ai_score = float(score)
        profile.ai_analysis = result.get('reasoning') or profile.ai_analysis or ''
        profile.ai_score_breakdown = result.get('score_breakdown') or profile.ai_score_breakdown
        profile.ai_analysis_date = timezone.now()
        profile.save()
        update_shortlist_for_vacancy(profile.vacancy)
        print(f"✅ Re-scored profile for {profile.candidate.full_name} - {profile.vacancy.title}: {score}/10")
    except Exception as e:
        print(f"❌ Failed to rescore profile after questionnaire: {e}")


def update_shortlist_for_vacancy(vacancy):
    """
    Update shortlist for a vacancy from CandidateVacancyProfile.ai_score (CV + questionnaire when available).
    Top 5 by profile ai_score; falls back to candidate ai_score_out_of_10 when profile has no score.
    """
    try:
        from vacancies.models import Shortlist
        from .models import CandidateVacancyProfile, Application

        # Prefer per-vacancy profile score (includes questionnaire when replied)
        profiles = (
            CandidateVacancyProfile.objects.filter(vacancy=vacancy)
            .exclude(ai_score__isnull=True)
            .select_related('candidate')
            .order_by('-ai_score')[:5]
        )
        if not profiles.exists():
            # Fallback: use candidate-level AI score (CV-only) via applications
            applications_base = getattr(vacancy, 'get_applied_candidates', None)
            applications_base = applications_base() if callable(applications_base) else getattr(vacancy, 'applications', None)
            if applications_base is None:
                applications_base = Application.objects.filter(vacancy=vacancy)
            applications = applications_base.filter(
                cv__candidate__ai_score_out_of_10__isnull=False
            ).select_related('cv__candidate').order_by('-cv__candidate__ai_score_out_of_10')[:5]
            vacancy.shortlists.all().delete()
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
            print(f"✅ Shortlist updated for vacancy '{vacancy.title}' (CV-only): {applications.count()} candidates")
            return
        vacancy.shortlists.all().delete()
        for rank, profile in enumerate(profiles, 1):
            application = Application.objects.filter(
                vacancy=vacancy,
                cv__candidate=profile.candidate
            ).select_related('cv').first()
            if not application:
                continue
            Shortlist.objects.create(
                vacancy=vacancy,
                candidate=profile.candidate,
                application=application,
                rank=rank,
                ai_score=profile.ai_score,
                generated_at=timezone.now()
            )
        print(f"✅ Shortlist updated for vacancy '{vacancy.title}': {profiles.count()} candidates (profile score)")
    except Exception as e:
        print(f"❌ Failed to update shortlist for vacancy {vacancy.id}: {str(e)}")
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

        # Refresh shortlist so this candidate is included if they're in top 5 (profile didn't exist when score_candidate ran)
        try:
            update_shortlist_for_vacancy(vacancy)
        except Exception as shortlist_err:
            print(f"⚠️ Shortlist refresh after profile save: {shortlist_err}")

        print(f"✅ Candidate vacancy profile {'created' if created else 'updated'} for {candidate.full_name} - {vacancy.title}")

    except Exception as e:
        print(f"❌ Failed to create/update candidate vacancy profile: {str(e)}")
        # Do not propagate to avoid breaking admin save/transactions
        return False
