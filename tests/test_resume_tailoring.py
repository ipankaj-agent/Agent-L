from __future__ import annotations

import logging
import zipfile
import pytest
from pathlib import Path
from linkagent.resume.tailoring import ResumeTailor
from linkagent.workflows.tailor_resume import tailor_resume_workflow

logger = logging.getLogger(__name__)


def test_tailor_resume_docx_writes_to_output_path(monkeypatch):
    source_path_str = "data/Resume_base.docx"
    target_path_str = "data/output_resume.docx"

    source_path = Path(source_path_str)
    target_path = Path(target_path_str)

    assert source_path.exists()

    monkeypatch.setattr(
        "linkagent.resume.tailoring.generate_tailored_summary",
        lambda **kwargs: (
            "Profile rewritten for a target role with relevant ATS keywords."
        ),
    )

    logger.info("Testing tailor_resume_docx with source: %s and target: %s", source_path_str, target_path_str)

    try:
        result = ResumeTailor().tailor_resume_docx(
            resume_path=source_path_str,
            job_description=(
                "Candidate should have strong resume tailoring and keyword optimization skills."
            ),
            output_path=target_path_str,
        )

        assert result["resume_path"] == str(target_path)
        assert result["summary"] == (
            "Profile rewritten for a target role with relevant ATS keywords."
        )

        assert target_path.exists()

        with zipfile.ZipFile(target_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")

        assert (
            "Profile rewritten for a target role with relevant ATS keywords."
            in document_xml
        )

    finally:
        # Clean up after the test
        if target_path.exists():
            target_path.unlink()


def test_tailor_resume_docx_raises_file_not_found(tmp_path):
    missing_path = tmp_path / "missing_resume.docx"

    with pytest.raises(FileNotFoundError, match="Resume file not found"):
        ResumeTailor().tailor_resume_docx(
            missing_path,
            job_description="Any job description.",
        )


def test_tailor_resume_workflow_creates_docx_and_pdf(tmp_path, monkeypatch):
    source_path = "data/Resume_base.docx"
    output_dir = tmp_path

    monkeypatch.setattr(
        "linkagent.resume.tailoring.generate_tailored_summary",
        lambda **kwargs: "Profile rewritten for a target role with relevant ATS keywords.",
    )

    result = tailor_resume_workflow(
        resume_path=source_path,
        job_description="Python developer with automation experience",
        output_dir=output_dir,
    )

    assert Path(result["docx_path"]).exists()
    assert Path(result["pdf_path"]).exists()
    assert result["summary"] == "Profile rewritten for a target role with relevant ATS keywords."
