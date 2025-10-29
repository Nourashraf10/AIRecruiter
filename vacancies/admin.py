from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Vacancy, Shortlist
from django.contrib import messages
from interviews.services import ZohoCalendarService, InterviewSchedulingService
from interviews.models import InterviewSlot, Interview
from django.utils import timezone
from datetime import timedelta
import os
import certifi
from comms.daily_automation_service import DailyAutomationService

# Test CalDAV credentials for admin actions (for easing testing)
TEST_CALDAV_USERNAME = "noureldin.ashraf@bit68.com"
TEST_CALDAV_PASSWORD = "Dvg2e2AG8dXM"
TEST_CALDAV_URL = "https://calendar.zoho.com/caldav/bca62345ad5e4b609586bf2d53fc9cc7/events/"

@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "department", "manager", "status", "applications_count", "shortlist_count", "created_at")
    list_filter = ("status", "department")
    search_fields = ("title", "department", "keywords", "manager__email")
    readonly_fields = ("applications_list", "shortlist_list", "shortlist_actions")
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'department', 'manager', 'status', 'created_by')
        }),
        ('Requirements', {
            'fields': ('keywords', 'require_dob_in_cv', 'require_egyptian', 'require_relevant_university', 'require_relevant_major')
        }),
        ('LinkedIn Integration', {
            'fields': ('linkedin_url', 'linkedin_posted_at', 'collection_ends_at'),
            'classes': ('collapse',)
        }),
        ('Questionnaire', {
            'fields': ('questionnaire_template',),
            'classes': ('collapse',)
        }),
        ('Applications & Shortlist', {
            'fields': ('applications_list', 'shortlist_list', 'shortlist_actions'),
            'classes': ('wide',)
        }),
        ('Metadata', {
            'fields': ('meta',),
            'classes': ('collapse',)
        }),
    )

    actions = [
        "check_caldav_availability",
        "send_caldav_offer_to_first_shortlisted",
        "schedule_first_shortlisted_from_caldav",
        "send_questionnaire_to_next_shortlisted",
    ]

    def _get_first_shortlisted_candidate(self, vacancy: Vacancy):
        shortlist = vacancy.shortlists.order_by("rank").first()
        return shortlist.candidate if shortlist else None

    @admin.action(description="Check CalDAV free slots (next 7 days)")
    def check_caldav_availability(self, request, queryset):
        # Ensure SMTP can verify certificates
        os.environ["SSL_CERT_FILE"] = certifi.where()
        count_checked = 0
        for vacancy in queryset:
            manager_email = vacancy.manager.email if vacancy.manager else TEST_CALDAV_USERNAME
            start_date = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
            cal = ZohoCalendarService(manager_email=manager_email)
            cal.configure_basic_auth_caldav(TEST_CALDAV_URL, TEST_CALDAV_USERNAME, TEST_CALDAV_PASSWORD)
            slots = cal.get_available_slots(start_date, end_date, 60, manager_email=manager_email)
            messages.info(request, f"Vacancy '{vacancy.title}': found {len(slots)} free slots")
            count_checked += 1
        if count_checked == 0:
            messages.warning(request, "No vacancies selected.")

    @admin.action(description="Send CalDAV slot offer to manager + first shortlisted")
    def send_caldav_offer_to_first_shortlisted(self, request, queryset):
        os.environ["SSL_CERT_FILE"] = certifi.where()
        notif = InterviewSchedulingService()
        sent = 0
        for vacancy in queryset:
            candidate = self._get_first_shortlisted_candidate(vacancy)
            if not candidate:
                messages.warning(request, f"Vacancy '{vacancy.title}': no shortlisted candidates")
                continue
            manager_email = vacancy.manager.email if vacancy.manager else TEST_CALDAV_USERNAME
            start_date = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
            cal = ZohoCalendarService(manager_email=manager_email)
            cal.configure_basic_auth_caldav(TEST_CALDAV_URL, TEST_CALDAV_USERNAME, TEST_CALDAV_PASSWORD)
            slots = cal.get_available_slots(start_date, end_date, 60, manager_email=manager_email)
            if not slots:
                messages.warning(request, f"Vacancy '{vacancy.title}': no free slots found")
                continue
            first_slot = slots[0]
            result = notif.send_free_slot_offer(
                manager_email=manager_email,
                candidate_email=candidate.email,
                vacancy_title=vacancy.title,
                slot_start=first_slot["start_time"],
                duration_minutes=first_slot.get("duration_minutes", 60),
            )
            if result.get("success"):
                sent += 1
                messages.success(request, f"Offer sent for '{vacancy.title}' to {candidate.email}")
            else:
                messages.error(request, f"Failed to send offer for '{vacancy.title}': {result.get('error')}")
        if sent == 0 and queryset.count() > 0:
            messages.warning(request, "No offers sent.")

    @admin.action(description="Schedule first shortlisted from CalDAV and notify")
    def schedule_first_shortlisted_from_caldav(self, request, queryset):
        os.environ["SSL_CERT_FILE"] = certifi.where()
        scheduled = 0
        for vacancy in queryset:
            candidate = self._get_first_shortlisted_candidate(vacancy)
            if not candidate:
                messages.warning(request, f"Vacancy '{vacancy.title}': no shortlisted candidates")
                continue
            manager = vacancy.manager
            manager_email = manager.email if manager else TEST_CALDAV_USERNAME
            start_date = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
            cal = ZohoCalendarService(manager_email=manager_email)
            cal.configure_basic_auth_caldav(TEST_CALDAV_URL, TEST_CALDAV_USERNAME, TEST_CALDAV_PASSWORD)
            slots = cal.get_available_slots(start_date, end_date, 60, manager_email=manager_email)
            if not slots:
                messages.warning(request, f"Vacancy '{vacancy.title}': no free slots found")
                continue
            s = slots[0]
            interview_slot = InterviewSlot.objects.create(
                vacancy=vacancy,
                manager=manager,
                start_time=s["start_time"],
                end_time=s["end_time"],
                is_available=False,
            )
            interview = Interview.objects.create(
                vacancy=vacancy,
                candidate=candidate,
                manager=manager,
                interview_slot=interview_slot,
                scheduled_at=s["start_time"],
                duration_minutes=s.get("duration_minutes", 60),
                status='scheduled',
            )
            # notify both
            result = InterviewSchedulingService().send_interview_notifications([interview])
            if result.get('success'):
                scheduled += 1
                messages.success(request, f"Interview scheduled and notifications sent for '{vacancy.title}'")
            else:
                messages.warning(request, f"Interview scheduled for '{vacancy.title}' but notifications failed: {result.get('error')}")
        if scheduled == 0 and queryset.count() > 0:
            messages.warning(request, "No interviews scheduled.")

    @admin.action(description="Send questionnaire to next un-scheduled shortlisted")
    def send_questionnaire_to_next_shortlisted(self, request, queryset):
        sent = 0
        svc = DailyAutomationService()
        for vacancy in queryset:
            candidate = svc._pick_next_shortlisted_candidate(vacancy)
            if not candidate:
                messages.warning(request, f"Vacancy '{vacancy.title}': no eligible shortlisted candidate")
                continue
            try:
                svc._send_questionnaire_email(vacancy, candidate)
                sent += 1
                messages.success(request, f"Questionnaire emailed to {candidate.email} for '{vacancy.title}'")
            except Exception as e:
                messages.error(request, f"Failed to send questionnaire for '{vacancy.title}': {str(e)}")
        if sent == 0 and queryset.count() > 0:
            messages.warning(request, "No questionnaires sent.")
    
    def applications_count(self, obj):
        """Show count of applications for this vacancy"""
        count = obj.get_applied_candidates().count()
        if count > 0:
            url = reverse('admin:candidates_application_changelist') + f'?vacancy__id__exact={obj.id}'
            return format_html('<a href="{}">{} applications</a>', url, count)
        return "0 applications"
    applications_count.short_description = "Applications"
    
    def shortlist_count(self, obj):
        """Show count of shortlisted candidates"""
        count = obj.shortlists.count()
        if count > 0:
            url = reverse('admin:vacancies_shortlist_changelist') + f'?vacancy__id__exact={obj.id}'
            return format_html('<a href="{}">{} shortlisted</a>', url, count)
        return "No shortlist"
    shortlist_count.short_description = "Shortlist"
    
    def applications_list(self, obj):
        """Display list of all applications for this vacancy"""
        applications = obj.get_applied_candidates()
        if not applications.exists():
            return "No applications yet"
        
        html = "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<tr style='background-color: #f8f9fa;'>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Candidate</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Email</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>AI Score</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Status</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Applied</th>"
        html += "</tr>"
        
        for app in applications:
            candidate = app.cv.candidate if app.cv and app.cv.candidate else None
            if candidate:
                score = candidate.ai_score_out_of_10 or 0
                score_color = "green" if score >= 7 else "orange" if score >= 5 else "red"
                html += f"<tr>"
                html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{candidate.full_name}</td>"
                html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{candidate.email}</td>"
                html += f"<td style='border: 1px solid #ddd; padding: 8px; color: {score_color}; font-weight: bold;'>{score}/10</td>"
                html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{app.status}</td>"
                html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{app.created_at.strftime('%Y-%m-%d %H:%M')}</td>"
                html += f"</tr>"
        
        html += "</table>"
        return mark_safe(html)
    applications_list.short_description = "All Applications"
    
    def shortlist_list(self, obj):
        """Display the current shortlist"""
        shortlists = obj.get_shortlisted_candidates()
        if not shortlists.exists():
            return "No shortlist generated yet. Click 'Generate Shortlist' below."
        
        html = "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<tr style='background-color: #e3f2fd;'>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Rank</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Candidate</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Email</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>AI Score</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Generated</th>"
        html += "</tr>"
        
        for shortlist in shortlists:
            candidate = shortlist.candidate
            score_color = "green" if shortlist.ai_score >= 7 else "orange" if shortlist.ai_score >= 5 else "red"
            html += f"<tr>"
            html += f"<td style='border: 1px solid #ddd; padding: 8px; font-weight: bold;'>#{shortlist.rank}</td>"
            html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{candidate.full_name}</td>"
            html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{candidate.email}</td>"
            html += f"<td style='border: 1px solid #ddd; padding: 8px; color: {score_color}; font-weight: bold;'>{shortlist.ai_score}/10</td>"
            html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{shortlist.generated_at.strftime('%Y-%m-%d %H:%M')}</td>"
            html += f"</tr>"
        
        html += "</table>"
        return mark_safe(html)
    shortlist_list.short_description = "Top 5 Shortlist"
    
    def shortlist_actions(self, obj):
        """Display action buttons for shortlist management"""
        applications_count = obj.get_applied_candidates().count()
        shortlist_count = obj.shortlists.count()
        
        html = "<div style='margin: 10px 0;'>"
        
        if applications_count > 0:
            html += f"<a href='#' onclick='generateShortlist({obj.id})' class='button' style='background: #28a745; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-right: 10px;'>Generate Shortlist</a>"
        else:
            html += "<span style='color: #6c757d;'>No applications to shortlist</span>"
        
        if shortlist_count > 0:
            html += f"<a href='#' onclick='clearShortlist({obj.id})' class='button' style='background: #dc3545; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;'>Clear Shortlist</a>"
        
        html += "</div>"
        
        # Add JavaScript for the actions
        html += """
        <script>
        function generateShortlist(vacancyId) {
            if (confirm('Generate shortlist of top 5 candidates for this vacancy?')) {
                fetch(`/admin/vacancies/vacancy/${vacancyId}/generate-shortlist/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/json',
                    },
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(`Shortlist generated successfully! ${data.count} candidates shortlisted.`);
                        location.reload();
                    } else {
                        alert('Error generating shortlist: ' + data.error);
                    }
                })
                .catch(error => {
                    alert('Error: ' + error);
                });
            }
        }
        
        function clearShortlist(vacancyId) {
            if (confirm('Clear the current shortlist for this vacancy?')) {
                fetch(`/admin/vacancies/vacancy/${vacancyId}/clear-shortlist/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/json',
                    },
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Shortlist cleared successfully!');
                        location.reload();
                    } else {
                        alert('Error clearing shortlist: ' + data.error);
                    }
                })
                .catch(error => {
                    alert('Error: ' + error);
                });
            }
        }
        </script>
        """
        
        return mark_safe(html)
    shortlist_actions.short_description = "Shortlist Actions"
    
    def interview_scheduling(self, obj):
        """Display interview scheduling interface"""
        shortlist_count = obj.shortlists.count()
        
        if shortlist_count == 0:
            return "No shortlist available. Generate shortlist first."
        
        # Check if manager has calendar integration
        from interviews.models import CalendarIntegration
        from interviews.zoho_oauth_service import ZohoOAuthService
        
        try:
            calendar_integration = CalendarIntegration.objects.get(manager=obj.manager, is_active=True)
            calendar_available = True
            
            # Check OAuth token status
            oauth_service = ZohoOAuthService()
            has_valid_token = oauth_service.get_valid_access_token(obj.manager.email)
            token_status = "valid" if has_valid_token else "invalid"
            
        except CalendarIntegration.DoesNotExist:
            calendar_available = False
            token_status = "none"
        
        html = "<div style='margin: 10px 0;'>"
        
        if calendar_available:
            # Determine status color and message
            if token_status == "valid":
                status_color = "#2e7d32"
                status_bg = "#e8f5e8"
                status_icon = "✅"
                status_text = "OAuth Active & Token Valid"
            elif token_status == "invalid":
                status_color = "#856404"
                status_bg = "#fff3cd"
                status_icon = "⚠️"
                status_text = "OAuth Active but Token Invalid"
            else:
                status_color = "#721c24"
                status_bg = "#f8d7da"
                status_icon = "❌"
                status_text = "OAuth Setup Required"
            
            html += f"""
            <div style='background: {status_bg}; padding: 15px; border-radius: 5px; margin-bottom: 15px; border: 1px solid {status_color};'>
                <h4 style='margin: 0 0 10px 0; color: {status_color};'>{status_icon} {status_text}</h4>
                <p style='margin: 0;'>Manager: {obj.manager.email}</p>
                <p style='margin: 0;'>Calendar ID: {calendar_integration.calendar_id[:20]}...</p>
                <p style='margin: 5px 0 0 0;'>
                    <a href='/admin/interviews/calendarintegration/{calendar_integration.id}/change/' style='color: {status_color}; text-decoration: none; font-weight: bold;'>
                        → Manage Calendar Integration
                    </a>
                </p>
            </div>
            """
            
            html += f"""
            <div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px;'>
                <h4 style='margin: 0 0 15px 0;'>Schedule Interviews for {shortlist_count} Shortlisted Candidates</h4>
                
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;'>
                    <div>
                        <label style='display: block; margin-bottom: 5px; font-weight: bold;'>Start Date:</label>
                        <input type='date' id='start_date_{obj.id}' style='width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>
                    </div>
                    <div>
                        <label style='display: block; margin-bottom: 5px; font-weight: bold;'>End Date:</label>
                        <input type='date' id='end_date_{obj.id}' style='width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>
                    </div>
                </div>
                
                <div style='margin-bottom: 15px;'>
                    <label style='display: block; margin-bottom: 5px; font-weight: bold;'>Interview Duration (minutes):</label>
                    <select id='duration_{obj.id}' style='width: 200px; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>
                        <option value='30'>30 minutes</option>
                        <option value='60' selected>60 minutes</option>
                        <option value='90'>90 minutes</option>
                        <option value='120'>120 minutes</option>
                    </select>
                </div>
                
                <div style='display: flex; gap: 10px;'>
                    <button onclick='checkAvailability({obj.id})' style='background: #17a2b8; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;'>
                        Check Availability
                    </button>
                    <button onclick='scheduleInterviews({obj.id})' style='background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;'>
                        Schedule All Interviews
                    </button>
                    <button onclick='sendNotifications({obj.id})' style='background: #ffc107; color: black; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;'>
                        Send Notifications
                    </button>
                </div>
                
                <div id='availability_result_{obj.id}' style='margin-top: 15px;'></div>
            </div>
            """
        else:
            html += f"""
            <div style='background: #fff3cd; padding: 15px; border-radius: 5px; border: 1px solid #ffeaa7;'>
                <h4 style='margin: 0 0 10px 0; color: #856404;'>⚠️ Calendar Integration Required</h4>
                <p style='margin: 0 0 10px 0;'>Manager {obj.manager.email} needs calendar integration to schedule interviews.</p>
                <div style='display: flex; gap: 10px; margin-top: 10px;'>
                    <a href='/admin/interviews/calendarintegration/add/' style='background: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;'>
                        Set Up Calendar Integration
                    </a>
                    <button onclick='testOAuthSetup("{obj.manager.email}")' style='background: #28a745; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;'>
                        Test OAuth Setup
                    </button>
                </div>
            </div>
            """
        
        html += "</div>"
        
        # Add JavaScript for interview scheduling
        html += f"""
        <script>
        function testOAuthSetup(managerEmail) {{
            if (confirm(`Test OAuth setup for ${{managerEmail}}?`)) {{
                fetch('/api/admin/oauth/setup/', {{
                    method: 'POST',
                    headers: {{
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{'manager_email': managerEmail}})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.requires_authorization) {{
                        alert(`OAuth setup initiated!\\n\\nPlease visit this URL to authorize:\\n${{data.authorization_url}}`);
                        window.open(data.authorization_url, '_blank');
                    }} else if (data.success) {{
                        alert(`OAuth setup completed: ${{data.message}}`);
                        location.reload();
                    }} else {{
                        alert(`OAuth setup failed: ${{data.error}}`);
                    }}
                }})
                .catch(error => {{
                    alert(`Error: ${{error}}`);
                }});
            }}
        }}
        function checkAvailability(vacancyId) {{
            const startDate = document.getElementById('start_date_' + vacancyId).value;
            const endDate = document.getElementById('end_date_' + vacancyId).value;
            const duration = document.getElementById('duration_' + vacancyId).value;
            
            if (!startDate || !endDate) {{
                alert('Please select both start and end dates');
                return;
            }}
            
            const resultDiv = document.getElementById('availability_result_' + vacancyId);
            resultDiv.innerHTML = '<p>Checking availability...</p>';
            
            fetch(`/admin/vacancies/vacancy/${{vacancyId}}/check-availability/?start_date=${{startDate}}&end_date=${{endDate}}&duration_minutes=${{duration}}`, {{
                method: 'GET',
                headers: {{
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                }},
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    resultDiv.innerHTML = `
                        <div style='background: #d4edda; padding: 10px; border-radius: 4px; border: 1px solid #c3e6cb;'>
                            <strong>Found ${{data.count}} available slots</strong><br>
                            <small>Manager: ${{data.manager}}</small>
                        </div>
                    `;
                }} else {{
                    resultDiv.innerHTML = `
                        <div style='background: #f8d7da; padding: 10px; border-radius: 4px; border: 1px solid #f5c6cb;'>
                            <strong>Error:</strong> ${{data.error}}
                        </div>
                    `;
                }}
            }})
            .catch(error => {{
                resultDiv.innerHTML = `
                    <div style='background: #f8d7da; padding: 10px; border-radius: 4px; border: 1px solid #f5c6cb;'>
                        <strong>Error:</strong> ${{error}}
                    </div>
                `;
            }});
        }}
        
        function scheduleInterviews(vacancyId) {{
            const startDate = document.getElementById('start_date_' + vacancyId).value;
            const endDate = document.getElementById('end_date_' + vacancyId).value;
            const duration = document.getElementById('duration_' + vacancyId).value;
            
            if (!startDate || !endDate) {{
                alert('Please select both start and end dates');
                return;
            }}
            
            if (confirm('Schedule interviews for all shortlisted candidates?')) {{
                const resultDiv = document.getElementById('availability_result_' + vacancyId);
                resultDiv.innerHTML = '<p>Scheduling interviews...</p>';
                
                const formData = new FormData();
                formData.append('start_date', startDate);
                formData.append('end_date', endDate);
                formData.append('duration_minutes', duration);
                
                fetch(`/admin/vacancies/vacancy/${{vacancyId}}/schedule-interviews/`, {{
                    method: 'POST',
                    headers: {{
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    }},
                    body: formData
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        resultDiv.innerHTML = `
                            <div style='background: #d4edda; padding: 10px; border-radius: 4px; border: 1px solid #c3e6cb;'>
                                <strong>Success!</strong> ${{data.message}}<br>
                                <small>Notifications sent: ${{data.notifications_sent}}</small>
                            </div>
                        `;
                        setTimeout(() => location.reload(), 2000);
                    }} else {{
                        resultDiv.innerHTML = `
                            <div style='background: #f8d7da; padding: 10px; border-radius: 4px; border: 1px solid #f5c6cb;'>
                                <strong>Error:</strong> ${{data.error}}
                            </div>
                        `;
                    }}
                }})
                .catch(error => {{
                    resultDiv.innerHTML = `
                        <div style='background: #f8d7da; padding: 10px; border-radius: 4px; border: 1px solid #f5c6cb;'>
                            <strong>Error:</strong> ${{error}}
                        </div>
                    `;
                }});
            }}
        }}
        
        function sendNotifications(vacancyId) {{
            if (confirm('Send interview notifications to all scheduled candidates and manager?')) {{
                const resultDiv = document.getElementById('availability_result_' + vacancyId);
                resultDiv.innerHTML = '<p>Sending notifications...</p>';
                
                fetch(`/admin/vacancies/vacancy/${{vacancyId}}/send-notifications/`, {{
                    method: 'POST',
                    headers: {{
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    }},
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        resultDiv.innerHTML = `
                            <div style='background: #d4edda; padding: 10px; border-radius: 4px; border: 1px solid #c3e6cb;'>
                                <strong>Success!</strong> ${{data.message}}
                            </div>
                        `;
                    }} else {{
                        resultDiv.innerHTML = `
                            <div style='background: #f8d7da; padding: 10px; border-radius: 4px; border: 1px solid #f5c6cb;'>
                                <strong>Error:</strong> ${{data.error}}
                            </div>
                        `;
                    }}
                }})
                .catch(error => {{
                    resultDiv.innerHTML = `
                        <div style='background: #f8d7da; padding: 10px; border-radius: 4px; border: 1px solid #f5c6cb;'>
                            <strong>Error:</strong> ${{error}}
                        </div>
                    `;
                }});
            }}
        }}
        </script>
        """
        
        return mark_safe(html)
    interview_scheduling.short_description = "Interview Scheduling"
    
    def scheduled_interviews(self, obj):
        """Display scheduled interviews for this vacancy"""
        try:
            from interviews.models import Interview
            
            interviews = Interview.objects.filter(vacancy=obj).order_by('scheduled_at')
            
            if not interviews.exists():
                return "No interviews scheduled yet."
        except Exception as e:
            return f"Error loading interviews: {str(e)}"
        
        html = "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<tr style='background-color: #e3f2fd;'>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Candidate</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Date & Time</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Status</th>"
        html += "<th style='border: 1px solid #ddd; padding: 8px;'>Notifications</th>"
        html += "</tr>"
        
        for interview in interviews:
            status_color = "green" if interview.status == "scheduled" else "orange" if interview.status == "completed" else "red"
            html += f"<tr>"
            html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{interview.candidate.full_name}</td>"
            html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{interview.scheduled_at.strftime('%Y-%m-%d %H:%M')}</td>"
            html += f"<td style='border: 1px solid #ddd; padding: 8px; color: {status_color}; font-weight: bold;'>{interview.status}</td>"
            
            if interview.manager_notified and interview.candidate_notified:
                html += f"<td style='border: 1px solid #ddd; padding: 8px; color: green;'>✓ Both notified</td>"
            elif interview.manager_notified or interview.candidate_notified:
                html += f"<td style='border: 1px solid #ddd; padding: 8px; color: orange;'>⚠ Partial</td>"
            else:
                html += f"<td style='border: 1px solid #ddd; padding: 8px; color: red;'>✗ Not notified</td>"
            
            html += f"</tr>"
        
        html += "</table>"
        return mark_safe(html)
    scheduled_interviews.short_description = "Scheduled Interviews"


@admin.register(Shortlist)
class ShortlistAdmin(admin.ModelAdmin):
    list_display = ("vacancy", "rank", "candidate", "ai_score", "generated_at")
    list_filter = ("vacancy", "generated_at")
    search_fields = ("vacancy__title", "candidate__full_name", "candidate__email")
    readonly_fields = ("generated_at",)
    ordering = ("vacancy", "rank")
    
    fieldsets = (
        ('Shortlist Information', {
            'fields': ('vacancy', 'candidate', 'application', 'rank', 'ai_score')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('generated_at',),
            'classes': ('collapse',)
        }),
    )

