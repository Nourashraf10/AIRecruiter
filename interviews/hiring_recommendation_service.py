"""
Service for generating AI-powered hiring recommendations
"""
import os
import json
import requests
from typing import Dict, Any
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from candidates.models import CandidateVacancyProfile


class HiringRecommendationService:
    """
    Service to generate AI-powered hiring recommendations based on candidate profile
    """
    
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            print("⚠️  OPENAI_API_KEY not found. Hiring recommendation will not work.")
    
    def generate_hiring_recommendation(self, profile: CandidateVacancyProfile) -> Dict[str, Any]:
        """
        Generate hiring recommendation using OpenAI based on candidate profile
        """
        if not self.api_key:
            return {
                'recommendation': 'Unable to generate recommendation - OpenAI API key not configured',
                'reasoning': 'Please configure OPENAI_API_KEY in environment variables',
                'confidence': 'low'
            }
        
        try:
            # Prepare candidate information
            candidate_info = self._prepare_candidate_data(profile)
            
            # Create prompt for OpenAI
            prompt = self._create_recommendation_prompt(profile, candidate_info)
            
            # Call OpenAI API
            response = self._call_openai_api(prompt)
            
            # Parse response
            recommendation = self._parse_recommendation_response(response)
            
            return recommendation
            
        except Exception as e:
            print(f"❌ Error generating hiring recommendation: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'recommendation': 'Error generating recommendation',
                'reasoning': f'An error occurred: {str(e)}',
                'confidence': 'low'
            }
    
    def _prepare_candidate_data(self, profile: CandidateVacancyProfile) -> Dict[str, Any]:
        """
        Prepare candidate data for AI analysis
        """
        candidate = profile.candidate
        vacancy = profile.vacancy
        
        data = {
            'candidate_name': candidate.full_name,
            'candidate_email': candidate.email,
            'vacancy_title': vacancy.title,
            'vacancy_department': vacancy.department,
            'vacancy_keywords': vacancy.keywords,
            'vacancy_requirements': {
                'require_dob_in_cv': vacancy.require_dob_in_cv,
                'require_egyptian': vacancy.require_egyptian,
                'require_relevant_university': vacancy.require_relevant_university,
                'require_relevant_major': vacancy.require_relevant_major,
            }
        }
        
        # AI Analysis
        if profile.ai_score:
            data['ai_score'] = float(profile.ai_score)
        if profile.ai_analysis:
            data['ai_analysis'] = profile.ai_analysis
        if profile.ai_extracted_data:
            data['ai_extracted_data'] = profile.ai_extracted_data
        if profile.ai_score_breakdown:
            data['ai_score_breakdown'] = profile.ai_score_breakdown
        
        # Manager Feedback
        if profile.manager_feedback:
            data['manager_feedback'] = profile.manager_feedback
        if profile.manager_rating:
            data['manager_rating'] = profile.manager_rating
            rating_labels = {1: 'Poor', 2: 'Fair', 3: 'Good', 4: 'Very Good', 5: 'Excellent'}
            data['manager_rating_label'] = rating_labels.get(profile.manager_rating, 'Unknown')
        if profile.manager_recommendation is not None:
            data['manager_recommendation'] = 'Yes' if profile.manager_recommendation else 'No'
        
        # Questionnaire Response
        if profile.questionnaire_response:
            data['questionnaire_response'] = profile.questionnaire_response
        
        # Interview Information
        if profile.interview_date:
            data['interview_date'] = profile.interview_date.isoformat()
        if profile.interview_duration:
            data['interview_duration_minutes'] = profile.interview_duration
        
        return data
    
    def _create_recommendation_prompt(self, profile: CandidateVacancyProfile, candidate_info: Dict[str, Any]) -> str:
        """
        Create prompt for OpenAI to generate hiring recommendation
        """
        vacancy = profile.vacancy
        
        prompt = f"""You are an expert HR consultant analyzing a candidate for a job position. Based on all available information, provide a hiring recommendation.

VACANCY DETAILS:
- Title: {vacancy.title}
- Department: {vacancy.department}
- Keywords/Requirements: {vacancy.keywords}
- Requirements:
  * Date of Birth in CV: {'Required' if vacancy.require_dob_in_cv else 'Not Required'}
  * Egyptian Nationality: {'Required' if vacancy.require_egyptian else 'Not Required'}
  * Relevant University: {'Required' if vacancy.require_relevant_university else 'Not Required'}
  * Relevant Major: {'Required' if vacancy.require_relevant_major else 'Not Required'}

CANDIDATE INFORMATION:
- Name: {candidate_info.get('candidate_name', 'N/A')}
"""
        
        # Add AI Analysis
        if candidate_info.get('ai_score'):
            prompt += f"- AI Score: {candidate_info['ai_score']}/10\n"
        if candidate_info.get('ai_analysis'):
            prompt += f"- AI Analysis: {candidate_info['ai_analysis']}\n"
        if candidate_info.get('ai_extracted_data'):
            prompt += f"- Extracted Data: {json.dumps(candidate_info['ai_extracted_data'], indent=2)}\n"
        
        # Add Manager Feedback
        if candidate_info.get('manager_feedback'):
            prompt += f"\nMANAGER FEEDBACK:\n{candidate_info['manager_feedback']}\n"
        if candidate_info.get('manager_rating'):
            prompt += f"- Manager Rating: {candidate_info.get('manager_rating_label', 'N/A')} ({candidate_info['manager_rating']}/5)\n"
        if candidate_info.get('manager_recommendation'):
            prompt += f"- Manager Recommendation: {candidate_info['manager_recommendation']}\n"
        
        # Add Questionnaire Response
        if candidate_info.get('questionnaire_response'):
            prompt += f"\nQUESTIONNAIRE RESPONSE:\n{candidate_info['questionnaire_response']}\n"
        
        prompt += """
Please provide a comprehensive hiring recommendation in the following JSON format:
{
    "recommendation": "HIRE" or "DO NOT HIRE" or "CONSIDER",
    "confidence": "high" or "medium" or "low",
    "summary": "Brief 2-3 sentence summary of your recommendation",
    "strengths": ["strength1", "strength2", ...],
    "concerns": ["concern1", "concern2", ...],
    "reasoning": "Detailed explanation (3-5 sentences) of why you recommend this action based on the vacancy requirements, AI analysis, manager feedback, and questionnaire response",
    "key_factors": ["factor1", "factor2", ...]
}

Focus on:
1. How well the candidate matches the vacancy requirements and keywords
2. The AI score and analysis quality
3. Manager feedback and rating
4. Questionnaire responses showing candidate's fit
5. Overall alignment with the role

Respond with ONLY valid JSON, no additional text.
"""
        
        return prompt
    
    def _call_openai_api(self, prompt: str) -> str:
        """
        Call OpenAI API to generate recommendation
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'gpt-4',  # Using GPT-4 for better analysis
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are an expert HR consultant. Always respond with valid JSON only, no additional text or markdown formatting.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 1500,
                'temperature': 0.3  # Lower temperature for more consistent recommendations
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                print(f"❌ OpenAI API error: {response.status_code} - {response.text}")
                raise Exception(f"OpenAI API returned {response.status_code}")
                
        except Exception as e:
            print(f"❌ OpenAI API call failed: {str(e)}")
            raise
    
    def _get_rating_display(self, rating: int) -> str:
        """
        Get human-readable rating label
        """
        rating_labels = {
            1: 'Poor',
            2: 'Fair',
            3: 'Good',
            4: 'Very Good',
            5: 'Excellent'
        }
        return rating_labels.get(rating, f'{rating}/5')
    
    def _parse_recommendation_response(self, response: str) -> Dict[str, Any]:
        """
        Parse OpenAI response into structured recommendation
        """
        try:
            # Remove markdown code blocks if present
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            elif response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            # Parse JSON
            recommendation = json.loads(response)
            
            # Ensure required fields
            recommendation.setdefault('recommendation', 'CONSIDER')
            recommendation.setdefault('confidence', 'medium')
            recommendation.setdefault('summary', 'No summary provided')
            recommendation.setdefault('strengths', [])
            recommendation.setdefault('concerns', [])
            recommendation.setdefault('reasoning', 'No reasoning provided')
            recommendation.setdefault('key_factors', [])
            
            return recommendation
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse OpenAI response as JSON: {e}")
            print(f"Response was: {response[:500]}")
            # Return fallback recommendation
            return {
                'recommendation': 'CONSIDER',
                'confidence': 'low',
                'summary': 'Unable to parse AI recommendation',
                'strengths': [],
                'concerns': ['AI response parsing failed'],
                'reasoning': f'Error parsing AI response: {str(e)}',
                'key_factors': []
            }
    
    def send_recommendation_email(self, profile: CandidateVacancyProfile, recommendation: Dict[str, Any]) -> bool:
        """
        Send hiring recommendation email to manager
        """
        try:
            candidate = profile.candidate
            vacancy = profile.vacancy
            manager = vacancy.manager
            
            # Determine recommendation status
            rec_status = recommendation.get('recommendation', 'CONSIDER')
            confidence = recommendation.get('confidence', 'medium')
            
            # Create email subject
            subject = f"Hiring Recommendation: {candidate.full_name} - {vacancy.title}"
            
            # Create email body
            text_content = self._create_email_text(profile, recommendation)
            html_content = self._create_email_html(profile, recommendation)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[manager.email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            
            print(f"✅ Hiring recommendation email sent to {manager.email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send hiring recommendation email: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_email_text(self, profile: CandidateVacancyProfile, recommendation: Dict[str, Any]) -> str:
        """
        Create plain text email content
        """
        candidate = profile.candidate
        vacancy = profile.vacancy
        
        text = f"""
