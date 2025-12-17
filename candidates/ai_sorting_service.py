"""
AI-powered candidate sorting service using OpenAI
This service parses natural language queries and converts them to Django ORM filters
"""
import os
import json
import requests
from typing import Dict, Any, List, Optional
from django.db.models import Q
from candidates.models import Candidate, CandidateVacancyProfile


class CandidateSortingAIService:
    """
    AI service that parses natural language queries about candidate sorting/filtering
    and converts them to Django ORM queries
    """
    
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            print("⚠️  OPENAI_API_KEY not found. AI sorting features will not work.")
    
    def parse_query(self, user_query: str) -> Dict[str, Any]:
        """
        Parse a natural language query and return filter criteria
        
        Args:
            user_query: Natural language query like "get candidates with engineering background"
            
        Returns:
            Dictionary with filter criteria that can be used to query candidates
        """
        if not self.api_key:
            return {
                'error': 'OpenAI API key not configured',
                'filters': {}
            }
        
        try:
            # Create prompt for OpenAI
            prompt = self._create_parsing_prompt(user_query)
            
            # Call OpenAI API
            response = self._call_openai_api(prompt)
            
            # Parse response
            parsed_criteria = self._parse_ai_response(response)
            
            return parsed_criteria
            
        except Exception as e:
            print(f"❌ Error parsing query: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'error': f'Error parsing query: {str(e)}',
                'filters': {}
            }
    
    def _create_parsing_prompt(self, user_query: str) -> str:
        """
        Create a prompt for OpenAI to parse the user query
        """
        # Get available fields from the model
        available_fields = self._get_available_fields()
        
        prompt = f"""You are Fahmy, an AI assistant specialized in helping with candidate sorting and filtering in a recruitment system.

Your task is to parse natural language queries about candidates and convert them into structured filter criteria.

Available candidate fields and their types:
{json.dumps(available_fields, indent=2)}

User Query: "{user_query}"

Analyze the query and extract filter criteria. Return ONLY a valid JSON object with this structure:
{{
    "filters": {{
        "education_degree": "string or null (e.g., 'Bachelor', 'Master', 'PhD', 'Computer Science', 'Engineering')",
        "education_field": "string or null (e.g., 'Computer Science', 'Engineering', 'Business')",
        "skills": ["array of skill keywords or null"],
        "experience_years": "number or null (minimum years of experience)",
        "nationality": "string or null",
        "ai_score_min": "number or null (minimum AI score 0-10)",
        "manager_rating_min": "number or null (minimum manager rating 1-5)",
        "manager_recommended": "boolean or null (true/false/null)",
        "has_interview": "boolean or null (true if interview scheduled/done)",
        "application_status": "string or null (e.g., 'applied', 'shortlisted', 'interview_scheduled')"
    }},
    "sort_by": "string or null (e.g., 'ai_score', 'created_at', 'manager_rating')",
    "sort_order": "string or null ('asc' or 'desc', default 'desc')",
    "explanation": "brief explanation of what filters were applied"
}}

Rules:
1. Only extract criteria that are explicitly mentioned in the query
2. For education queries, try to extract both degree level and field
3. For "engineering background", set education_field to "Engineering" or similar
4. For "bachelor degree in computer science", set education_degree to "Bachelor" and education_field to "Computer Science"
5. Return null for fields not mentioned
6. Return ONLY the JSON object, no additional text or markdown

Example queries:
- "get candidates with engineering background" -> {{"filters": {{"education_field": "Engineering"}}, "sort_by": null, "sort_order": "desc"}}
- "show me candidates with bachelor degree in computer science" -> {{"filters": {{"education_degree": "Bachelor", "education_field": "Computer Science"}}, "sort_by": null, "sort_order": "desc"}}
- "candidates with AI score above 7" -> {{"filters": {{"ai_score_min": 7}}, "sort_by": "ai_score", "sort_order": "desc"}}
"""
        return prompt
    
    def _get_available_fields(self) -> Dict[str, Any]:
        """
        Get available fields that can be used for filtering
        """
        return {
            "candidate_fields": {
                "full_name": "string",
                "email": "string",
                "nationality": "string",
                "ai_extracted_data": "JSON (contains education, skills, experience)",
                "ai_score_out_of_10": "decimal 0-10"
            },
            "profile_fields": {
                "education_degree": "extracted from ai_extracted_data.education",
                "education_field": "extracted from ai_extracted_data.education",
                "skills": "extracted from ai_extracted_data.skills",
                "experience_years": "extracted from ai_extracted_data.experience",
                "ai_score": "decimal 0-10",
                "manager_rating": "integer 1-5",
                "manager_recommendation": "boolean",
                "interview_scheduled": "boolean",
                "application_status": "string"
            }
        }
    
    def _call_openai_api(self, prompt: str) -> str:
        """
        Call OpenAI API to parse the query
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'gpt-4',  # Using GPT-4 for better understanding
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are Fahmy, an AI assistant for candidate sorting. Always respond with valid JSON only, no additional text or markdown formatting.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 500,
                'temperature': 0.1  # Low temperature for consistent parsing
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=30
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
    
    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the AI response into structured filter criteria
        """
        try:
            # Clean the response (remove markdown code blocks if present)
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            # Parse JSON
            parsed = json.loads(response)
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing AI response as JSON: {e}")
            print(f"Response was: {response}")
            return {
                'error': 'Failed to parse AI response',
                'filters': {},
                'explanation': 'The AI response could not be parsed as valid JSON'
            }
    
    def apply_filters(self, filters: Dict[str, Any], vacancy_id: Optional[int] = None) -> List[CandidateVacancyProfile]:
        """
        Apply the parsed filters to get matching candidates
        
        Args:
            filters: Dictionary of filter criteria from parse_query
            vacancy_id: Optional vacancy ID to filter by specific vacancy
            
        Returns:
            QuerySet of CandidateVacancyProfile objects matching the criteria
        """
        # Start with base queryset
        queryset = CandidateVacancyProfile.objects.all()
        
        # Filter by vacancy if specified
        if vacancy_id:
            queryset = queryset.filter(vacancy_id=vacancy_id)
        
        # Apply filters
        if filters.get('education_field'):
            # Search in ai_extracted_data JSON field
            education_field = filters['education_field'].lower()
            queryset = queryset.filter(
                ai_extracted_data__education__icontains=education_field
            ) | queryset.filter(
                candidate__ai_extracted_data__education__icontains=education_field
            )
        
        if filters.get('education_degree'):
            degree = filters['education_degree'].lower()
            queryset = queryset.filter(
                ai_extracted_data__education__icontains=degree
            ) | queryset.filter(
                candidate__ai_extracted_data__education__icontains=degree
            )
        
        if filters.get('skills'):
            # Search for any of the skills in ai_extracted_data
            skills = filters['skills']
            if isinstance(skills, list):
                q_objects = Q()
                for skill in skills:
                    q_objects |= Q(ai_extracted_data__skills__icontains=skill.lower())
                    q_objects |= Q(candidate__ai_extracted_data__skills__icontains=skill.lower())
                queryset = queryset.filter(q_objects)
        
        if filters.get('experience_years'):
            # This is tricky - we'd need to parse experience from JSON
            # For now, we'll search in the text
            exp_years = filters['experience_years']
            queryset = queryset.filter(
                ai_extracted_data__experience__icontains=str(exp_years)
            ) | queryset.filter(
                candidate__ai_extracted_data__experience__icontains=str(exp_years)
            )
        
        if filters.get('nationality'):
            queryset = queryset.filter(
                candidate__nationality__icontains=filters['nationality']
            )
        
        if filters.get('ai_score_min') is not None:
            queryset = queryset.filter(ai_score__gte=filters['ai_score_min'])
        
        if filters.get('manager_rating_min') is not None:
            queryset = queryset.filter(manager_rating__gte=filters['manager_rating_min'])
        
        if filters.get('manager_recommended') is not None:
            queryset = queryset.filter(manager_recommendation=filters['manager_recommended'])
        
        if filters.get('has_interview') is not None:
            if filters['has_interview']:
                queryset = queryset.filter(interview_scheduled=True)
            else:
                queryset = queryset.filter(interview_scheduled=False)
        
        if filters.get('application_status'):
            queryset = queryset.filter(application_status=filters['application_status'])
        
        # Apply sorting
        sort_by = filters.get('sort_by', 'created_at')
        sort_order = filters.get('sort_order', 'desc')
        
        if sort_by == 'ai_score':
            if sort_order == 'asc':
                queryset = queryset.order_by('ai_score')
            else:
                queryset = queryset.order_by('-ai_score')
        elif sort_by == 'manager_rating':
            if sort_order == 'asc':
                queryset = queryset.order_by('manager_rating')
            else:
                queryset = queryset.order_by('-manager_rating')
        elif sort_by == 'created_at':
            if sort_order == 'asc':
                queryset = queryset.order_by('created_at')
            else:
                queryset = queryset.order_by('-created_at')
        else:
            # Default sorting
            queryset = queryset.order_by('-created_at')
        
        return queryset.select_related('candidate', 'vacancy')


