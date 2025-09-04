from typing import Optional, Sequence, List
from pathlib import Path
import sys
import os

try:
    import typer
except ModuleNotFoundError:
    print(
        "Missing dependency: typer.\n"
        "Quick fix: `python -m pip install 'typer[all]' rich`\n"
        "Or install the package: `python -m pip install -e '.[dev]'`",
        file=sys.stderr,
    )
    raise SystemExit(1)

from importlib import resources

# Import new modules
from resumetool.analysis.resume_parser import ResumeParser
from resumetool.discovery.job_search import JobSearchEngine
from resumetool.ai.openai_client import OpenAIAnalyzer
from resumetool.types import ResumeAnalysis, JobListing, JobMatch

app = typer.Typer(help="AI-powered job matching and resume optimization system.")


def _find_files(patterns: Sequence[str]) -> list[Path]:
    cwd = Path.cwd()
    files: list[Path] = []
    for pat in patterns:
        files.extend(sorted(cwd.glob(pat)))
    # unique while preserving order
    uniq: list[Path] = []
    seen: set[Path] = set()
    for f in files:
        if f.exists() and f not in seen:
            uniq.append(f)
            seen.add(f)
    return uniq


def _pick_from_list(title: str, items: list[str]) -> Optional[str]:
    # Lazy import rich only when needed (interactive path)
    try:
        from rich.console import Console
        from rich.prompt import IntPrompt
    except ModuleNotFoundError:
        print(
            "Missing dependency: rich. Install with: `python -m pip install rich`",
            file=sys.stderr,
        )
        return items[0] if items else None
    console = Console()
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    console.print(f"[bold]{title}[/bold]")
    for i, item in enumerate(items, start=1):
        console.print(f"  [cyan]{i}[/cyan]) {item}")
    idx = IntPrompt.ask("Select a number", default=1)
    if 1 <= idx <= len(items):
        return items[idx - 1]
    return None


def _available_templates() -> list[str]:
    try:
        tpl_root = resources.files("resumetool") / "templates"
        if not tpl_root.exists():
            return []
        return [p.name for p in tpl_root.iterdir() if p.is_dir()]
    except Exception:
        return []


