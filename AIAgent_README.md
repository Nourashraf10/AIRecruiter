## License

© 2025 Nour Ashraf. All rights reserved.

This project is publicly viewable for demonstration purposes only. 
Any copying, redistribution, or commercial use is strictly prohibited without explicit permission.

🤖 AI Recruiter Agent
Automating the hiring workflow from vacancy creation to candidate evaluation and interview scheduling.
📧 Agent Information
Agent Name: AI Recruiter
Agent Email: recruiter@example.com
Purpose: Automate HR and recruitment tasks (vacancy creation, candidate screening, interview scheduling, and feedback collection).
🧩 Overview
The AI Recruiter automates the end-to-end recruitment process for your company:
Creates job vacancies from email prompts.
Coordinates approvals between managers and HR.
Collects and evaluates candidates automatically.
Schedules interviews and manages questionnaires.
Gathers interview feedback and compiles structured candidate profiles.
📨 How to Use
Step 1 — Create a New Vacancy
Send an email to the AI Recruiter (recruiter@example.com) with the following details:
Subject:
Open Vacancy
Body Example:
Title: Fullstack Developer
Department: Engineering
Manager Email: noureldin.ashraf@example.com
Keywords: python, django, postgres, aws, rest api
RequireDOB: true
RequireEgyptian: false
Relevant_University: true
Relevant_Major: true
Questionnaire: Why do you want to join our team? What's your biggest technical achievement?
🧠 Tips:
The Keywords field helps the AI match and score candidates.
Boolean fields (true/false) determine whether certain filters apply (e.g., nationality, DOB, major relevance).
Step 2 — Manager Approval
Once the AI Recruiter receives the vacancy email:
It sends an approval request to the manager (Manager Email).
When the manager approves, the AI automatically emails the HR department to post the vacancy on LinkedIn.
Step 3 — HR Confirmation
After posting the vacancy, HR must reply to the recruiter’s email with the single word:
Posted
⚠️ Important: HR should not include any additional text in this reply.
Step 4 — Candidate Applications
As candidates apply (via LinkedIn or email):
Their CVs and details are sent to the AI Recruiter from the HR.
The Recruiter extracts data, analyzes the CV, and generates a score out of 10, based on:
Keyword match
Relevant university & major
Experience relevance
Questionnaire quality
All candidate data is saved in the database under the corresponding vacancy.
Step 5 — Daily Shortlisting
At the end of each day, the AI Recruiter:
Generates a shortlist of top-scoring candidates.
Automatically checks the manager’s calendar for a free interview slot.
Sends:
Interview invitation to the selected candidate.
Interview notification to the corresponding manager (with candidate details).
Questionnaire email to the candidate to answer before the interview.
🕐 Note:
At this stage, interview dates are fixed and not negotiable — no rescheduling is allowed for either side.
Step 6 — Candidate Questionnaire
The candidate replies to the questionnaire email.
Their answers are automatically parsed and added to their profile in the system for future evaluation.
Step 7 — Manager Feedback
After each interview:
The AI sends a feedback request email to the interviewing manager.
The manager replies with notes or ratings.
The feedback is stored in the candidate’s profile.
Step 8 — Hiring Decision
By the end of the process, each candidate profile includes:
📄 Data extracted from CV
💬 Questionnaire responses
🗒️ Manager interview feedback
⭐ Final AI recommendation sent to the manager via mail
This allows the HR team and managers to easily compare candidates and finalize hiring decisions.
🗃️ Data Structure
Each project (vacancy) and candidate are stored in a relational database.
Main Entities:
User – represents HR, manager, or AI agent
Vacancy – job opening details and requirements
Candidate – applicant’s data, CV analysis, and scores
Questionnaire – predefined questions per vacancy
Interview – scheduled date, status, feedback links
Feedback – manager’s notes and rating
All entities are linked via foreign keys for easy tracking and querying.
⚙️ Tech Stack
Backend: Django
AI Integration: OpenAI API
Scheduling / Background Tasks: Celery
Containerization: Docker
Database: PostgreSQL
Email Handling: SMTP (for agent email automation)
💡 Future Improvements
Add rescheduling logic for interviews
Support multiple AI Recruiters per department
Improve scoring algorithm with machine learning feedback
Integrate dashboard for vacancy and candidate insights