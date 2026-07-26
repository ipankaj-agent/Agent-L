from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.linkagent.llm.filter import filter_job

class BaseEasyApply(ABC):
    """Abstract base class for Easy Apply submission flows."""
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 15000,
    ) -> None:
        self.headless = headless
        self.timeout = timeout
        self.max_steps = 8
        self.questions_answers: list[dict[str, Any]] = []
        self.job_title: str | None = None
        self.job_description: str | None = None
    
    @abstractmethod
    async def open_job(self, job_id: int) -> bool:
        """Open a specific job by ID.
        
        Args:
            job_id: The ID of the job to open
            
        Returns:
            True if the job was opened successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def open_first_job(self) -> bool:
        """Open the first job from the current jobs page.
        
        Returns:
            True if the job was opened successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_job_id(self) -> int | None:
        """Extract the job ID from the current page URL.
        
        Returns:
            The job ID if found, None otherwise
        """
        pass
    
    
    @abstractmethod
    async def limits(self) -> bool:
        """Check if the Easy Apply daily limit has been reached.
        
        Returns:
            True if the limit has been reached, False otherwise
        """
        pass
    
    @abstractmethod
    async def fill_current_step(self, resume_path: str | Path) -> bool:
        """Fill form fields in the current application step.
        
        Args:
            resume_path: Path to the resume file to upload if needed
            
        Returns:
            True if fields were filled successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def next(self) -> bool:
        """Advance to the next application step.
        
        Returns:
            True if advancement was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def submit(self) -> bool:
        """Submit the current application.
        
        Returns:
            True if submission was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def handle_post_submission(self) -> bool:
        """Handle any post-submission dialogs or confirmations.
        
        Returns:
            True if post-submission handling was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def dismiss_dialog(self) -> bool:
        """Dismiss any open dialogs.
        
        Returns:
            True if dismissal was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def open_next_job(self, href: str) -> bool:
        """Navigate to the next job.
        
        Args:
            href: The URL or identifier of the next job
            
        Returns:
            True if navigation was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def refresh_page(self) -> None:
        """Refresh the current page."""
        pass
    
    @abstractmethod
    async def resume_submission(self, resume_path: str | Path | None = None) -> bool:
        """Upload a resume file if a file input is present.
        
        Args:
            resume_path: Path to the resume file to upload
            
        Returns:
            True if the resume was uploaded successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def ensure_logged_in(self) -> bool:
        """Check if the user is logged in.
        
        Returns:
            True if logged in, False otherwise
        """
        pass

    def filter(self, job_description: str) -> bool:
        """Decide whether to skip or apply the job.
        
        Returns:
            True if Apply, False otherwise
        """
        return filter_job(job_description=job_description)
        