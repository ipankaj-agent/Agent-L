from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path
from typing import Optional, Union
from xml.etree import ElementTree as ET
from docx import Document
from linkagent.llm.tailoring import generate_tailored_summary

logger = logging.getLogger(__name__)

PathLike = Union[str, os.PathLike[str]]
DEFAULT_RESUME_PATH = Path(__file__).resolve().parents[3] / "data" / "Resume.docx"
DEFAULT_RESUME_OUTPUT_PATH = Path(__file__).resolve().parents[3] / "data" / "Resume_Tailored.docx"


class ResumeTailor:
    """Tailor a resume.docx summary for ATS alignment using an LLM."""

    def __init__(self) -> None:
        pass

    def tailor_resume_docx(
        self,
        resume_path: PathLike,
        job_description: str,
        output_path: Optional[PathLike] = None,
    ) -> dict[str, str]:
        """Read a .docx resume, rewrite its summary using the LLM, and save it back."""
        # resume_path = Path(resume_path)
        resume_path = Path(DEFAULT_RESUME_PATH) if resume_path is None else Path(resume_path)
        output_path = Path(DEFAULT_RESUME_OUTPUT_PATH) if output_path is None else Path(output_path)

        if not resume_path.exists():
            raise FileNotFoundError(f"Resume file not found: {resume_path}")
        
        logger.info("Output path for tailored resume: %s", output_path)

        resume_text = self._read_docx_text(resume_path)
        current_summary = self._extract_summary_from_docx_text(resume_text)
        tailored_summary = generate_tailored_summary(
            job_description=job_description,
            current_summary=current_summary,
        )

        self._write_tailed_summary(resume_path, output_path, tailored_summary)
        return {"resume_path": str(output_path), "summary": tailored_summary}

    def _read_docx_text(self, resume_path: Path) -> str:
        with zipfile.ZipFile(resume_path) as archive:
            with archive.open("word/document.xml") as handle:
                xml_bytes = handle.read()

        root = ET.fromstring(xml_bytes)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", namespace):
            text = "".join(node.text or "" for node in paragraph.iter() if node.tag.endswith("}t"))
            if text.strip():
                paragraphs.append(text.strip())

        return "\n\n".join(paragraphs)

    def _extract_summary_from_docx_text(self, resume_text: str) -> str:
        paragraphs = [p.strip() for p in resume_text.split("\n\n") if p.strip()]

        headings = {
            "summary",
            "profile",
            "professional summary",
            "professional profile",
            "about",
            "overview",
            "objective",
        }

        for i, paragraph in enumerate(paragraphs):
            if paragraph.lower() in headings:
                if i + 1 < len(paragraphs):
                    return paragraphs[i + 1]

        return ""
    

    def _replace_paragraph_text(self, paragraph: ET.Element, text: str) -> None:
        namespace = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        }

        runs = paragraph.findall("w:r", namespace)

        if runs:
            first_run = runs[0]

            # Remove all runs after the first
            for run in runs[1:]:
                paragraph.remove(run)

            # Find or create the text element
            text_node = first_run.find("w:t", namespace)
            if text_node is None:
                text_node = ET.SubElement(
                    first_run,
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t",
                )

            text_node.text = text
        else:
            run = ET.SubElement(
                paragraph,
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r",
            )
            text_node = ET.SubElement(
                run,
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t",
            )
            text_node.text = text


    def _write_tailed_summary(
        self,
        resume_path: Path,
        output_path: Path,
        tailored_summary: str,
    ) -> None:
        """Rewrite the summary paragraph using python-docx."""

        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = Document(resume_path)

        headings = {
            "summary",
            "profile",
            "professional summary",
            "professional profile",
            "about",
            "overview",
            "objective",
        }

        paragraphs = doc.paragraphs

        for i, paragraph in enumerate(paragraphs):
            if paragraph.text.strip().lower() in headings:
                if i + 1 >= len(paragraphs):
                    raise ValueError("Summary paragraph not found.")

                target = paragraphs[i + 1]

                # Remove all existing runs while preserving paragraph properties.
                for run in target.runs[::-1]:
                    target._element.remove(run._element)

                target.add_run(tailored_summary)

                doc.save(output_path)
                return

        raise ValueError("Summary heading not found.")