@app.command()
def analyze(
    resume: Path = typer.Argument(..., exists=True, dir_okay=False),
    enhance: bool = typer.Option(True, help="Use AI to enhance analysis"),
    openai_key: Optional[str] = typer.Option(None, help="OpenAI API key", envvar="OPENAI_API_KEY")
):
    """Parse and analyze a resume file to extract skills and experience."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        
        console = Console()
        
        # Parse the resume
        parser = ResumeParser()
        with console.status("Parsing resume..."):
            analysis = parser.parse_file(str(resume))
        
        # Enhance with AI if requested and API key available
        if enhance and openai_key:
            with console.status("Enhancing analysis with AI..."):
                analyzer = OpenAIAnalyzer(api_key=openai_key)
                analysis = analyzer.enhance_resume_analysis(analysis)
        
        # Display results
        console.print(Panel(f"[bold]Resume Analysis: {resume.name}[/bold]", style="blue"))
        
        if analysis.name:
            console.print(f"[bold]Name:[/bold] {analysis.name}")
        if analysis.title:
            console.print(f"[bold]Title:[/bold] {analysis.title}")
        if analysis.email:
            console.print(f"[bold]Email:[/bold] {analysis.email}")
        
        if analysis.summary:
            console.print(f"\n[bold]Summary:[/bold]\n{analysis.summary}")
        
        # Skills table
        if analysis.skills:
            skills_table = Table(title="Skills")
            skills_table.add_column("Skill", style="cyan")
            skills_table.add_column("Level", style="green")
            skills_table.add_column("Category", style="yellow")
            
            for skill in analysis.skills:
                skills_table.add_row(
                    skill.name, 
                    skill.level.value,
                    skill.category or "N/A"
                )
            console.print(skills_table)
        
        # Experience
        if analysis.experience:
            console.print(f"\n[bold]Experience ({len(analysis.experience)} positions):[/bold]")
            for exp in analysis.experience:
                console.print(f"• [bold]{exp.title}[/bold] at [italic]{exp.company}[/italic] ({exp.duration})")
        
        console.print(f"\n[dim]Found {len(analysis.skills)} skills and {len(analysis.experience)} work experiences[/dim]")
        
    except Exception as e:
        typer.echo(f"Error analyzing resume: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def discover(
    query: Optional[str] = typer.Argument(None, help="Job search query"),
    location: str = typer.Option("", help="Job location"),
    remote: bool = typer.Option(False, help="Include remote jobs"),
    limit: int = typer.Option(10, help="Maximum number of jobs to find"),
    resume: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="Resume file for query generation"),
    openai_key: Optional[str] = typer.Option(None, help="OpenAI API key", envvar="OPENAI_API_KEY")
):
    """Discover job opportunities based on query or resume analysis."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        
        console = Console()
        
        # Generate search query from resume if provided
        if resume and not query:
            with console.status("Analyzing resume for job search terms..."):
                parser = ResumeParser()
                analysis = parser.parse_file(str(resume))
                
                if openai_key:
                    analyzer = OpenAIAnalyzer(api_key=openai_key)
                    search_terms = analyzer.generate_job_search_terms(analysis)
                    query = search_terms[0] if search_terms else "software engineer"
                else:
                    # Use basic terms from resume
                    if analysis.title:
                        query = analysis.title
                    elif analysis.skills:
                        query = analysis.skills[0].name
                    else:
                        query = "professional"
        
        if not query:
            query = typer.prompt("What type of job are you looking for?")
        
        # Search for jobs
        with console.status(f"Searching for {query} jobs..."):
            search_engine = JobSearchEngine()
            jobs = search_engine.search_jobs(
                query=query,
                location=location,
                remote=remote,
                limit=limit
            )
        
        if not jobs:
            console.print("[yellow]No jobs found. Try a different search query.[/yellow]")
            return
        
        # Display results
        console.print(Panel(f"[bold]Found {len(jobs)} job opportunities for: {query}[/bold]", style="green"))
        
        jobs_table = Table()
        jobs_table.add_column("Title", style="cyan")
        jobs_table.add_column("Company", style="white")
        jobs_table.add_column("Location", style="yellow")
        jobs_table.add_column("Source", style="dim")
        
        for job in jobs:
            location_text = f"🏠 {job.location}" if job.remote else job.location
            jobs_table.add_row(
                job.title,
                job.company,
                location_text,
                job.source
            )
        
        console.print(jobs_table)
        console.print(f"\n[dim]Use 'resumetool match' to see how well these jobs match your resume[/dim]")
        
    except Exception as e:
        typer.echo(f"Error discovering jobs: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def match(
    resume: Path = typer.Argument(..., exists=True, dir_okay=False),
    query: Optional[str] = typer.Option(None, help="Job search query"),
    location: str = typer.Option("", help="Job location"),
    remote: bool = typer.Option(False, help="Include remote jobs"),
    limit: int = typer.Option(10, help="Maximum number of job matches"),
    openai_key: Optional[str] = typer.Option(None, help="OpenAI API key", envvar="OPENAI_API_KEY")
):
    """Find and analyze job matches for your resume."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        
        console = Console()
        
        # Analyze resume
        with console.status("Analyzing your resume..."):
            parser = ResumeParser()
            analysis = parser.parse_file(str(resume))
            
            if openai_key:
                analyzer = OpenAIAnalyzer(api_key=openai_key)
                analysis = analyzer.enhance_resume_analysis(analysis)
        
        # Generate search query if not provided
        if not query:
            if openai_key:
                search_terms = analyzer.generate_job_search_terms(analysis)
                query = search_terms[0] if search_terms else "software engineer"
            elif analysis.title:
                query = analysis.title
            else:
                query = typer.prompt("What type of job are you looking for?")
        
        # Search for jobs
        with console.status(f"Finding {query} opportunities..."):
            search_engine = JobSearchEngine()
            jobs = search_engine.search_jobs(
                query=query,
                location=location,
                remote=remote,
                limit=limit * 2  # Get more to analyze
            )
        
        if not jobs:
            console.print("[yellow]No jobs found for matching.[/yellow]")
            return
        
        # Analyze matches
        matches = []
        with console.status("Analyzing job matches..."):
            for job in jobs:
                if openai_key:
                    match = analyzer.analyze_job_fit(analysis, job)
                else:
                    # Basic matching without AI
                    match = JobMatch(
                        job=job,
                        match_score=0.5,  # Neutral score
                        skill_match_score=0.5,
                        experience_match_score=0.5
                    )
                matches.append(match)
        
        # Sort by match score and limit results
        matches.sort(key=lambda m: m.match_score, reverse=True)
        matches = matches[:limit]
        
        # Display results
        console.print(Panel(f"[bold]Top {len(matches)} Job Matches[/bold]", style="green"))
        
        for i, match in enumerate(matches, 1):
            score_color = "green" if match.match_score >= 0.7 else "yellow" if match.match_score >= 0.5 else "red"
            
            console.print(f"\n[bold]{i}. {match.job.title}[/bold] at [italic]{match.job.company}[/italic]")
            console.print(f"📍 {match.job.location}")
            console.print(f"🎯 Match Score: [{score_color}]{match.match_score:.0%}[/{score_color}]")
            
            if match.matching_skills:
                console.print(f"✅ Matching Skills: {', '.join(match.matching_skills[:3])}")
            if match.missing_skills:
                console.print(f"❌ Missing Skills: {', '.join(match.missing_skills[:3])}")
            if match.recommendations:
                console.print(f"💡 {match.recommendations[0]}")
        
    except Exception as e:
        typer.echo(f"Error matching jobs: {e}", err=True)
        raise typer.Exit(1)


@app.command() 
def optimize(
    resume: Path = typer.Argument(..., exists=True, dir_okay=False),
    job_query: str = typer.Argument(..., help="Job title or company to optimize for"),
    output: Optional[str] = typer.Option(None, help="Output file path"),
    openai_key: Optional[str] = typer.Option(None, help="OpenAI API key", envvar="OPENAI_API_KEY")
):
    """Generate an optimized resume version for a specific job."""
    try:
        from rich.console import Console
        console = Console()
        
        if not openai_key:
            console.print("[red]OpenAI API key required for resume optimization[/red]")
            console.print("Set OPENAI_API_KEY environment variable or use --openai-key option")
            raise typer.Exit(1)
        
        # This is a simplified version - would need full job search integration
        console.print(f"[yellow]Resume optimization is under development[/yellow]")
        console.print(f"Would optimize {resume.name} for: {job_query}")
        console.print(f"Output: {output or 'optimized_resume.docx'}")
        
    except Exception as e:
        typer.echo(f"Error optimizing resume: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def apply(
    job_id: str = typer.Argument(..., help="Job ID to apply for"),
    auto: bool = typer.Option(False, help="Automatically submit application")
):
    """Track or auto-apply to a job (future feature)."""
    typer.echo(f"[yellow]Application management is under development[/yellow]")
    typer.echo(f"Would {'auto-apply' if auto else 'track application'} for job: {job_id}")


@app.command()
def dashboard():
    """Launch web interface for managing applications (future feature)."""
    typer.echo(f"[yellow]Web dashboard is under development[/yellow]")
    typer.echo("Would launch FastAPI web interface at http://localhost:8000")


@app.command()
def wizard():
    """Interactive guided mode for common tasks."""
    try:
        from rich.prompt import Prompt, Confirm
        from rich.console import Console
        from rich.panel import Panel
    except ModuleNotFoundError:
        print(
            "Missing dependency: rich. Install with: `python -m pip install rich`",
            file=sys.stderr,
        )
        raise SystemExit(1)

    console = Console()
    
    console.print(Panel(
        "[bold]Welcome to ResumeTool AI Job Matching System[/bold]\n"
        "This wizard will guide you through finding and matching job opportunities.",
        style="blue"
    ))

    action = Prompt.ask(
        "What would you like to do?",
        choices=["analyze", "discover", "match", "optimize"],
        default="match",
        show_choices=True,
    )

    # Find resume file
    candidates = _find_files(["*.pdf", "*.docx", "*.txt"])
    resume_path: Optional[str]
    if candidates:
        picked = _pick_from_list("Detected resume files:", [str(p) for p in candidates])
        resume_path = picked or Prompt.ask("Path to resume file")
    else:
        resume_path = Prompt.ask("Path to resume file")

    # Check for OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key and Confirm.ask("Do you have an OpenAI API key for enhanced AI analysis?"):
        openai_key = Prompt.ask("Enter your OpenAI API key", password=True)

    if action == "analyze":
        analyze(Path(resume_path), enhance=bool(openai_key), openai_key=openai_key)  # type: ignore[arg-type]
    
    elif action == "discover":
        query = Prompt.ask("Job search query (or press Enter to auto-generate from resume)", default="")
        location = Prompt.ask("Location (or press Enter for any location)", default="")
        remote = Confirm.ask("Include remote jobs?", default=False)
        limit = int(Prompt.ask("How many jobs to find?", default="10"))
        
        discover(
            query=query or None, 
            location=location,
            remote=remote,
            limit=limit,
            resume=Path(resume_path),  # type: ignore[arg-type]
            openai_key=openai_key
        )
    
    elif action == "match":
        query = Prompt.ask("Job search query (or press Enter to auto-generate from resume)", default="")
        location = Prompt.ask("Location (or press Enter for any location)", default="")
        remote = Confirm.ask("Include remote jobs?", default=False)
        limit = int(Prompt.ask("How many job matches to show?", default="5"))
        
        match(
            resume=Path(resume_path),  # type: ignore[arg-type]
            query=query or None,
            location=location,
            remote=remote,
            limit=limit,
            openai_key=openai_key
        )
    
    elif action == "optimize":
        if not openai_key:
            console.print("[red]OpenAI API key is required for resume optimization[/red]")
            return
        
        job_query = Prompt.ask("Job title or company to optimize for")
        output = Prompt.ask("Output file path", default="optimized_resume.docx")
        
        optimize(
            resume=Path(resume_path),  # type: ignore[arg-type]
            job_query=job_query,
            output=output,
            openai_key=openai_key
        )


if __name__ == "__main__":
    app()
