from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse
from playwright.async_api import Page
import logging
from pathlib import Path

from linkagent.sites.BaseApply import BaseEasyApply
from linkagent.llm.question_answering import answer_question

logger = logging.getLogger(__name__)

class LinkedInEasyApply(BaseEasyApply):
    """Coordinate a simple LinkedIn Easy Apply submission flow."""

    def __init__(
        self,
        page: Page | None = None,
        *,
        headless: bool = True,
        timeout: int = 15000,
    ) -> None:
        self.page = page
        self.headless = headless
        self.timeout = timeout
        self.max_steps = 8
        self.questions_answers: list[dict[str, Any]] = []
        self.job_title: str | None = None
        self.job_description: str | None = None
    
    async def open_job(self, job_id: int) -> bool:
        """Open a specific LinkedIn job by ID."""
        if self.page is None:
            return False

        job_url = f"https://www.linkedin.com/jobs/search/?currentJobId={job_id}"
        try:
            await self.page.goto(job_url, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(2000)
            logger.info("Opened job ID: %d", job_id)
            return True
        except Exception as exc:
            logger.exception("Failed to open job ID %d: %s", job_id, exc)

        logger.warning("No jobs could be opened from the provided list.")
        return False    

    def get_job_id(self) -> int | None:
        """Extract the LinkedIn job ID from the current page URL."""
        if self.page is None:
            return None
        url = self.page.url
        params = parse_qs(urlparse(url).query)
        job_id = params.get("currentJobId", [None])[0]
        logger.info("Job ID: %s", job_id)
        return int(job_id) if job_id else None

    async def open_first_job(self) -> bool:
        """Open the first job card from the current jobs page."""
        if self.page is None:
            return False
        # Use the more specific job card selector from the inspection
        job_card = self.page.locator(".display-flex.job-card-container").first
        await job_card.click(timeout=self.timeout)
        return True

    async def click_easy_apply(self) -> bool:
        """Click the visible Easy Apply button if present."""
        if self.page is None:
            return False

        try: 
            no_longer =  self.page.get_by_text(re.compile(r"No longer accepting", re.IGNORECASE))
            if await no_longer.is_visible():
                return False
        except Exception as exec :
            logger.exception(f"Failed to fetch no Longer accepting applications")

        try:
            await self.page.wait_for_timeout(2000)
            job_card = self.page.locator(".display-flex.job-card-container").first
            job_title = self.page.locator(".t-24").first

            if await job_card.count() > 0:
                title = (await job_card.inner_text()).strip()
            elif await job_title.count() > 0:
                title = (await job_title.inner_text()).strip()
            else:
                raise Exception("Job title not found")

            logger.info("Opened first job: %s", title)
            self.job_title = title

        except Exception as exc:
            logger.exception("Failed to open first job: %s", exc)

        try:
            card_wrapper = self.page.locator(".jobs-search__job-details--wrapper")

            if await card_wrapper.count() > 0:
                card_wrapper_text = (await card_wrapper.inner_text()).strip()
                match = re.search(
                        r"(About the job.*?)(?=Job search faster with Premium)",
                        card_wrapper_text,
                        re.DOTALL,
                    )

                job_description_text = match.group(1).strip() if match else ""
                logger.info("Job description: %s", job_description_text)    
                self.job_description = job_description_text
        except Exception as exc:
            logger.exception("Failed to get job description: %s", exc)

        # Try role-based selector first with the job title
        try:            
            easy_apply = self.page.get_by_role("button", name=re.compile(r"Easy Apply", re.IGNORECASE))
            await easy_apply.wait_for(timeout=10000)
            await easy_apply.click(timeout=self.timeout)
            logger.info("Clicked Easy Apply button by role")
            return True
        except Exception as exc:
            logger.exception("Failed to click Easy Apply by role: %s", exc)

        # Try role-based selector first with the job title
        try:            
            easy_apply = self.page.get_by_role("link", name=re.compile(r"Easy Apply", re.IGNORECASE))
            await easy_apply.wait_for(timeout=10000)
            await easy_apply.click(timeout=self.timeout)
            logger.info("Clicked Easy Apply link by role")
            return True
        except Exception as exc:
            logger.exception("Failed to click Easy Apply by role: %s", exc)            

        return False

    async def limits(self) -> bool:
        """Check if Easy Apply daily limit is reached."""
        if self.page is None:
            return False

        try:
            limit_text = self.page.get_by_text(
                re.compile(r"You reached.*Easy Apply", re.IGNORECASE)
            )

            await limit_text.wait_for(timeout=5000)

            logger.warning("Easy Apply daily limit reached")
            return True

        except Exception:
            pass 

        try:
            limit_text = self.page.get_by_text(
                re.compile(r"We limit daily submissions*", re.IGNORECASE)
            )

            await limit_text.wait_for(timeout=5000)

            logger.warning("Easy Apply daily limit reached")
            return True

        except Exception:
            pass 
        
        return False

    async def fill_current_step(self, resume_path: str) -> bool:
        """Try to focus common form controls in the current application step."""
        if self.page is None:
            return False
        
        # Attempt to submit/upload a resume if the form requires it
        try:
            if await self.resume_submission(resume_path=resume_path):
                logger.info("Uploaded resume for application.")
        except Exception as exc:
            logger.exception("Failed to submit resume: %s", exc)

        dialogs = self.page.get_by_role("dialog")
        count = await dialogs.count()
        logger.info("Found %d dialogs", count)

        fields = dialogs.locator("""
            input:not([type=hidden]),
            textarea,
            select
        """)

        count = await fields.count()
        logger.info("Found %d non-radio form fields", count)

        if count == 0:
            logger.info("Found 0 form submission trying, form-fields ")
            return await self.next()

        for index in range(count):
            try:
                field = fields.nth(index)

                if not await field.is_visible():
                    continue

                info = await field.evaluate("""
                el => ({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || "",
                    name: el.name || "",
                    id: el.id || "",
                    placeholder: el.placeholder || "",
                    label:
                        el.labels && el.labels.length
                            ? [...el.labels].map(l => l.innerText.trim()).join(", ")
                            : "",
                    ariaLabel: el.getAttribute("aria-label") || "",
                    role: el.getAttribute("role") || ""
                })
                """)

                if info["tag"] == "select" and  "Phone country code" in info["label"]:
                    logger.info("Skipping Phone country code select field")
                    continue

                if info["type"] == "input" and info["label"] == "Mobile phone number":
                    logger.info("Skipping Phone number input field")
                    continue

                logger.info(
                    "Field %d: tag=%s type=%s name=%s id=%s label=%s placeholder=%s aria-label=%s",
                    index,
                    info["tag"],
                    info["type"],
                    info["name"],
                    info["id"],
                    info["label"],
                    info["placeholder"],
                    info["ariaLabel"],
                )

                if info["type"] == "checkbox" and 'follow' in info["label"].lower():
                        logger.info("Checkbox label: %r", info["label"])
                        logger.info("Found Follow checkbox")
                        # await field.uncheck()
                        await field.set_checked(False, force=True)
                        # Skip it, or uncheck/check as desired
                        return False

                question = info["label"]

                options = []

                if info["tag"] == "select":
                    options = await field.evaluate("""
                        el => [...el.options]
                            .filter(o => o.value)
                            .map(o => ({
                                label: o.text.trim(),
                                value: o.value
                            }))
                        """)
                    
                    logger.info("Found select options: %s", options)

                if question:
                    response = await answer_question(
                        question,
                        options=options if info["tag"] == "select" else None,
                    )
                    if response:
                        logger.info("Answered field with LLM response: %s", response)
                        self.questions_answers.append(
                            {
                                "question": question,
                                "answer": response,
                                "field_type": info["tag"],
                                "options": options if info["tag"] == "select" else None,
                            }
                        )
                        if info["tag"] == "select":
                            # Match either label or value
                            option = next(
                                (
                                    o for o in options
                                    if o["label"].lower() == response.lower()
                                    or o["value"].lower() == response.lower()
                                ),
                                None,
                            )
                            logger.info("Matched select option: %s", option)
                            if option:
                                await field.select_option(value=option["value"])
                            else:
                                logger.warning("No matching option found for '%s'", response)
                        elif info["type"] == "radio":
                            if info["label"].strip().lower() == "yes":
                                await field.check()
                        else:
                            await field.fill(response)
                        await self.page.wait_for_timeout(2000)
                        continue

            except Exception as exc:
                logger.exception("Skipping form field %d: %s", index, exc)

        return count > 0

    async def next(self) -> bool:
        """Advance to the next application step if a next button exists."""
        if self.page is None:
            return False

        # Try the specific button from the inspection
        try:
            await self.page.wait_for_timeout(2000)
            next_button = self.page.get_by_role("button", name="Continue to next step")
            if await next_button.count() > 0 and await next_button.is_visible():
                await next_button.click(timeout=self.timeout)
                logger.info("Clicked Continue to next step button")
                return True
        except Exception as exc:
            logger.exception("Failed to click Continue to next step button: %s", exc)

        # Try review button
        try:
            await self.page.wait_for_timeout(2000)
            review_button = self.page.get_by_role("button", name="Review your application")
            if await review_button.count() > 0 and await review_button.is_visible():
                await review_button.click(timeout=self.timeout)
                logger.info("Clicked Review your application button")
                return True
        except Exception as exc:
            logger.exception("Failed to click Review your application button: %s", exc)

        return False 

    async def submit(self) -> bool:
        """Submit the current application when a submit button is available."""
        if self.page is None:
            return False
        
        # try:
        #     follow_check = self.page.get_by_text(re.compile(r"Follow", re.IGNORECASE))
        #     await follow_check.wait_for(timeout=10000)
        #     await follow_check.click(timeout=self.timeout)
        #     logger.info("Clicked Follow button to UnFollow company")
        # except Exception as exc:
        #     logger.exception("Failed to click Follow button: %s", exc)

        # Try the specific submit button from the inspection
        try:
            await self.page.wait_for_timeout(2000)
            submit_button = self.page.get_by_role("button", name="Submit application")
            if await submit_button.count() > 0 and await submit_button.is_visible():
                await submit_button.click(timeout=self.timeout)
                logger.info("Clicked Submit application button")
                return True
        except Exception as exc:
            logger.exception("Failed to click Submit application button: %s", exc)

        return False

    async def handle_post_submission(self) -> bool:
        """Handle any post-submission dialogs, such as 'Not now' or 'Dismiss' buttons."""

        # Get the submission heading
        try:
            await self.page.wait_for_timeout(2000)

            heading = self.page.get_by_role(
                "heading",
                name=re.compile(r"Your application was sent to", re.IGNORECASE),
            )

            if await heading.count() > 0 and await heading.is_visible():
                heading_text = await heading.inner_text()
                logger.info("Submission heading: %s", heading_text)
            else:
                logger.error("Submission heading not found")

        except Exception as exc:
            logger.exception("Failed to get submission heading: %s", exc)

        # Handle "Not now" button that appears after submission
        try:
            await self.page.wait_for_timeout(2000)
            not_now_button = self.page.get_by_role("button", name="Not now")
            if await not_now_button.count() > 0 and await not_now_button.is_visible():
                await not_now_button.click(timeout=self.timeout)
                logger.info("Clicked Not now button after submission")
                return True
        except Exception as exc:
            logger.exception("Failed to click Not now button: %s", exc)


    async def dismiss_dialog(self) -> bool:
        """Dismiss any post-submission dialogs, such as 'Dismiss' buttons."""
        try:
            await self.page.wait_for_timeout(2000)

            dismiss_button = self.page.get_by_role(
                "button",
                name=re.compile(r"^Dismiss", re.IGNORECASE)
            ).first

            await dismiss_button.wait_for(timeout=self.timeout)
            await dismiss_button.click(timeout=self.timeout)

            logger.info("Clicked the first button starting with 'Dismiss'")
            return True

        except Exception as exc:
            logger.exception("Failed to click Dismiss button: %s", exc)

        return False

    async def open_next_job(self, href: str) -> bool:
        """Move to the next job card when available."""
        if self.page is None:
            return False
        try:
            await self.page.keyboard.press("Escape")
        except Exception:
            logger.exception("Unable to dismiss the current dialog")

        await self.page.goto(href, wait_until="domcontentloaded")
        logger.info("Opened next job: %s", href)
        await self.page.wait_for_timeout(3000)  # Wait 3 seconds for the page to load
        return True


    async def refresh_page(self) -> None:
        """Move to the next job card when available."""
        await self.page.reload(wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)

    async def resume_submission(self, resume_path: str | Path | None = None) -> bool:
        """Upload a resume file if a file input is present in the current dialog.

        Returns True when a file was set on an input element, False otherwise.
        """
        if self.page is None:
            return False
        
        if resume_path is None:
            logger.warning("No resume path provided for submission")
            return False

        path = Path(resume_path) 
        if not path.exists():
            logger.warning("Resume file not found: %s", path)
            return False

        try:
            # Prefer file inputs inside dialogs
            dialogs = self.page.get_by_role("dialog")
            file_inputs = dialogs.locator('input[type="file"]')

            if await file_inputs.count() == 0:
                file_inputs = self.page.locator('input[type="file"]')

            if await file_inputs.count() == 0:
                logger.info("No file input found for resume upload")
                return False

            await file_inputs.first.set_input_files(str(path))
            logger.info("Set resume file input to %s", path)
            await self.page.wait_for_timeout(1500)
            return True

        except Exception as exc:
            logger.exception("Failed to upload resume: %s", exc)
            return False
        

    async def ensure_logged_in(self) -> bool:
        """Return True if LinkedIn's sign-in prompt appears within the timeout."""
        if self.page is None:
            return False

        try:
            await self.page.wait_for_timeout(3000)

            heading = self.page.get_by_role(
                "heading",
                name="Sign in to view more jobs",
            )

            join_heading = self.page.get_by_role(
                "heading",
                name="Join LinkedIn",
            )
            button = self.page.get_by_role(
                "button",
                name="Sign in with Email",
            )


            return (
                await join_heading.is_visible(timeout=0)
                or await heading.is_visible(timeout=0)
                or await button.is_visible(timeout=0)
            )

        except Exception as e:
            logger.exception("Error checking for sign-in prompt: %s", e)
            return False
        
    def filter(self, job_description: str) -> bool:
        return super().filter(job_description)