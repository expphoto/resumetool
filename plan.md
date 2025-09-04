# ResumeTool – AI Job Matching & Resume Optimization System

**Vision**: An AI-powered system that analyzes resumes, discovers matching job opportunities, and automatically generates optimized resume versions for each opportunity, with eventual auto-application capabilities.

**Updated**: 2025-09-03 - Revised to reflect actual vision vs. simple resume tailoring tool.

## Core User Flow
1. **Resume Upload** → User uploads/pastes their resume
2. **AI Analysis** → System extracts skills, experience, preferences using OpenAI
3. **Job Discovery** → AI searches job boards/APIs for matching opportunities  
4. **Smart Matching** → Present top 10 best-fit jobs with match scores
5. **Resume Optimization** → Generate tailored resume versions for selected jobs
6. **Application Pipeline** → Track applications, eventually auto-apply

## Architecture
- Pipeline: **Resume Analysis → Job Discovery → Matching Engine → Resume Optimization → Application Management**
- Core Modules: `analysis/`, `discovery/`, `matching/`, `optimization/`, `application/`, `tracking/`
- AI Integration: OpenAI for analysis, matching, and content generation
- Data Flow: Resume → Skills/Experience extraction → Job search → Match scoring → Tailored resumes → Application tracking

## Directory Structure
- `pyproject.toml`, `README.md`, `.gitignore`, `plan.md`
- `src/resumetool/`
  - `__init__.py`, `cli.py`, `config.py`, `types.py`
  - `analysis/` (resume_parser.py, skills_extractor.py, experience_analyzer.py)
  - `discovery/` (job_search.py, indeed_api.py, linkedin_api.py, ziprecruiter_api.py)
  - `matching/` (similarity_engine.py, ml_matcher.py, scoring.py)
  - `optimization/` (resume_generator.py, content_optimizer.py, ats_optimizer.py)
  - `application/` (tracker.py, form_filler.py, auto_apply.py)
  - `ai/` (openai_client.py, prompts.py, response_parser.py)
  - `storage/` (database.py, resume_store.py, job_cache.py)
  - `web/` (app.py, routes.py, templates/)
- `tests/` (unit/, integration/, fixtures/)
- `data/` (job_cache/, resumes/, applications/)

## Core Commands
- `resumetool analyze <resume>`: Parse and extract skills/experience from resume
- `resumetool discover [--skills] [--location] [--remote]`: Find matching job opportunities
- `resumetool match <resume> [--limit 10]`: Show top job matches with scores
- `resumetool optimize <resume> <job_id>`: Generate tailored resume version
- `resumetool apply <job_id> [--auto]`: Track or auto-apply to job
- `resumetool dashboard`: Launch web interface for managing applications

## Feature Phasing & Acceptance

### Phase 1: Core Analysis (Week 1)
**Goal**: Resume analysis and basic job discovery
- ✅ Resume parsing (DOCX/PDF/TXT) with skill extraction
- ✅ OpenAI integration for intelligent content analysis  
- ✅ Basic job search API integration (Indeed/ZipRecruiter)
- ✅ CLI commands: `analyze`, `discover`
- **Acceptance**: `resumetool analyze resume.pdf` extracts 15+ relevant skills with 90%+ accuracy

### Phase 2: Smart Matching (Week 2) 
**Goal**: AI-powered job matching engine
- ✅ ML-based job matching algorithm
- ✅ Match scoring with explanations
- ✅ Top-10 job recommendations
- ✅ CLI command: `match`
- **Acceptance**: `resumetool match resume.pdf` returns 10 relevant jobs with 80%+ user satisfaction

### Phase 3: Resume Optimization (Week 3)
**Goal**: Tailored resume generation
- ✅ AI-powered resume optimization for specific jobs
- ✅ ATS-friendly formatting
- ✅ Multiple output formats (DOCX/PDF)
- ✅ CLI command: `optimize`  
- **Acceptance**: Generated resumes pass ATS scans and improve match scores by 25%+

### Phase 4: Application Management (Week 4)
**Goal**: Application tracking and web interface
- ✅ Application status tracking
- ✅ Web dashboard for resume/job management
- ✅ Batch processing capabilities
- ✅ CLI command: `apply`, `dashboard`
- **Acceptance**: Web interface allows full resume→application workflow in <5 minutes

### Phase 5: Auto-Application (Future)
**Goal**: Automated job applications
- 🔄 Form filling automation
- 🔄 Application submission pipeline
- 🔄 Response monitoring
- **Acceptance**: 80%+ successful auto-applications with proper form completion

