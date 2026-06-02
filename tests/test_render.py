"""Unit tests for the HTML/DOCX/PDF renderers."""
import json
import zipfile
from pathlib import Path

import pytest

from resumetool.render import render_docx, render_html, render_pdf
from resumetool.types import JobExperience, Resume


def _sample_resume() -> Resume:
    return Resume(
        full_name="Jane Smith",
        contact_info_redacted=True,
        summary="Senior engineer with 10 years of experience.",
        skills=["Python", "AWS", "Kubernetes"],
        experience=[
            JobExperience(
                company="Acme",
                title="Staff Engineer",
                duration="2020 - present",
                bullet_points=["Built X", "Reduced Y by 50%"],
            ),
        ],
        education=["B.S. CS, State University, 2014"],
        certifications=["AWS SAA"],
    )


@pytest.fixture
def resume_json(tmp_path) -> Path:
    p = tmp_path / "resume.json"
    p.write_text(json.dumps(_sample_resume().model_dump()))
    return p


def test_render_html_creates_file_and_copies_css(resume_json, tmp_path):
    out = Path(render_html(resume_json, output_path=tmp_path / "r.html"))
    assert out.exists()
    html = out.read_text()
    assert "Jane Smith" in html
    assert "Staff Engineer" in html
    assert "Built X" in html
    # CSS asset must be alongside the HTML
    assert (tmp_path / "styles.css").exists()
    assert "stylesheet" in html


def test_render_html_redacts_contact(resume_json, tmp_path):
    out = Path(render_html(resume_json, output_path=tmp_path / "r.html"))
    html = out.read_text()
    assert "redacted for privacy" in html.lower()
    # No @ symbol in body
    body = html.split("<body>")[1]
    assert "@" not in body


def test_render_html_unknown_template_raises(resume_json, tmp_path):
    with pytest.raises(FileNotFoundError):
        render_html(resume_json, template="does-not-exist", output_path=tmp_path / "r.html")


def test_render_html_missing_resume_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_html(tmp_path / "missing.json", output_path=tmp_path / "r.html")


def test_render_html_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid")
    with pytest.raises(Exception):
        render_html(bad, output_path=tmp_path / "r.html")


def test_render_docx_creates_valid_zip(resume_json, tmp_path):
    out = Path(render_docx(resume_json, output_path=tmp_path / "r.docx"))
    assert out.exists()
    # DOCX is a zip; verify it opens
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "word/document.xml" in names


def test_render_docx_default_path(resume_json):
    out = Path(render_docx(resume_json))
    assert out.exists()
    assert out.suffix == ".docx"
    out.unlink()


def test_render_pdf_without_weasyprint_raises_actionable_error(resume_json, tmp_path, monkeypatch):
    """If WeasyPrint is not installed the error must be helpful."""
    html_path = render_html(resume_json, output_path=tmp_path / "r.html")
    # Force the weasyprint import to fail
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint" or name.startswith("weasyprint."):
            raise ImportError("simulated missing weasyprint")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match=r"WeasyPrint"):
        render_pdf(html_path, output_path=tmp_path / "r.pdf")
