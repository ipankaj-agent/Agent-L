
from __future__ import annotations

import logging
import asyncio

from linkagent.browser.playwright_manager import PlaywrightManager
from linkagent.browser.session import BrowserSession
from linkagent.sites.linkedin.easy_apply import LinkedInEasyApply
from linkagent.workflows.tailor_resume import tailor_resume_workflow
from linkagent.sites.linkedin.auto_login import LinkedInAutoLogin
from linkagent.database.db import (
    save_job_application, 
    job_exists, 
    start_session, 
    finish_session, 
    get_unsubmitted_job_ids,
    update_job_application
)

__all__ = ["apply_job_workflow"]

logger = logging.getLogger(__name__)

RESUME_PATH = "data/Resume_base.docx"
RESUME_OUTPUT_PATH = "data"
OUTPUT_NAME = "Resume"


async def apply_job_workflow(platform: str, url: str, headless: bool = True, numJobs: int = 20, refill_failed: bool = False, linkedin_job_id: int | None = None) -> None:
    """Apply to the first LinkedIn job using Easy Apply."""

    if platform.lower() != "linkedin":
        logger.error("Currently, only LinkedIn platform is supported for job applications.")
        return
    platformApplier = LinkedInEasyApply(headless=headless)

    logger.info("Starting the LinkedIn Easy Apply flow for platform: %s", platform)
    logger.info("Refill failed applications: %s", refill_failed)
    if linkedin_job_id is not None:
        logger.info("Using provided LinkedIn job ID: %s", linkedin_job_id)
    
    if platformApplier.page is None:
        if not url:
            raise ValueError("Either a page or a URL must be provided")

        async with PlaywrightManager(headless=platformApplier.headless) as manager:
            async with BrowserSession(manager) as session:
                assert session.page is not None
                platformApplier.page = session.page
                await _run_application_flow(platformApplier, url, numJobs, refill_failed=refill_failed, linkedin_job_id=linkedin_job_id)
        logger.info("Completed the LinkedIn Easy Apply flow with a new browser session")
        return
    
    logger.info("Using the provided page for the LinkedIn Easy Apply flow")
    await _run_application_flow(platformApplier, url, numJobs, refill_failed=refill_failed, linkedin_job_id=linkedin_job_id)

