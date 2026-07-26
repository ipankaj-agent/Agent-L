from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Union
from xml.etree import ElementTree as ET
import platform
import shutil
import subprocess
from docx2pdf import convert as docx2pdf_convert

from linkagent.resume.tailoring import ResumeTailor

__all__ = ["tailor_resume_workflow"]

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESUME_PATH = REPO_ROOT / "data" / "Resume.docx"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data"


def tailor_resume_workflow(
    resume_path: PathLike | None = None,
    job_description: str = "",
    output_dir: PathLike | None = None,
    output_name: str = "Resume_Tailored",
) -> dict[str, str]:
    """Tailor a resume document and export a PDF copy of the result."""
    if not job_description.strip():
        raise ValueError("job_description must be provided")

    source_path = Path(DEFAULT_RESUME_PATH if resume_path is None else resume_path)
    output_folder = Path(DEFAULT_OUTPUT_DIR if output_dir is None else output_dir)
    output_folder.mkdir(parents=True, exist_ok=True)


    assert source_path.exists(), f"Source resume file does not exist: {source_path}"

    docx_output_path = output_folder / f"{output_name}.docx"
    pdf_output_path = output_folder / f"{output_name}.pdf"

    logger.info("Tailoring resume from %s into %s", source_path, docx_output_path)
    result = ResumeTailor().tailor_resume_docx(
        resume_path=source_path,
        job_description=job_description,
        output_path=docx_output_path,
    )


    _convert_docx_to_pdf(docx_output_path, pdf_output_path)

    return {
        "docx_path": str(docx_output_path),
        "pdf_path": str(pdf_output_path),
        "summary": result["summary"],
    }


def _convert_docx_to_pdf(docx_path: str | Path, pdf_path: str | Path) -> None:
    """Convert DOCX to PDF preserving formatting."""

    docx_path = Path(docx_path).resolve()
    pdf_path = Path(pdf_path).resolve()

    system = platform.system()

    if system == "Windows":
        _convert_windows(docx_path, pdf_path)
        return

    if system in ("Linux", "Darwin"):
        _convert_libreoffice(docx_path, pdf_path)
        return

    raise RuntimeError(f"Unsupported platform: {system}")


def _convert_windows(docx_path: Path, pdf_path: Path) -> None:
    """Use Microsoft Word via docx2pdf."""

    try:
        docx2pdf_convert(str(docx_path), str(pdf_path))
    except Exception as e:
        logger.exception("Failed to convert DOCX to PDF on Windows: %s", e)
        raise RuntimeError(
            "Failed to convert DOCX to PDF. "
            "Microsoft Word must be installed on Windows."
        ) from e


def _convert_libreoffice(docx_path: Path, pdf_path: Path) -> None:
    """Use LibreOffice headless."""

    soffice = shutil.which("soffice") or shutil.which("libreoffice")

    if soffice is None:
        raise RuntimeError(
            "LibreOffice is not installed. "
            "Install LibreOffice to enable PDF conversion."
        )

    subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            str(docx_path),
            "--outdir",
            str(pdf_path.parent),
        ],
        check=True,
    )

    generated = pdf_path.parent / f"{docx_path.stem}.pdf"

    if generated != pdf_path:
        generated.replace(pdf_path)

