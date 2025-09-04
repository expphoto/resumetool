"""Resume parsing and analysis functionality."""
import re
from pathlib import Path
from typing import Optional, Dict, Any

from docx import Document
import pypdf
from pdfminer.high_level import extract_text

from resumetool.types import ResumeAnalysis, Skill, Experience, SkillLevel


class ResumeParser:
    """Parse and extract information from resume documents."""
    
    def __init__(self):
        self.supported_formats = {'.docx', '.pdf', '.txt'}
    
    def parse_file(self, file_path: str) -> ResumeAnalysis:
        """Parse resume from file path."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path}")
        
        if path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        # Extract text based on file type
        if path.suffix.lower() == '.docx':
            raw_text = self._extract_docx(path)
        elif path.suffix.lower() == '.pdf':
            raw_text = self._extract_pdf(path)
        else:  # .txt
            raw_text = self._extract_txt(path)
        
        return self._analyze_text(raw_text, {"file_path": str(path)})
    
    def parse_text(self, text: str) -> ResumeAnalysis:
        """Parse resume from raw text."""
        return self._analyze_text(text, {"source": "text_input"})
    
    def _extract_docx(self, path: Path) -> str:
        """Extract text from DOCX file."""
        try:
            doc = Document(path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return '\n'.join(paragraphs)
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX file: {e}")
    
    def _extract_pdf(self, path: Path) -> str:
        """Extract text from PDF file."""
        try:
            # First try pdfminer (better text extraction)
            text = extract_text(str(path))
            if text.strip():
                return text
            
            # Fallback to pypdf
            with open(path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                text_parts = []
                for page in reader.pages:
                    text_parts.append(page.extract_text())
                return '\n'.join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to parse PDF file: {e}")
    
    def _extract_txt(self, path: Path) -> str:
        """Extract text from TXT file."""
        try:
            return path.read_text(encoding='utf-8')
        except Exception as e:
            raise ValueError(f"Failed to read TXT file: {e}")
    
    def _analyze_text(self, text: str, metadata: Dict[str, Any]) -> ResumeAnalysis:
        """Analyze resume text and extract structured information."""
        
        # Basic contact info extraction
        name = self._extract_name(text)
        email = self._extract_email(text)
        phone = self._extract_phone(text)
        
        # Extract sections
        summary = self._extract_summary(text)
        skills = self._extract_skills(text)
        experience = self._extract_experience(text)
        education = self._extract_education(text)
        certifications = self._extract_certifications(text)
        
        return ResumeAnalysis(
            name=name,
            email=email,
            phone=phone,
            summary=summary,
            skills=skills,
            experience=experience,
            education=education,
            certifications=certifications,
            raw_text=text,
            metadata=metadata
        )
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract candidate name from resume text."""
        lines = text.split('\n')
        
        # Look for name in first few lines
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 3 and len(line.split()) >= 2:
                # Basic heuristic: if line has 2-4 words and looks like a name
                words = line.split()
                if 2 <= len(words) <= 4 and all(word.istitle() for word in words):
                    return line
        
        return None
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email address from resume text."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        return matches[0] if matches else None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number from resume text."""
        phone_patterns = [
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',
            r'\+?1?[-.\s]?\(\d{3}\)[-.\s]?\d{3}[-.\s]?\d{4}'
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        
        return None
    
    def _extract_summary(self, text: str) -> Optional[str]:
        """Extract professional summary or objective."""
        summary_keywords = ['summary', 'objective', 'profile', 'about']
        lines = text.lower().split('\n')
        
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in summary_keywords):
                # Get next few lines as summary
                summary_lines = []
                for j in range(i + 1, min(i + 6, len(lines))):
                    if lines[j].strip() and not any(
                        section in lines[j] for section in ['experience', 'education', 'skills']
                    ):
                        summary_lines.append(text.split('\n')[j].strip())
                    else:
                        break
                
                if summary_lines:
                    return ' '.join(summary_lines)
        
        return None
    
    def _extract_skills(self, text: str) -> list[Skill]:
        """Extract skills from resume text."""
        # Common skill categories and keywords
        skill_categories = {
            'programming': ['python', 'javascript', 'java', 'c++', 'react', 'angular', 'vue'],
            'databases': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis'],
            'cloud': ['aws', 'azure', 'gcp', 'docker', 'kubernetes'],
            'design': ['photoshop', 'illustrator', 'figma', 'sketch'],
            'project_management': ['agile', 'scrum', 'jira', 'confluence'],
        }
        
        skills = []
        text_lower = text.lower()
        
        # Look for skills section
        skills_section = self._find_section(text, ['skills', 'technical skills', 'technologies'])
        
        if skills_section:
            # Extract skills from dedicated section
            skill_text = skills_section.lower()
            for category, keywords in skill_categories.items():
                for keyword in keywords:
                    if keyword in skill_text:
                        # Determine skill level based on context
                        level = self._determine_skill_level(keyword, text)
                        skills.append(Skill(
                            name=keyword.title(),
                            level=level,
                            category=category
                        ))
        
        # Remove duplicates
        seen = set()
        unique_skills = []
        for skill in skills:
            if skill.name.lower() not in seen:
                seen.add(skill.name.lower())
                unique_skills.append(skill)
        
        return unique_skills
    
    def _extract_experience(self, text: str) -> list[Experience]:
        """Extract work experience from resume text."""
        experience_section = self._find_section(text, ['experience', 'work experience', 'employment'])
        
        if not experience_section:
            return []
        
        # Simple extraction - could be enhanced with more sophisticated parsing
        experiences = []
        
        # Split by common patterns that indicate new job entries
        job_entries = re.split(r'\n(?=[A-Z][^a-z]*\n)', experience_section)
        
        for entry in job_entries[:5]:  # Limit to 5 most recent
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if len(lines) >= 2:
                # First line is often title/company
                title_company = lines[0]
                duration = lines[1] if len(lines) > 1 else "Unknown duration"
                description = ' '.join(lines[2:]) if len(lines) > 2 else ""
                
                # Try to separate title and company
                if ' at ' in title_company:
                    title, company = title_company.split(' at ', 1)
                else:
                    title = title_company
                    company = "Unknown company"
                
                experiences.append(Experience(
                    title=title.strip(),
                    company=company.strip(),
                    duration=duration,
                    description=description,
                    key_achievements=[],  # Could extract bullet points
                    skills_used=[]  # Could extract from description
                ))
        
        return experiences
    
    def _extract_education(self, text: str) -> list[str]:
        """Extract education information."""
        education_section = self._find_section(text, ['education', 'academic background'])
        
        if not education_section:
            return []
        
        education_lines = [line.strip() for line in education_section.split('\n') if line.strip()]
        return education_lines[:5]  # Limit to 5 entries
    
    def _extract_certifications(self, text: str) -> list[str]:
        """Extract certifications."""
        cert_section = self._find_section(text, ['certifications', 'certificates', 'licenses'])
        
        if not cert_section:
            return []
        
        cert_lines = [line.strip() for line in cert_section.split('\n') if line.strip()]
        return cert_lines[:10]  # Limit to 10 certs
    
    def _find_section(self, text: str, keywords: list[str]) -> Optional[str]:
        """Find a section in the resume text by keywords."""
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(keyword.lower() in line_lower for keyword in keywords):
                # Found section header, extract content until next section
                section_lines = []
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    # Stop if we hit another section header
                    if (next_line and 
                        any(section in next_line.lower() for section in 
                            ['experience', 'education', 'skills', 'projects', 'certifications']) and
                        next_line != lines[i]):
                        break
                    if next_line:
                        section_lines.append(next_line)
                
                return '\n'.join(section_lines) if section_lines else None
        
        return None
    
    def _determine_skill_level(self, skill: str, text: str) -> SkillLevel:
        """Determine skill level based on context in resume."""
        text_lower = text.lower()
        
        # Look for experience indicators
        if any(phrase in text_lower for phrase in ['expert', f'expert in {skill}', f'{skill} expert']):
            return SkillLevel.EXPERT
        elif any(phrase in text_lower for phrase in ['advanced', f'advanced {skill}', f'{skill} advanced']):
            return SkillLevel.ADVANCED
        elif any(phrase in text_lower for phrase in [f'{skill} experience', 'years of', 'proficient']):
            return SkillLevel.INTERMEDIATE
        else:
            return SkillLevel.BEGINNER