Dear {vacancy.manager.get_full_name() or vacancy.manager.username},

Hiring Recommendation Report

CANDIDATE: {candidate.full_name}
VACANCY: {vacancy.title} ({vacancy.department})

RECOMMENDATION: {recommendation.get('recommendation', 'CONSIDER')}
CONFIDENCE LEVEL: {recommendation.get('confidence', 'medium').upper()}

SUMMARY:
{recommendation.get('summary', 'No summary available')}

STRENGTHS:
"""
        
        for strength in recommendation.get('strengths', []):
            text += f"  • {strength}\n"
        
        if recommendation.get('concerns'):
            text += "\nCONCERNS:\n"
            for concern in recommendation.get('concerns', []):
                text += f"  • {concern}\n"
        
        text += f"\nDETAILED REASONING:\n{recommendation.get('reasoning', 'No reasoning provided')}\n"
        
        if recommendation.get('key_factors'):
            text += "\nKEY FACTORS:\n"
            for factor in recommendation.get('key_factors', []):
                text += f"  • {factor}\n"
        
        text += f"""
---
This recommendation is based on:
- Initial Assessment Score: {profile.ai_score or 'N/A'}/10
- Manager Feedback: {profile.manager_feedback[:100] if profile.manager_feedback else 'N/A'}...
- Manager Rating: {self._get_rating_display(profile.manager_rating) if profile.manager_rating else 'N/A'}
- Questionnaire Response: {'Provided' if profile.questionnaire_response else 'Not provided'}

