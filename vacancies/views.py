from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import F
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from .models import Vacancy
from .serializers import VacancySerializer
from candidates.models import Application

class VacancyViewSet(viewsets.ModelViewSet):
    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        vacancy = self.get_object()
        if not (request.user.is_staff or request.user == vacancy.created_by or request.user == vacancy.manager):
            return Response({"detail": "Not permitted to approve this vacancy."}, status=status.HTTP_403_FORBIDDEN)
        if vacancy.status not in ['awaiting_approval']:
            return Response({"detail": "Vacancy cannot be approved from current status."}, status=status.HTTP_400_BAD_REQUEST)
        vacancy.status = 'approved'
        vacancy.save(update_fields=['status'])
        return Response(VacancySerializer(vacancy).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        vacancy = self.get_object()
        if not (request.user.is_staff or request.user == vacancy.created_by or request.user == vacancy.manager):
            return Response({"detail": "Not permitted to reject this vacancy."}, status=status.HTTP_403_FORBIDDEN)
        if vacancy.status not in ['awaiting_approval']:
            return Response({"detail": "Vacancy cannot be rejected from current status."}, status=status.HTTP_400_BAD_REQUEST)
        vacancy.status = 'rejected'
        vacancy.save(update_fields=['status'])
        return Response(VacancySerializer(vacancy).data)

    @action(detail=True, methods=['post'])
    def shortlist_top5(self, request, pk=None):
        vacancy = self.get_object()
        if not (request.user.is_staff or request.user == vacancy.created_by or request.user == vacancy.manager):
            return Response({"detail": "Not permitted to shortlist for this vacancy."}, status=status.HTTP_403_FORBIDDEN)
        # Select top 5 by score_out_of_10, ignore nulls
        apps = (
            Application.objects
            .filter(vacancy=vacancy, score_out_of_10__isnull=False)
            .order_by(F('score_out_of_10').desc(nulls_last=True))[:5]
        )
        updated = 0
        for app in apps:
            if app.status != 'shortlisted':
                app.status = 'shortlisted'
                app.save(update_fields=['status'])
                updated += 1
        return Response({"shortlisted_count": updated})

    @action(detail=True, methods=['post'])
    def prepare_linkedin_posting(self, request, pk=None):
        """Generate LinkedIn job posting content for manual posting"""
        vacancy = self.get_object()
        if vacancy.status != 'approved':
            return Response({"detail": "Vacancy must be approved first"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate LinkedIn job posting content
        linkedin_content = self._generate_linkedin_content(vacancy)
        
        # Update status to collecting applications (simplified workflow)
        vacancy.status = 'collecting_applications'
        vacancy.save(update_fields=['status'])
        
        return Response({
            "linkedin_content": linkedin_content,
            "instructions": "Copy the content above and post it manually on LinkedIn. The vacancy is now collecting applications.",
            "vacancy_id": vacancy.id
        })

    @action(detail=True, methods=['post'])
    def mark_linkedin_posted(self, request, pk=None):
        """Mark vacancy as posted on LinkedIn and start 3-day collection period"""
        vacancy = self.get_object()
        if vacancy.status != 'collecting_applications':
            return Response({"detail": "Vacancy must be collecting applications first"}, status=status.HTTP_400_BAD_REQUEST)
        
        linkedin_url = request.data.get('linkedin_url', '')
        if not linkedin_url:
            return Response({"detail": "linkedin_url is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update vacancy with LinkedIn details and set collection period
        vacancy.linkedin_url = linkedin_url
        vacancy.linkedin_posted_at = timezone.now()
        vacancy.collection_ends_at = timezone.now() + timedelta(days=3)
        vacancy.save(update_fields=['linkedin_url', 'linkedin_posted_at', 'collection_ends_at'])
        
        return Response({
            "message": "Vacancy marked as posted on LinkedIn",
            "collection_ends_at": vacancy.collection_ends_at,
            "linkedin_url": vacancy.linkedin_url
        })

    @action(detail=True, methods=['post'])
    def start_application_collection(self, request, pk=None):
        """Start collecting applications (call this after 3 days)"""
        vacancy = self.get_object()
        if vacancy.status != 'collecting_applications':
            return Response({"detail": "Vacancy must be in collecting applications status"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Vacancy is already collecting applications, just confirm
        return Response({
            "message": "Application collection is already active",
            "vacancy_id": vacancy.id,
            "status": vacancy.status
        })

    def _generate_linkedin_content(self, vacancy):
        """Generate LinkedIn job posting content"""
        content = f"""🚀 We're Hiring: {vacancy.title}

📍 Department: {vacancy.department}
🏢 Company: Bit68

📋 Job Description:
We are looking for a talented {vacancy.title} to join our {vacancy.department} team.

🔍 Key Requirements:
• Relevant experience in {vacancy.keywords.replace(',', ', ')}
• Strong problem-solving skills
• Excellent communication skills"""

        if vacancy.require_egyptian:
            content += "\n• Egyptian nationality preferred"
        
        if vacancy.require_relevant_university:
            content += "\n• Relevant university degree"
        
        if vacancy.require_relevant_major:
            content += "\n• Relevant major/field of study"
        
        if vacancy.require_dob_in_cv:
            content += "\n• Date of birth must be included in CV"

        content += f"""

💼 What We Offer:
• Competitive salary
• Professional development opportunities
• Collaborative work environment
• Growth opportunities

📧 How to Apply:
Send your CV to: {getattr(settings, 'APPLICATION_EMAIL', settings.DEFAULT_FROM_EMAIL)}
Subject: Application for {vacancy.title}

Include in your application:
• Updated CV with relevant experience
• Cover letter highlighting your qualifications
• Expected salary range

#hiring #jobs #careers #bit68 #{vacancy.department.lower()} #{vacancy.keywords.replace(',', ' #').replace(' ', '')}

⏰ Application deadline: 3 days from posting

Good luck! 🍀"""

        return content


from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View


@method_decorator([staff_member_required, csrf_exempt], name='dispatch')
class GenerateShortlistView(View):
    """Admin view to generate shortlist for a vacancy"""
    
    def post(self, request, vacancy_id):
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id)
            count = vacancy.generate_shortlist()
            
            return JsonResponse({
                'success': True,
                'count': count,
                'message': f'Shortlist generated with {count} candidates'
            })
        except Vacancy.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Vacancy not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@method_decorator([staff_member_required, csrf_exempt], name='dispatch')
class ClearShortlistView(View):
    """Admin view to clear shortlist for a vacancy"""
    
    def post(self, request, vacancy_id):
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id)
            count = vacancy.shortlists.count()
            vacancy.shortlists.all().delete()
            
            return JsonResponse({
                'success': True,
                'count': count,
                'message': f'Shortlist cleared ({count} candidates removed)'
            })
        except Vacancy.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Vacancy not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
