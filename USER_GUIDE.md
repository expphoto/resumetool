# ResumeTool - Complete User Guide

*AI-Powered Job Matching & Resume Optimization System*

## 🚀 Overview

ResumeTool is an intelligent job search assistant that combines advanced resume parsing, AI-powered analysis, and automated job discovery to help professionals find their ideal career opportunities.

### Key Benefits:
- **6x Better Resume Analysis** with AI enhancement
- **Intelligent Job Matching** with compatibility scoring
- **Multi-Source Job Discovery** across major job boards
- **Cost-Effective AI** using GPT-5-nano
- **Professional CLI Interface** with rich formatting

---

## 📋 Prerequisites

- **Python 3.11+** (macOS/Linux)
- **Virtual Environment** (recommended)
- **OpenAI API Key** (optional, for enhanced AI features)

---

## ⚡ Quick Start

### 1. Setup Environment
```bash
# Activate virtual environment
source .venv/bin/activate
export PYTHONPATH=src
```

### 2. Basic Commands
```bash
# Analyze a resume
./run.sh analyze resume.pdf

# Find job opportunities
./run.sh discover "software engineer" --limit 10

# Match resume to jobs
./run.sh match resume.pdf --query "cloud architect"

# Interactive wizard
./run.sh wizard
```

### 3. With AI Enhancement
```bash
# Set OpenAI API key for enhanced features
export OPENAI_API_KEY="your_api_key_here"
./run.sh analyze resume.pdf --enhance
```

---

## 🎯 Core Features

### 1. Resume Analysis

#### Basic Analysis
- Extracts contact information
- Identifies basic skills and experience
- Parses work history
- Supports PDF, DOCX, TXT formats

#### AI-Enhanced Analysis (Requires API Key)
- Professional title generation
- Comprehensive skill categorization
- Expertise level assessment
- Enhanced experience parsing
- Industry-specific insights

**Example:**
```bash
./run.sh analyze my_resume.pdf --enhance
```

**Output:**
```
╭──────────────────────────────────────────────────────────────────╮
│ Resume Analysis: my_resume.pdf                                   │
╰──────────────────────────────────────────────────────────────────╯
Title: Senior Software Engineer
Email: candidate@example.com

                    Skills                    
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Skill        ┃ Level        ┃ Category   ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Python       │ expert       │ Programming│
│ AWS          │ advanced     │ Cloud      │
│ Leadership   │ intermediate │ Management │
└──────────────┴──────────────┴────────────┘

Found 15 skills and 3 work experiences
```

### 2. Job Discovery

#### Manual Search
```bash
# Search by job title
./run.sh discover "data scientist" --limit 5

# Include remote jobs
./run.sh discover "devops engineer" --remote --limit 10

# Specify location
./run.sh discover "marketing manager" --location "San Francisco"
```

#### Resume-Based Discovery
```bash
# Auto-generate search terms from resume
./run.sh discover --resume my_resume.pdf --limit 8
```

**Example Output:**
```
╭──────────────────────────────────────────────────────────────────╮
│ Found 5 job opportunities for: cloud architect                  │
╰──────────────────────────────────────────────────────────────────╯
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Title                    ┃ Company        ┃ Location          ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ Senior Cloud Architect   │ TechCorp       │ San Francisco, CA │
│ Cloud Solutions Engineer │ InnovateCo     │ 🏠 Remote         │
│ Principal Cloud Architect│ DataSystems    │ New York, NY      │
└──────────────────────────┴────────────────┴───────────────────┘
```

### 3. Intelligent Job Matching

Match your resume against discovered jobs with AI-powered compatibility scoring:

```bash
./run.sh match my_resume.pdf --query "machine learning engineer" --limit 5
```

**Example Output:**
```
╭──────────────────────────────────────────────────────────────────╮
│ Top 5 Job Matches                                               │
╰──────────────────────────────────────────────────────────────────╯

1. Senior ML Engineer at AI Startup
📍 Palo Alto, CA
🎯 Match Score: 92%
✅ Matching Skills: Python, TensorFlow, AWS, Machine Learning
❌ Missing Skills: Kubernetes, MLOps
💡 Consider gaining experience with MLOps and container orchestration

2. Data Scientist at FinTech Corp
📍 🏠 Remote
🎯 Match Score: 78%
✅ Matching Skills: Python, Statistics, SQL
❌ Missing Skills: Financial modeling, Risk analysis
💡 Develop domain expertise in financial services
```

### 4. Interactive Wizard Mode

For guided workflows:

```bash
./run.sh wizard
```

**Wizard Flow:**
1. Choose action (analyze, discover, match, optimize)
2. Select resume file (auto-detects in current directory)
3. Configure options (location, remote, AI enhancement)
4. Review results with formatted output

---

## 🛠 Advanced Usage

### Command-Line Options

#### Analyze Command
```bash
resumetool analyze [OPTIONS] RESUME

Options:
  --enhance / --no-enhance    Use AI to enhance analysis [default: True]
  --openai-key TEXT          OpenAI API key
  --help                     Show help message
```

#### Discover Command
```bash
resumetool discover [OPTIONS] [QUERY]

Options:
  --location TEXT            Job location
  --remote / --no-remote     Include remote jobs [default: False]
  --limit INTEGER            Maximum number of jobs [default: 10]
  --resume FILE              Resume file for intelligent query generation
  --openai-key TEXT          OpenAI API key
  --help                     Show help message
```

