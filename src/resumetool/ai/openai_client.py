"""OpenAI client for AI-powered analysis and generation."""
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from pydantic import ValidationError

from resumetool.types import ResumeAnalysis, Skill, Experience, SkillLevel, JobListing, JobMatch


class OpenAIAnalyzer:
    """OpenAI-powered resume and job analysis."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-5-nano"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def enhance_resume_analysis(self, basic_analysis: ResumeAnalysis) -> ResumeAnalysis:
        """Enhance basic resume analysis with AI-powered insights."""
        
        prompt = self._build_resume_analysis_prompt(basic_analysis)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert resume analyzer. Provide structured analysis in the exact JSON format requested."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            enhanced_data = json.loads(content)
            
            # Update the analysis with enhanced data
            if "skills" in enhanced_data:
                basic_analysis.skills = self._parse_enhanced_skills(enhanced_data["skills"])
            
            if "experience" in enhanced_data:
                basic_analysis.experience = self._parse_enhanced_experience(enhanced_data["experience"])
            
            if "title" in enhanced_data:
                basic_analysis.title = enhanced_data["title"]
            
            if "summary" in enhanced_data:
                basic_analysis.summary = enhanced_data["summary"]
            
            return basic_analysis
            
        except Exception as e:
            # If AI enhancement fails, return original analysis
            print(f"AI enhancement failed: {e}")
            return basic_analysis
    
    def analyze_job_fit(self, resume: ResumeAnalysis, job: JobListing) -> JobMatch:
        """Analyze how well a resume fits a job using AI."""
        
        prompt = self._build_job_fit_prompt(resume, job)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert recruiter analyzing job fit. Provide detailed matching analysis in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            match_data = json.loads(content)
            
            return JobMatch(
                job=job,
                match_score=match_data.get("match_score", 0.0),
                skill_match_score=match_data.get("skill_match_score", 0.0),
                experience_match_score=match_data.get("experience_match_score", 0.0),
                missing_skills=match_data.get("missing_skills", []),
                matching_skills=match_data.get("matching_skills", []),
                experience_gaps=match_data.get("experience_gaps", []),
                recommendations=match_data.get("recommendations", [])
            )
            
        except Exception as e:
            # Return basic match if AI fails
            basic_match_score = self._calculate_basic_match_score(resume, job)
            return JobMatch(
                job=job,
                match_score=basic_match_score,
                skill_match_score=basic_match_score,
                experience_match_score=basic_match_score,
                missing_skills=[],
                matching_skills=[],
                experience_gaps=[],
                recommendations=[f"AI analysis failed: {e}"]
            )
    
    def generate_job_search_terms(self, resume: ResumeAnalysis) -> List[str]:
        """Generate relevant job search terms based on resume."""
        
        prompt = f"""
        Based on this resume analysis, generate 10-15 relevant job search keywords and terms:
        
        Title: {resume.title}
        Skills: {[skill.name for skill in resume.skills]}
        Experience: {[exp.title for exp in resume.experience]}
        
        Return only a JSON array of search terms, like: ["software engineer", "python developer", ...]
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Generate job search keywords based on resume data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception:
            # Fallback to basic terms
            terms = []
            if resume.title:
                terms.append(resume.title.lower())
            for skill in resume.skills[:5]:
                terms.append(skill.name.lower())
            return terms
    
    def optimize_resume_content(self, resume: ResumeAnalysis, job: JobListing) -> Dict[str, str]:
        """Generate optimized resume content for a specific job."""
        
        prompt = self._build_optimization_prompt(resume, job)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert resume writer specializing in ATS optimization and job-specific tailoring."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            return {
                "summary": resume.summary or "Professional summary optimization failed",
                "key_changes": [f"Optimization failed: {e}"],
                "optimized_skills": [skill.name for skill in resume.skills]
            }
    
    def _build_resume_analysis_prompt(self, analysis: ResumeAnalysis) -> str:
        """Build prompt for resume analysis enhancement."""
        return f"""
        Analyze this resume and enhance the extracted information:
        
        Raw Resume Text:
        {analysis.raw_text[:2000]}...
        
        Current Analysis:
        - Name: {analysis.name}
        - Title: {analysis.title}
        - Skills: {[skill.name for skill in analysis.skills]}
        - Experience: {len(analysis.experience)} entries
        
        Please provide enhanced analysis in this JSON format:
        {{
            "title": "Most likely professional title based on experience",
            "summary": "Professional summary if found or generated",
            "skills": [
                {{"name": "skill_name", "level": "beginner|intermediate|advanced|expert", "category": "category_name", "years_experience": 2}}
            ],
            "experience": [
                {{"title": "job_title", "company": "company_name", "duration": "duration", "key_achievements": ["achievement1", "achievement2"]}}
            ]
        }}
        """
    
    def _build_job_fit_prompt(self, resume: ResumeAnalysis, job: JobListing) -> str:
        """Build prompt for job fit analysis."""
        return f"""
        Analyze how well this resume matches this job posting:
        
        RESUME:
        Title: {resume.title}
        Skills: {[skill.name for skill in resume.skills]}
        Experience: {[f"{exp.title} at {exp.company}" for exp in resume.experience]}
        
        JOB POSTING:
        Title: {job.title}
        Company: {job.company}
        Requirements: {job.requirements}
        Preferred Skills: {job.preferred_skills}
        Description: {job.description[:500]}...
        
        Provide detailed matching analysis in this JSON format:
        {{
            "match_score": 0.85,
            "skill_match_score": 0.9,
            "experience_match_score": 0.8,
            "missing_skills": ["skill1", "skill2"],
            "matching_skills": ["skill3", "skill4"],
            "experience_gaps": ["gap1", "gap2"],
            "recommendations": ["recommendation1", "recommendation2"]
        }}
        
        Scores should be between 0.0 and 1.0.
        """
    
    def _build_optimization_prompt(self, resume: ResumeAnalysis, job: JobListing) -> str:
        """Build prompt for resume optimization."""
        return f"""
        Optimize this resume for the specific job posting:
        
        CURRENT RESUME:
        Summary: {resume.summary}
        Skills: {[skill.name for skill in resume.skills]}
        Experience: {[exp.title for exp in resume.experience]}
        
        TARGET JOB:
        Title: {job.title}
        Company: {job.company}
        Requirements: {job.requirements}
        
        Provide optimized content in this JSON format:
        {{
            "summary": "ATS-optimized professional summary",
            "key_changes": ["change1", "change2"],
            "optimized_skills": ["skill1", "skill2"],
            "suggested_keywords": ["keyword1", "keyword2"]
        }}
        """
    
    def _parse_enhanced_skills(self, skills_data: List[Dict]) -> List[Skill]:
        """Parse enhanced skills data from AI response."""
        skills = []
        for skill_data in skills_data:
            try:
                level = SkillLevel(skill_data.get("level", "intermediate"))
                skills.append(Skill(
                    name=skill_data["name"],
                    level=level,
                    years_experience=skill_data.get("years_experience"),
                    category=skill_data.get("category")
                ))
            except (ValidationError, ValueError):
                # Skip invalid skill data
                continue
        return skills
    
    def _parse_enhanced_experience(self, exp_data: List[Dict]) -> List[Experience]:
        """Parse enhanced experience data from AI response."""
        experiences = []
        for exp in exp_data:
            try:
                experiences.append(Experience(
                    title=exp["title"],
                    company=exp["company"], 
                    duration=exp["duration"],
                    description=exp.get("description", ""),
                    key_achievements=exp.get("key_achievements", []),
                    skills_used=exp.get("skills_used", [])
                ))
            except (ValidationError, KeyError):
                # Skip invalid experience data
                continue
        return experiences
    
    def _calculate_basic_match_score(self, resume: ResumeAnalysis, job: JobListing) -> float:
        """Calculate basic match score without AI."""
        resume_skills = {skill.name.lower() for skill in resume.skills}
        job_requirements = {req.lower() for req in job.requirements + job.preferred_skills}
        
        if not job_requirements:
            return 0.5  # Neutral score if no requirements
        
        matches = len(resume_skills.intersection(job_requirements))
        return min(1.0, matches / len(job_requirements))