# ResumeTool - Quick Start Guide

## 🚀 Getting Started

### 1. Activate the Virtual Environment and Set Python Path
```bash
source .venv/bin/activate
export PYTHONPATH=src
```

### 2. Run the Interactive Wizard
```bash
resumetool wizard
```

### 3. Or Use Specific Commands

#### Analyze a Resume
```bash
resumetool analyze resume.pdf
```

#### Discover Job Opportunities
```bash
resumetool discover "software engineer" --limit 10
resumetool discover --remote --location "San Francisco"
```

#### Find Job Matches for Your Resume
```bash
resumetool match resume.pdf --query "python developer"
resumetool match resume.pdf --remote --limit 5
```

#### Get Help
```bash
resumetool --help
resumetool match --help
```

## 🔑 Optional: Enhanced AI Features

For AI-powered analysis and matching, set your OpenAI API key:
```bash
export OPENAI_API_KEY="your_api_key_here"
```

## 📁 Supported File Formats

- **Resumes**: `.pdf`, `.docx`, `.txt`
- **Output**: DOCX, PDF (future), HTML (future)

## 🎯 Example Workflow

1. **Analyze your resume:**
   ```bash
   resumetool analyze my_resume.pdf
   ```

2. **Find matching jobs:**
   ```bash
   resumetool match my_resume.pdf --query "data scientist" --limit 10
   ```

3. **Discover opportunities:**
   ```bash
   resumetool discover "machine learning" --remote
   ```

## 🛠 Troubleshooting

- **Command not found?** → Make sure you activated the venv: `source .venv/bin/activate`
- **Import errors?** → Set PYTHONPATH: `export PYTHONPATH=src`
- **Module not found errors?** → Make sure both venv is active AND PYTHONPATH is set
- **No jobs found?** → Job APIs may be rate-limited; fallback system provides sample data

## 🔧 Quick Fix Script
Create this as `run.sh` for convenience:
```bash
#!/bin/bash
source .venv/bin/activate
export PYTHONPATH=src
resumetool "$@"
```
Then use: `./run.sh wizard`

---

**Need help?** Run `resumetool wizard` for interactive guidance!