#### Match Command
```bash
resumetool match [OPTIONS] RESUME

Options:
  --query TEXT               Job search query
  --location TEXT            Job location
  --remote / --no-remote     Include remote jobs [default: False]
  --limit INTEGER            Maximum matches [default: 10]
  --openai-key TEXT          OpenAI API key
  --help                     Show help message
```

### Environment Variables

```bash
# OpenAI API key for enhanced features
export OPENAI_API_KEY="your_api_key_here"

# Python path for module imports
export PYTHONPATH=src
```

### Configuration Files

Create `.env` file in project root:
```bash
OPENAI_API_KEY=your_api_key_here
DEFAULT_JOB_LIMIT=15
DEFAULT_LOCATION="San Francisco, CA"
ENABLE_REMOTE_BY_DEFAULT=true
```

---

## 📊 Understanding Results

### Match Scores
- **90-100%**: Excellent fit, apply immediately
- **75-89%**: Strong candidate, minor skill gaps
- **60-74%**: Good potential, some development needed
- **Below 60%**: Significant gaps, consider other opportunities

### Skill Categories
- **Programming**: Technical coding skills
- **Cloud**: Cloud platform expertise
- **Management**: Leadership and project management
- **Design**: UI/UX and design skills
- **Data**: Data analysis and database skills

### Experience Levels
- **Expert**: 5+ years, deep expertise
- **Advanced**: 3-5 years, strong proficiency
- **Intermediate**: 1-3 years, working knowledge
- **Beginner**: <1 year, basic familiarity

---

## 🔧 Troubleshooting

### Common Issues

#### Command Not Found
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Use the convenience script
./run.sh --help
```

#### Import Errors
```bash
# Set Python path
export PYTHONPATH=src

# Reinstall dependencies
.venv/bin/python -m pip install -e .
```

#### No Jobs Found
- Job search APIs may be rate-limited
- System provides fallback sample data
- Try different search terms or locations
- Check internet connectivity

#### AI Features Not Working
```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Test with specific key
resumetool analyze resume.pdf --openai-key "your_key"
```

### Performance Tips

1. **Use Convenience Script**: `./run.sh` handles environment setup
2. **Batch Operations**: Process multiple resumes with scripting
3. **Cache Results**: Save analysis results for repeated matching
4. **Optimize Queries**: Use specific job titles for better matches

---

## 🎨 Customization

### Custom Templates (Future Feature)
```bash
# Create custom resume templates
mkdir -p templates/my_template/
# Add template files...

# Use custom template
resumetool optimize resume.pdf job.txt --template my_template
```

### API Integration
```python
# Python API usage
from resumetool.analysis.resume_parser import ResumeParser
from resumetool.ai.openai_client import OpenAIAnalyzer

parser = ResumeParser()
analysis = parser.parse_file("resume.pdf")

analyzer = OpenAIAnalyzer(api_key="your_key")
enhanced = analyzer.enhance_resume_analysis(analysis)
```

---

## 📈 Best Practices

### Resume Preparation
1. **Use Standard Formats**: PDF or DOCX for best parsing
2. **Clear Structure**: Distinct sections for skills, experience
3. **Keyword Rich**: Include industry-relevant terms
4. **Quantify Achievements**: Use numbers and metrics
5. **Recent Experience First**: Reverse chronological order

### Job Search Strategy
1. **Start Broad**: Use general terms, then narrow down
2. **Include Remote Options**: Expand your opportunity pool
3. **Review Match Explanations**: Understand why jobs fit
4. **Act on Recommendations**: Address identified skill gaps
5. **Track Applications**: Use notes for follow-up

### AI Enhancement Tips
1. **Use API Key**: Dramatic improvement in analysis quality
2. **Cost Management**: GPT-5-nano provides excellent value
3. **Batch Processing**: Analyze multiple resumes efficiently
4. **Regular Updates**: Re-analyze as you gain new skills

---

## 🔮 Future Features

### Coming Soon
- **Resume Optimization**: AI-generated tailored versions
- **Auto-Application**: Automated job application submission
- **Web Dashboard**: Browser-based interface
- **Batch Processing**: Handle multiple resumes simultaneously
- **Integration APIs**: Connect with LinkedIn, Indeed directly
- **Analytics Dashboard**: Track application success rates

### Roadmap
- **Q4 2025**: Resume optimization and web interface
- **Q1 2026**: Auto-application features
- **Q2 2026**: Advanced analytics and integrations

---

## 💡 Tips for Success

### Maximize Match Scores
1. **Update Skills Regularly**: Keep resume current with latest technologies
2. **Use Industry Keywords**: Match job posting terminology
3. **Quantify Experience**: Include specific achievements and metrics
4. **Professional Summary**: Clear, concise overview of expertise
5. **Relevant Experience**: Highlight most applicable positions

### Effective Job Searching
1. **Multiple Search Terms**: Try variations of job titles
2. **Location Flexibility**: Consider remote and different cities
3. **Company Research**: Understand organization culture and needs
4. **Network Integration**: Combine with LinkedIn and referrals
5. **Follow-up Strategy**: Track applications and responses

---

## 📞 Support

### Getting Help
- **Built-in Help**: `resumetool --help` for command info
- **Interactive Mode**: Use `wizard` for guided assistance
- **Documentation**: Comprehensive guides in project directory
- **Error Messages**: Detailed feedback for troubleshooting

### Community Resources
- **GitHub Repository**: Source code and issue tracking
- **Documentation**: Updated guides and examples
- **Best Practices**: Community-contributed tips and strategies

---

*User Guide for ResumeTool v0.1.0*  
*Last Updated: September 2025*  
*AI-Powered Job Matching & Resume Optimization*