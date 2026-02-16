# ai/linkedin_job_post_prompt.py
"""
GPT prompt template for generating professional LinkedIn job posts.
"""

def create_linkedin_job_post_prompt(vacancy) -> str:
    """
    Create a GPT prompt for generating a LinkedIn job post from vacancy data
    
    Args:
        vacancy: Vacancy model instance
        
    Returns:
        Formatted prompt string
    """
    
    prompt = f"""
You are an expert HR professional creating a compelling LinkedIn job posting.

Generate a professional, engaging LinkedIn job post based on the following vacancy details:

**Job Title**: {vacancy.title}
**Department**: {vacancy.department}
**Keywords/Skills**: {vacancy.keywords}
**Manager**: {vacancy.manager.get_full_name() or vacancy.manager.email}

Create a CONCISE LinkedIn job post that includes:

1. **Opening Hook** (1 sentence)
   - Attention-grabbing introduction

2. **About the Role** (1-2 sentences)
   - Clear overview of the position and key impact

3. **Key Responsibilities** (3-4 bullet points)
   - Most important tasks only
   - Use strong action verbs

4. **Required Qualifications** (3-4 bullet points)
   - Must-have skills only
   - Based on the keywords provided

5. **What We Offer** (2-3 bullet points)
   - Top benefits and growth opportunities

6. **Call to Action** (1 sentence)
   - Encourage candidates to apply

**CRITICAL Guidelines:**
- Keep the TOTAL length under 500 words maximum (strict limit!)
- Be extremely concise - every word must count
- Use professional but engaging tone
- Use emojis sparingly (max 2 total, only in section headers)
- Make it scannable with clear sections
- Focus on the most important information only

**Output Format:**
Return ONLY the job post text, formatted with clear section breaks.
Do not include any meta-commentary or explanations.
Use line breaks between sections for readability.

Example structure:
[1 sentence hook]

**About the Role** 🎯
[1-2 sentences]

**Key Responsibilities**
• [Item 1]
• [Item 2]
• [Item 3]

**Required Qualifications**
• [Item 1]
• [Item 2]
• [Item 3]

**What We Offer** 
• [Item 1]
• [Item 2]

**Ready to Join Us?**
[1 sentence call to action]
"""
    
    return prompt


def create_job_description_from_keywords(keywords: str) -> str:
    """
    Generate a basic job description from keywords (fallback)
    
    Args:
        keywords: Comma-separated keywords
        
    Returns:
        Basic job description
    """
    keywords_list = [k.strip() for k in keywords.split(',') if k.strip()]
    
    if not keywords_list:
        return "We are looking for a talented professional to join our team."
    
    return f"We are seeking a skilled professional with expertise in {', '.join(keywords_list[:-1])} and {keywords_list[-1]}."