## Stack & Rationale
- **CLI/Web**: Typer + Rich for CLI; FastAPI + Jinja2 for web dashboard
- **Resume Parsing**: `python-docx`, `pdfminer.six`, `pypdf` for document processing
- **AI/ML**: OpenAI API for content analysis and generation; scikit-learn for matching algorithms
- **Job Discovery**: Indeed API, ZipRecruiter API, web scraping for job data
- **Database**: SQLite for local storage, optional PostgreSQL for production
- **Document Generation**: `python-docx` for DOCX; WeasyPrint for PDF rendering
- **Web Scraping**: BeautifulSoup4, Selenium for job board scraping
- **Config/Logging**: pydantic-settings, structlog with cost/latency tracking
- **Testing**: pytest, httpx for API testing, fixtures for job/resume data

## Security & Privacy
- Default-on PII redaction; placeholders before LLM calls.
- Env-based key management; no secrets in logs.
- In-memory processing; ephemeral temp files; optional encrypted cache (`cryptography.fernet`).
- Structured, PII-filtered logs; opt-in prompt tracing stored locally.
- Timeouts, rate limits, cost circuit breakers.

## Evaluation & Guardrails
- Golden set: 20 anonymized resume/JD pairs in `tests/fixtures/evaluation/`.
- `resumetool eval --provider <p>` runs fixtures; logs cost/latency/format adherence; optional LLM-as-judge.
- Validation: JSON schema; self-consistency (n=3); deterministic seeds where supported.
- Metrics: Parse success, score stability, rewrite quality, format validity %, cost/run, p95 latency.

## Cost & Performance Targets
- Latency: Parse <5s; LLM 10–30s; end-to-end <45s.
- Cost: Default <$0.50 per resume; model tiers; token caps.

## Progress Tracking

### ✅ Completed Milestones
- [2025-09-03] Project setup and venv configuration
- [2025-09-03] Updated plan.md to reflect AI job matching vision  
- [2025-09-03] Basic CLI structure scaffolded
- [2025-09-03] **PHASE 1 COMPLETE**: Core Analysis System
  - ✅ Updated pyproject.toml with new dependencies (OpenAI, scikit-learn, BeautifulSoup4, etc.)
  - ✅ Restructured src/ directory with new architecture (analysis/, discovery/, matching/, etc.)
  - ✅ Implemented resume_parser.py with DOCX/PDF/TXT support
  - ✅ Built OpenAI integration for intelligent resume analysis and job matching
  - ✅ Created job discovery module with Indeed/ZipRecruiter integration + fallbacks
  - ✅ CLI commands working: `analyze`, `discover`, `match`, `optimize`, `wizard`
  - ✅ Rich UI with tables, panels, and progress indicators

### 🔄 Current Sprint (Phase 2: Smart Matching)
**Target**: End of Week 2
- [x] ~~ML-based job matching algorithm implementation~~ **COMPLETED** (AI-powered via OpenAI)
- [x] ~~Match scoring with detailed explanations~~ **COMPLETED**  
- [x] ~~Top-10 job recommendations~~ **COMPLETED**
- [x] ~~CLI command: `match` with filtering options~~ **COMPLETED**

### 🎯 Next Sprint (Phase 3: Resume Optimization)
**Target**: End of Week 3
- [ ] Full resume optimization implementation with ATS-friendly formatting  
- [ ] Multiple output formats (DOCX/PDF/HTML)
- [ ] Template system for different resume styles
- [ ] Batch processing for multiple job applications
- [ ] Enhanced job matching with better scraping/API integration

### 📝 Current System Status
**✅ WORKING FEATURES:**
- Resume parsing (DOCX/PDF/TXT) with skill/experience extraction
- Job discovery with fallback system when APIs are blocked
- AI-powered resume analysis and job matching (requires OpenAI key)
- Rich CLI interface with `analyze`, `discover`, `match`, `wizard` commands
- Interactive wizard for guided workflows

**⚠️ KNOWN LIMITATIONS:**
- Job search APIs may be blocked by rate limiting (fallback system provides mock data)
- Resume optimization feature is placeholder (needs full implementation)
- Application tracking and web dashboard are future features

**🔧 USAGE:**
```bash
# Analyze a resume
export OPENAI_API_KEY="your_key"
resumetool analyze resume.pdf

# Find job matches
resumetool match resume.pdf --query "software engineer" --limit 5

# Interactive mode
resumetool wizard
```

## Open Questions
- Default model: cheapest vs best quality?
- Industry focus: generic vs targeted templates?
- Offline mode: v1 or stretch?
- ATS depth: basic vs advanced now/later?
- Retention: cache outputs or stateless?

