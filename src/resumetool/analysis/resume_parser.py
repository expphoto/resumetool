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
        original_lines = text.split('\n')
        lower_lines = [line.lower() for line in original_lines]

        def _is_decorative(s: str) -> bool:
            s = s.strip()
            return bool(s) and all(c in "-=*_~" for c in s)

        for i, line in enumerate(lower_lines):
            stripped = line.strip().lstrip('*#').strip()
            if not any(
                stripped == kw or stripped.startswith(kw + ':') or stripped.startswith(kw + ' ')
                for kw in summary_keywords
            ):
                continue
            # Get next few non-decorative, non-header lines as summary
            summary_lines = []
            for j in range(i + 1, min(i + 6, len(original_lines))):
                raw = original_lines[j].strip()
                if not raw:
                    continue
                if _is_decorative(raw):
                    continue
                low = lower_lines[j]
                if any(
                    low == sec or low.startswith(sec + ':') or low.startswith(sec + ' ')
                    for sec in ['experience', 'education', 'skills', 'projects', 'certifications']
                ):
                    break
                summary_lines.append(raw)

            if summary_lines:
                return ' '.join(summary_lines)

        return None
    
    def _extract_skills(self, text: str) -> list[Skill]:
        """Extract skills from resume text."""
        # Common skill categories and keywords
        skill_categories = {
            'programming': [
                'python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'go', 'golang',
                'rust', 'ruby', 'php', 'swift', 'kotlin', 'react', 'angular', 'vue',
                'node', 'django', 'flask', 'fastapi', 'spring', 'grpc', 'graphql',
            ],
            'databases': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'dynamodb', 'elasticsearch'],
            'cloud': [
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'k8s', 'helm', 'terraform',
                'ansible', 'jenkins', 'github actions', 'circleci', 'istio', 'linkerd',
                'ec2', 'eks', 's3', 'lambda', 'vpc', 'iam', 'cloudformation', 'sre',
            ],
            'data': ['pandas', 'numpy', 'spark', 'hadoop', 'kafka', 'airflow', 'dbt', 'snowflake'],
            'design': ['photoshop', 'illustrator', 'figma', 'sketch'],
            'project_management': ['agile', 'scrum', 'jira', 'confluence'],
        }
        
        skills = []

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

        # Drop decorative separator lines (e.g. "------")
        def _is_decorative(s: str) -> bool:
            s = s.strip()
            return bool(s) and all(c in "-=*_~" for c in s)

        if not experience_section:
            # Fallback: if no Experience header, look for indented "- " bullet
            # lines anywhere in the document — common in DOCX exports.
            bullet_lines = [
                ln[2:].strip() if ln.strip().startswith("- ") else ln.strip()
                for ln in text.split('\n')
                if ln.strip().startswith("- ")
            ]
            if bullet_lines:
                return [Experience(
                    title="Experience",
                    company="",
                    duration="",
                    description="\n".join(bullet_lines),
                )]
            return []

        # Simple extraction - could be enhanced with more sophisticated parsing
        experiences = []

        # Split by common patterns that indicate new job entries
        job_entries = re.split(r'\n(?=[A-Z][^a-z]*\n)', experience_section)

        for entry in job_entries[:5]:  # Limit to 5 most recent
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            lines = [line for line in lines if not _is_decorative(line)]
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
        """Find a section in the resume text by keywords.

        Returns the section's text including any inline content on the
        header line (e.g. ``Skills: Python, Go, AWS``).

        A keyword is treated as a section header only when the line
        starts with the keyword (allowing a leading label like ``**``,
        whitespace, or a ``#`` markdown prefix) — not when it appears
        inside running prose such as ``"Experienced engineer"``.
        """

        lines = text.split('\n')
        stop_headers = [
            'experience', 'education', 'skills', 'projects',
            'certifications', 'summary', 'cover letter',
        ]
        # Sort longer keywords first to avoid "skills" matching "technical skills"
        sorted_keywords = sorted(keywords, key=lambda k: -len(k))
        sorted_stop = sorted(stop_headers, key=lambda k: -len(k))

        def _is_header_line(raw_line: str, kws: list[str]) -> str | None:
            """Return the matching keyword if `raw_line` is a section header."""
            stripped = raw_line.strip().lstrip('*#').strip()
            lower = stripped.lower()
            for kw in kws:
                kw_l = kw.lower()
                if lower == kw_l:
                    return kw
                if lower.startswith(kw_l + ':') or lower.startswith(kw_l + ' '):
                    return kw
            return None

        for i, line in enumerate(lines):
            matched = _is_header_line(line, sorted_keywords)
            if not matched:
                continue
            section_lines = []
            # Pull inline content off the header line
            header_stripped = line.strip().lstrip('*#').strip()
            idx = header_stripped.lower().find(matched.lower())
            if idx >= 0:
                inline = header_stripped[idx + len(matched):].lstrip(" :\t-")
                if inline:
                    section_lines.append(inline)

            # Walk forward until we hit another section header
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                stop_match = _is_header_line(next_line, sorted_stop)
                if stop_match and stop_match.lower() != matched.lower():
                    break
                section_lines.append(next_line)

            if section_lines:
                return '\n'.join(section_lines)
            return None

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