Best regards,
Fahmy
"""
        
        return text.strip()
    
    def _create_email_html(self, profile: CandidateVacancyProfile, recommendation: Dict[str, Any]) -> str:
        """
        Create HTML email content
        """
        candidate = profile.candidate
        vacancy = profile.vacancy
        
        rec_status = recommendation.get('recommendation', 'CONSIDER')
        confidence = recommendation.get('confidence', 'medium')
        
        # Color coding for recommendation
        if rec_status == 'HIRE':
            status_color = '#10b981'  # Green
            status_bg = '#d1fae5'
        elif rec_status == 'DO NOT HIRE':
            status_color = '#ef4444'  # Red
            status_bg = '#fee2e2'
        else:
            status_color = '#f59e0b'  # Orange
            status_bg = '#fef3c7'
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #007cba; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; }}
        .recommendation {{ background: {status_bg}; border-left: 4px solid {status_color}; padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .recommendation h2 {{ margin: 0 0 10px 0; color: {status_color}; }}
        .section {{ margin: 20px 0; }}
        .section h3 {{ color: #007cba; border-bottom: 2px solid #007cba; padding-bottom: 5px; }}
        .strength {{ color: #10b981; }}
        .concern {{ color: #ef4444; }}
        .factor {{ background: #f3f4f6; padding: 8px; margin: 5px 0; border-radius: 4px; }}
        .footer {{ background: #f3f4f6; padding: 15px; text-align: center; font-size: 12px; color: #6b7280; border-radius: 0 0 8px 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Hiring Recommendation</h1>
        </div>
        <div class="content">
            <p>Dear {vacancy.manager.get_full_name() or vacancy.manager.username},</p>
            
            <div class="section">
                <h3>Candidate Information</h3>
                <p><strong>Name:</strong> {candidate.full_name}</p>
                <p><strong>Vacancy:</strong> {vacancy.title} ({vacancy.department})</p>
            </div>
            
            <div class="recommendation">
                <h2>RECOMMENDATION: {rec_status}</h2>
                <p><strong>Confidence Level:</strong> {confidence.upper()}</p>
            </div>
            
            <div class="section">
                <h3>Summary</h3>
                <p>{recommendation.get('summary', 'No summary available')}</p>
            </div>
"""
        
        if recommendation.get('strengths'):
            html += """
            <div class="section">
                <h3>✅ Strengths</h3>
                <ul>
"""
            for strength in recommendation.get('strengths', []):
                html += f"                    <li class='strength'>{strength}</li>\n"
            html += "                </ul>\n            </div>\n"
        
        if recommendation.get('concerns'):
            html += """
            <div class="section">
                <h3>⚠️ Concerns</h3>
                <ul>
"""
            for concern in recommendation.get('concerns', []):
                html += f"                    <li class='concern'>{concern}</li>\n"
            html += "                </ul>\n            </div>\n"
        
        html += f"""
            <div class="section">
                <h3>📋 Detailed Reasoning</h3>
                <p>{recommendation.get('reasoning', 'No reasoning provided')}</p>
            </div>
"""
        
        if recommendation.get('key_factors'):
            html += """
            <div class="section">
                <h3>🔑 Key Factors</h3>
"""
            for factor in recommendation.get('key_factors', []):
                html += f"                <div class='factor'>{factor}</div>\n"
            html += "            </div>\n"
        
        html += f"""
            <div class="section">
                <h3>📊 Analysis Basis</h3>
                <ul>
                    <li><strong>Initial Assessment Score:</strong> {profile.ai_score or 'N/A'}/10</li>
                    <li><strong>Manager Rating:</strong> {self._get_rating_display(profile.manager_rating) if profile.manager_rating else 'N/A'}</li>
                    <li><strong>Manager Recommendation:</strong> {'Yes' if profile.manager_recommendation else 'No' if profile.manager_recommendation is False else 'N/A'}</li>
                    <li><strong>Questionnaire Response:</strong> {'Provided' if profile.questionnaire_response else 'Not provided'}</li>
                </ul>
            </div>
        </div>
        <div class="footer">
            <p>This recommendation is based on comprehensive candidate analysis and evaluation.</p>
            <p>Fahmy | {timezone.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html

