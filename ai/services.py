# ai/services.py
import json
import os
import requests
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from .models import AIAnalysis

class AIService:
    """Service for AI-powered CV analysis and candidate profiling"""
    
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            print("⚠️  OPENAI_API_KEY not found. AI features will be simulated.")
    
    def extract_cv_data(self, cv_text: str, cv_file: Optional[UploadedFile] = None) -> Dict[str, Any]:
        """Extract structured data from CV using OpenAI"""
        
        if cv_file:
            # If we have a file, we could use OpenAI's vision API for PDF/image analysis
            # For now, we'll work with the text content
            print(f"📄 Processing CV file: {cv_file.name}")
        
        # Create the extraction prompt
        prompt = self._create_cv_extraction_prompt(cv_text)
        
        if not self.api_key:
            # Simulate extraction for testing
            return self._simulate_cv_extraction(cv_text)
        
        try:
            # Call OpenAI API
            response = self._call_openai_api(prompt)
            
            # Parse the response
            extracted_data = self._parse_cv_extraction_response(response)
            
            return extracted_data
            
        except Exception as e:
            print(f"❌ CV extraction failed: {str(e)}")
            # Fallback to simulation
            return self._simulate_cv_extraction(cv_text)
    
    def _create_cv_extraction_prompt(self, cv_text: str) -> str:
        """Create OpenAI prompt for CV data extraction"""
        
        prompt = f"""
You are an expert HR professional extracting structured data from a CV. Please analyze the following CV text and extract key information.

CV TEXT:
{cv_text}

Please extract and return the following information in a JSON format:

{{
    "personal_info": {{
        "full_name": "Full name of the candidate",
        "email": "Email address if found",
        "phone": "Phone number if found",
        "location": "City, Country or location",
        "date_of_birth": "Date of birth if mentioned",
        "nationality": "Nationality if mentioned"
    }},
    "education": [
        {{
            "degree": "Degree name",
            "institution": "University/School name",
            "field_of_study": "Field of study",
            "graduation_year": "Year of graduation",
            "gpa": "GPA if mentioned"
        }}
    ],
    "experience": [
        {{
            "job_title": "Job title",
            "company": "Company name",
            "start_date": "Start date",
            "end_date": "End date or 'Present'",
            "description": "Job description and responsibilities",
            "technologies": ["List of technologies used"]
        }}
    ],
    "skills": {{
        "technical_skills": ["List of technical skills"],
        "programming_languages": ["List of programming languages"],
        "frameworks": ["List of frameworks and libraries"],
        "tools": ["List of tools and software"],
        "soft_skills": ["List of soft skills"]
    }},
    "certifications": [
        {{
            "name": "Certification name",
            "issuer": "Issuing organization",
            "date": "Date obtained"
        }}
    ],
    "projects": [
        {{
            "name": "Project name",
            "description": "Project description",
            "technologies": ["Technologies used"],
            "url": "Project URL if mentioned"
        }}
    ],
    "languages": [
        {{
            "language": "Language name",
            "proficiency": "Native/Fluent/Intermediate/Basic"
        }}
    ],
    "summary": "Brief professional summary extracted from the CV"
}}

Important instructions:
1. If information is not found, use null or empty arrays
2. Be accurate and don't make up information
3. Extract dates in YYYY-MM format when possible
4. For skills, be specific and technical
5. For experience, focus on recent and relevant positions
6. Return only valid JSON, no additional text
"""
        return prompt
    
    def _parse_cv_extraction_response(self, response: str) -> Dict[str, Any]:
        """Parse OpenAI response for CV extraction"""
        try:
            # Try to parse as JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback parsing
            return self._simulate_cv_extraction("")
    
    def _simulate_cv_extraction(self, cv_text: str) -> Dict[str, Any]:
        """Simulate CV extraction for testing"""
        
        # Simple keyword extraction for simulation
        cv_lower = cv_text.lower()
        
        # Extract basic info from CV text
        import re
        
        # Extract name
        name_match = re.search(r'^([A-Za-z\s]+)', cv_text.strip())
        full_name = name_match.group(1).strip() if name_match else "Extracted Name"
        
        # Extract email
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', cv_text)
        email = email_match.group(1) if email_match else "candidate@example.com"
        
        # Extract phone
        phone_match = re.search(r'(\+?[0-9\s\-\(\)]{10,})', cv_text)
        phone = phone_match.group(1).strip() if phone_match else "+1234567890"
        
        # Extract location
        location_match = re.search(r'Location:\s*([^\n\r]+)', cv_text, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else "City, Country"
        
        # Extract nationality
        nationality_match = re.search(r'Nationality:\s*([^\n\r]+)', cv_text, re.IGNORECASE)
        nationality = nationality_match.group(1).strip() if nationality_match else None
        
        # Extract date of birth
        dob_match = re.search(r'Date of Birth:\s*([^\n\r]+)', cv_text, re.IGNORECASE)
        date_of_birth = dob_match.group(1).strip() if dob_match else None
        
        personal_info = {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "location": location,
            "date_of_birth": date_of_birth,
            "nationality": nationality
        }
        
        # Extract skills based on common keywords
        technical_skills = []
        programming_languages = []
        frameworks = []
        
        skill_keywords = {
            'python': 'Python',
            'java': 'Java',
            'javascript': 'JavaScript',
            'react': 'React',
            'django': 'Django',
            'flask': 'Flask',
            'node': 'Node.js',
            'sql': 'SQL',
            'postgresql': 'PostgreSQL',
            'mysql': 'MySQL',
            'mongodb': 'MongoDB',
            'docker': 'Docker',
            'kubernetes': 'Kubernetes',
            'aws': 'AWS',
            'azure': 'Azure',
            'git': 'Git'
        }
        
        for keyword, skill in skill_keywords.items():
            if keyword in cv_lower:
                if keyword in ['python', 'java', 'javascript']:
                    programming_languages.append(skill)
                elif keyword in ['django', 'flask', 'react', 'node']:
                    frameworks.append(skill)
                else:
                    technical_skills.append(skill)
        
        # Extract education
        education = []
        edu_match = re.search(r'Education:\s*(.*?)(?=Technical Skills|Experience|$)', cv_text, re.IGNORECASE | re.DOTALL)
        if edu_match:
            edu_text = edu_match.group(1)
            degree_match = re.search(r'(Bachelor|Master|PhD|Diploma)[^\\n]*', edu_text, re.IGNORECASE)
            institution_match = re.search(r'([A-Za-z\s]+University|[A-Za-z\s]+College)', edu_text)
            year_match = re.search(r'\((\d{4})\)', edu_text)
            
            education.append({
                "degree": degree_match.group(0).strip() if degree_match else "Bachelor of Computer Science",
                "institution": institution_match.group(1).strip() if institution_match else "University",
                "field_of_study": "Computer Science",
                "graduation_year": year_match.group(1) if year_match else "2020",
                "gpa": None
            })
        else:
            education.append({
                "degree": "Bachelor of Computer Science",
                "institution": "University",
                "field_of_study": "Computer Science",
                "graduation_year": "2020",
                "gpa": None
            })
        
        # Extract experience
        experience = []
        exp_match = re.search(r'Professional Experience:\s*(.*?)(?=Education|Technical Skills|$)', cv_text, re.IGNORECASE | re.DOTALL)
        if exp_match:
            exp_text = exp_match.group(1)
            # Extract job titles and companies
            job_matches = re.findall(r'([A-Za-z\s]+(?:Developer|Engineer|Manager|Analyst))[^\\n]*at\s+([A-Za-z\s]+)(?:\s*\([^)]+\))?', exp_text)
            for i, (title, company) in enumerate(job_matches[:2]):  # Limit to 2 most recent
                experience.append({
                    "job_title": title.strip(),
                    "company": company.strip(),
                    "start_date": f"202{2-i}-01",
                    "end_date": "Present" if i == 0 else f"202{3-i}-12",
                    "description": f"Worked as {title.strip()} at {company.strip()}",
                    "technologies": technical_skills[:3]
                })
        else:
            experience.append({
                "job_title": "Software Developer",
                "company": "Tech Company",
                "start_date": "2020-01",
                "end_date": "Present",
                "description": "Developed software applications",
                "technologies": technical_skills[:3]
            })
        
        # Extract certifications
        certifications = []
        cert_match = re.search(r'Certifications:\s*(.*?)(?=Languages|Projects|$)', cv_text, re.IGNORECASE | re.DOTALL)
        if cert_match:
            cert_text = cert_match.group(1)
            cert_matches = re.findall(r'([A-Za-z\s]+(?:Certified|Certification)[^\\n]*)', cert_text)
            for cert in cert_matches[:3]:  # Limit to 3
                certifications.append({
                    "name": cert.strip(),
                    "issuer": "Professional Organization",
                    "date": "2022"
                })
        
        # Extract languages
        languages = []
        lang_match = re.search(r'Languages:\s*(.*?)(?=Projects|Certifications|$)', cv_text, re.IGNORECASE | re.DOTALL)
        if lang_match:
            lang_text = lang_match.group(1)
            lang_matches = re.findall(r'([A-Za-z\s]+)\s*\(([A-Za-z\s]+)\)', lang_text)
            for lang, proficiency in lang_matches:
                languages.append({
                    "language": lang.strip(),
                    "proficiency": proficiency.strip()
                })
        else:
            languages.append({
                "language": "English",
                "proficiency": "Fluent"
            })
        
        return {
            "personal_info": personal_info,
            "education": education,
            "experience": experience,
            "skills": {
                "technical_skills": technical_skills,
                "programming_languages": programming_languages,
                "frameworks": frameworks,
                "tools": ["Git", "Docker"],
                "soft_skills": ["Communication", "Teamwork", "Problem Solving"]
            },
            "certifications": certifications,
            "projects": [
                {
                    "name": "Sample Project",
                    "description": "A sample project description",
                    "technologies": technical_skills[:2],
                    "url": None
                }
            ],
            "languages": languages,
            "summary": f"Experienced {personal_info['full_name']} with strong technical skills in {', '.join(programming_languages[:2])}"
        }
    
    def _extract_text_from_cv_file(self, cv_file) -> str:
        """Extract text from CV file"""
        import os
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        
        # Save file temporarily
        file_path = default_storage.save(f'temp/{cv_file.name}', ContentFile(cv_file.read()))
        full_path = default_storage.path(file_path)
        
        try:
            # Extract text based on file type
            if cv_file.name.lower().endswith('.txt'):
                with open(full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif cv_file.name.lower().endswith('.pdf'):
                try:
                    import PyPDF2
                    with open(full_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        text = ''
                        for page in reader.pages:
                            text += page.extract_text() + '\n'
                        return text
                except ImportError:
                    return f"[PDF file: {cv_file.name} - Install PyPDF2 for PDF text extraction]"
            elif cv_file.name.lower().endswith(('.doc', '.docx')):
                try:
                    from docx import Document
                    doc = Document(full_path)
                    text = ''
                    for paragraph in doc.paragraphs:
                        text += paragraph.text + '\n'
                    return text
                except ImportError:
                    return f"[DOC file: {cv_file.name} - Install python-docx for DOC text extraction]"
            else:
                return f"[Unsupported file type: {cv_file.name}]"
        finally:
            # Clean up temporary file
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
    
    def analyze_cv_for_vacancy(self, cv_record, vacancy, cv_text=None) -> Dict[str, Any]:
        """Analyze a CV against vacancy requirements using AI"""
        
        # Extract text from CV file if not provided
        if cv_text is None:
            cv_text = self._extract_text_from_cv_file(cv_record.raw_file)
        
        # Create the AI prompt
        prompt = self._create_cv_analysis_prompt(vacancy, cv_text, cv_record.candidate)
        
        if not self.api_key:
            # Simulate AI response for testing
            return self._simulate_ai_response(vacancy, cv_text)
        
        try:
            # Call OpenAI API
            response = self._call_openai_api(prompt)
            
            # Parse the response
            analysis_result = self._parse_ai_response(response)
            
            return analysis_result
            
        except Exception as e:
            print(f"❌ AI analysis failed: {str(e)}")
            # Fallback to simulation
            return self._simulate_ai_response(vacancy, cv_text)
    
    def generate_candidate_profile(self, application, cv_text: str) -> Dict[str, Any]:
        """Generate detailed candidate profile using AI"""
        
        vacancy = application.vacancy
        candidate = application.candidate
        
        prompt = self._create_profile_generation_prompt(vacancy, cv_text, candidate)
        
        if not self.api_key:
            return self._simulate_profile_generation(vacancy, cv_text, candidate)
        
        try:
            response = self._call_openai_api(prompt)
            profile_result = self._parse_profile_response(response)
            
            self._save_analysis(application, prompt, response, 'profile_generation')
            
            return profile_result
            
        except Exception as e:
            print(f"❌ Profile generation failed: {str(e)}")
            return self._simulate_profile_generation(vacancy, cv_text, candidate)
    
    def _create_cv_analysis_prompt(self, vacancy, cv_text: str, candidate) -> str:
        """Create AI prompt for CV analysis"""
        
        prompt = f"""
You are an expert HR recruiter analyzing a candidate's CV for a specific job position.

JOB REQUIREMENTS:
- Title: {vacancy.title}
- Department: {vacancy.department}
- Required Keywords: {vacancy.keywords}
- Require DOB in CV: {vacancy.require_dob_in_cv}
- Require Egyptian nationality: {vacancy.require_egyptian}
- Require relevant university: {vacancy.require_relevant_university}
- Require relevant major: {vacancy.require_relevant_major}
- Questionnaire: {vacancy.questionnaire_template}

CANDIDATE CV:
{cv_text}

Please analyze this CV and provide a detailed assessment. Respond with a JSON object containing:

{{
    "overall_score": <score from 1-10>,
    "score_breakdown": {{
        "technical_skills": <score 1-10>,
        "experience_relevance": <score 1-10>,
        "education_match": <score 1-10>,
        "cultural_fit": <score 1-10>
    }},
    "strengths": ["strength1", "strength2", "strength3"],
    "weaknesses": ["weakness1", "weakness2"],
    "missing_requirements": ["requirement1", "requirement2"],
    "recommendation": "HIRE/MAYBE/REJECT",
    "reasoning": "Detailed explanation of the score and recommendation"
}}

Focus on:
1. Technical skills match with required keywords
2. Relevant experience for the role
3. Education background if required
4. Overall fit for the position
5. Any red flags or concerns

Be thorough and objective in your analysis.
"""
        return prompt
    
    def _create_profile_generation_prompt(self, vacancy, cv_text: str, candidate) -> str:
        """Create AI prompt for candidate profile generation"""
        
        prompt = f"""
You are an expert HR recruiter creating a detailed candidate profile for a specific job position.

JOB REQUIREMENTS:
- Title: {vacancy.title}
- Department: {vacancy.department}
- Required Keywords: {vacancy.keywords}

CANDIDATE INFORMATION:
- Name: {candidate.full_name}
- Email: {candidate.email}
- CV Content: {cv_text}

Please create a comprehensive candidate profile. Respond with a JSON object containing:

{{
    "summary": "2-3 sentence summary of the candidate",
    "skills_analysis": {{
        "technical_skills": ["skill1", "skill2", "skill3"],
        "soft_skills": ["skill1", "skill2"],
        "skill_levels": {{"skill1": "beginner/intermediate/advanced", "skill2": "level"}}
    }},
    "experience_level": "junior/mid-level/senior/expert",
    "strengths": ["strength1", "strength2", "strength3"],
    "areas_for_improvement": ["area1", "area2"],
    "cultural_fit_score": <score 1-10>,
    "technical_score": <score 1-10>,
    "overall_recommendation": "Detailed recommendation for hiring decision"
}}

Be professional and objective in your analysis.
"""
        return prompt
    
    def _call_openai_api(self, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are an expert HR professional specializing in CV data extraction. Always respond with valid JSON only.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 2000,
                'temperature': 0.1
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
                return self._simulate_openai_response(prompt)
                
        except Exception as e:
            print(f"❌ OpenAI API call failed: {str(e)}")
            return self._simulate_openai_response(prompt)
    
    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response into structured data"""
        try:
            # Try to parse as JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback parsing
            return {
                "overall_score": 7.0,
                "score_breakdown": {
                    "technical_skills": 7.0,
                    "experience_relevance": 7.0,
                    "education_match": 7.0,
                    "cultural_fit": 7.0
                },
                "strengths": ["Good technical background", "Relevant experience"],
                "weaknesses": ["Limited experience in some areas"],
                "missing_requirements": [],
                "recommendation": "MAYBE",
                "reasoning": "Candidate shows potential but needs further evaluation"
            }
    
    def _parse_profile_response(self, response: str) -> Dict[str, Any]:
        """Parse profile generation response"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "summary": "Experienced professional with relevant skills",
                "skills_analysis": {
                    "technical_skills": ["Python", "Django", "Database"],
                    "soft_skills": ["Communication", "Problem Solving"],
                    "skill_levels": {"Python": "intermediate", "Django": "intermediate"}
                },
                "experience_level": "mid-level",
                "strengths": ["Technical skills", "Problem solving"],
                "areas_for_improvement": ["Leadership experience"],
                "cultural_fit_score": 7.0,
                "technical_score": 7.0,
                "overall_recommendation": "Good candidate for the position"
            }
    
    def _simulate_ai_response(self, vacancy, cv_text: str) -> Dict[str, Any]:
        """Simulate AI response for testing"""
        
        # Simple keyword matching for simulation
        if vacancy and hasattr(vacancy, 'keyword_list'):
            keywords = vacancy.keyword_list()
        else:
            keywords = ['python', 'django', 'postgresql']  # Default keywords
        cv_lower = cv_text.lower()
        
        matched_keywords = [kw for kw in keywords if kw in cv_lower]
        match_percentage = len(matched_keywords) / len(keywords) if keywords else 0
        
        # Calculate score based on keyword matches
        base_score = match_percentage * 10
        
        # Add some variation
        import random
        score_variation = random.uniform(-1, 1)
        final_score = max(1, min(10, base_score + score_variation))
        
        return {
            "overall_score": round(final_score, 1),
            "score_breakdown": {
                "technical_skills": round(final_score, 1),
                "experience_relevance": round(final_score * 0.9, 1),
                "education_match": round(final_score * 0.8, 1),
                "cultural_fit": round(final_score * 0.85, 1)
            },
            "strengths": [f"Experience with {kw}" for kw in matched_keywords[:3]],
            "weaknesses": ["Could benefit from more experience"] if final_score < 8 else [],
            "missing_requirements": [kw for kw in keywords if kw not in matched_keywords],
            "recommendation": "HIRE" if final_score >= 8 else "MAYBE" if final_score >= 6 else "REJECT",
            "reasoning": f"Score based on {len(matched_keywords)}/{len(keywords)} keyword matches"
        }
    
    def _simulate_profile_generation(self, vacancy, cv_text: str, candidate) -> Dict[str, Any]:
        """Simulate profile generation"""
        
        keywords = vacancy.keyword_list()
        cv_lower = cv_text.lower()
        matched_keywords = [kw for kw in keywords if kw in cv_lower]
        
        return {
            "summary": f"{candidate.full_name} is a professional with experience in {', '.join(matched_keywords[:3])}",
            "skills_analysis": {
                "technical_skills": matched_keywords[:5],
                "soft_skills": ["Communication", "Problem Solving", "Teamwork"],
                "skill_levels": {kw: "intermediate" for kw in matched_keywords[:3]}
            },
            "experience_level": "mid-level",
            "strengths": [f"Strong {kw} skills" for kw in matched_keywords[:3]],
            "areas_for_improvement": ["Leadership experience", "Advanced certifications"],
            "cultural_fit_score": 7.5,
            "technical_score": 8.0 if len(matched_keywords) > 2 else 6.0,
            "overall_recommendation": "Good candidate with relevant technical skills"
        }
    
    def _simulate_openai_response(self, prompt: str) -> str:
        """Simulate OpenAI API response"""
        return json.dumps(self._simulate_ai_response(None, ""))
    
    def _save_analysis(self, application, prompt: str, response: str, analysis_type: str):
        """Save AI analysis to database"""
        try:
            AIAnalysis.objects.create(
                application=application,
                analysis_type=analysis_type,
                prompt_used=prompt,
                response_received=response,
                tokens_used=len(prompt.split()) + len(response.split()),  # Rough estimate
                cost=0.01  # Simulated cost
            )
        except Exception as e:
            print(f"⚠️  Failed to save AI analysis: {str(e)}")