async def _run_application_flow(platformApplier: LinkedInEasyApply, url: str | None = None, numJobs: int = 20, refill_failed: bool = False, linkedin_job_id: int | None = None) -> None:
    """Run LinkedIn Easy Apply on all available jobs."""

    if platformApplier.page is None:
        return

    if url:
        await platformApplier.page.goto(url, wait_until="domcontentloaded")
        await platformApplier.page.wait_for_timeout(3000)
        logger.info("Opened LinkedIn jobs page: %s", url)

    db_session_id: int = start_session()

    jobs_to_refill: set[int] = set()

    if refill_failed:
        jobs_to_refill = set(get_unsubmitted_job_ids())
        logger.info("Found %d jobs to refill.", len(jobs_to_refill))

        if not jobs_to_refill:
            logger.info("No pending jobs to refill.")
            finish_session(db_session_id)
            return

    while True:        

        if await platformApplier.ensure_logged_in():
            logger.warning("Sign-in prompt detected. Please sign in to LinkedIn.")
            break

        numJobs -= 1
        logger.info("Remaining jobs to apply for: %d", numJobs)
        if numJobs <= 0:
            logger.warning("Reached the maximum number of jobs to apply for. Exiting.")
            break
        platformApplier.questions_answers = []
        platformApplier.job_title = None
        platformApplier.job_description = None

        # Open the requested job directly when a LinkedIn job ID is provided.
        if linkedin_job_id is not None:
            logger.info("Opening provided job with job ID: %s", linkedin_job_id)
            await platformApplier.open_job(linkedin_job_id)
            job_id: int | None = linkedin_job_id
        elif refill_failed and jobs_to_refill:
            logger.info("Refilling failed applications. Jobs to refill: %s", jobs_to_refill)
            job_id = jobs_to_refill.pop()
            logger.info("Opening job with job ID: %s", job_id)
            await platformApplier.open_job(job_id)
        elif not await platformApplier.open_first_job():
            logger.warning("No jobs found.")
            await platformApplier.page.wait_for_timeout(2000)
            return
        else:
            job_id = platformApplier.get_job_id()
        
        logger.info("Processing current job with job ID: %s", job_id)

        if linkedin_job_id is None and ((not refill_failed and job_exists(job_id)) if job_id is not None else False):
            logger.info("Job ID %s already exists in the database. Skipping.", job_id)
            await platformApplier.dismiss_dialog()
            await platformApplier.refresh_page()
            continue
        
        logger.info("Job ID %s . Proceeding with application.", job_id)

        #Website Limitations 
        if await platformApplier.limits():
            break
        
        # Skip jobs without Easy Apply
        if not await platformApplier.click_easy_apply():
            logger.warning("No Easy Apply button found.")
            await _persist_application(platformApplier, linkedin_job_id=job_id, title=platformApplier.job_title, description=platformApplier.job_description, status="no_easy_apply", refill_failed=refill_failed)
        elif await platformApplier.limits():
            break  #Website Limitations to apply jobs
        elif platformApplier.filter(platformApplier.job_description):
            logger.warning("LLM Filtered job  ")
            await _persist_application(platformApplier, linkedin_job_id=job_id, title=platformApplier.job_title, description=platformApplier.job_description, status="llm_filtered", refill_failed=refill_failed)
        else:
            await platformApplier.page.wait_for_timeout(2000)

            logger.info("Starting Easy Apply flow")

            try:
                async with asyncio.timeout(300):  # 5 minutes

                    tailored_resume_result = tailor_resume_workflow(
                        resume_path=RESUME_PATH,
                        job_description=platformApplier.job_description or "",
                        output_dir=RESUME_OUTPUT_PATH,
                        output_name=OUTPUT_NAME,
                    )

                    for i in range(platformApplier.max_steps):
                        logger.info("Filling current Step, Step %d of %d", i + 1, platformApplier.max_steps)
                        if await platformApplier.fill_current_step(resume_path=tailored_resume_result['pdf_path']):
                            logger.info("Filled current step,  Opening next step...")
                            if await platformApplier.next():
                                continue
                        
                        logger.info("Reached the final step or could not proceed to next step.")
                        if await platformApplier.submit():
                            logger.info("Application submitted.")
                            await _persist_application(platformApplier, linkedin_job_id=job_id, title=platformApplier.job_title, description=platformApplier.job_description, status="submitted", refill_failed=refill_failed)
                            break

                        logger.warning("Could not continue application.")
                        await _persist_application(platformApplier, linkedin_job_id=job_id, title=platformApplier.job_title, description=platformApplier.job_description, status="could_not_continue", refill_failed=refill_failed)
                        break
            except TimeoutError:
                logger.exception("Application timed out.")
                await _persist_application(
                    platformApplier,
                    linkedin_job_id=job_id,
                    title=platformApplier.job_title,
                    description=platformApplier.job_description,
                    status="timeout",
                    refill_failed=refill_failed
                )
            except Exception as exc:
                logger.exception("Error during Easy Apply flow: %s", exc)
                await _persist_application(platformApplier, linkedin_job_id=job_id, title=platformApplier.job_title, description=platformApplier.job_description, status="flow_error", refill_failed=refill_failed)
                
            await platformApplier.handle_post_submission()

        if linkedin_job_id is not None:
            logger.info("Completed the requested job. Exiting.")
            break

        await platformApplier.dismiss_dialog()
        await platformApplier.refresh_page()
        logger.info("Moving to next job...")

    #Finish DB Session
    finish_session(db_session_id)



async def _persist_application(platformApplier: LinkedInEasyApply, linkedin_job_id: int, title: str | None, description: str | None, status: str, refill_failed: bool=False) -> None:
    """Persist the current application to the database when it is submitted."""
    if refill_failed:
        logger.info("Refilling failed application for job ID: %s with status: %s", linkedin_job_id, status)
        update_job_application(
            linkedin_job_id=linkedin_job_id,
            title=title or "Untitled job",
            description=description or "No description available",
            questions=platformApplier.questions_answers,
            resume_id=None,
            status=status
        )
    else:
        logger.info("Persisting application for job ID: %s with Status: %s", linkedin_job_id, status)
        save_job_application(
        linkedin_job_id=linkedin_job_id,
        title=title or "Untitled job",
        description=description or "No description available",
        questions=platformApplier.questions_answers,
        resume_id=None,
        status=status
    )
    logger.info("Saved application to the database for %s with status : %s", title or linkedin_job_id, status)


async def login_flow(url, headless: bool = True) -> None:
    async with PlaywrightManager(headless=headless) as manager:
        async with BrowserSession(manager) as session:
            assert session.page is not None
            loginEntity = LinkedInAutoLogin(page=session.page, url=url)
            await loginEntity.login()
            input("Press Enter after completing the login process to continue...")
