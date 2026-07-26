"""LinkedIn automatic login module."""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from playwright.async_api import Page, TimeoutError

from linkagent.browser.browser import getSessionPage

logger = logging.getLogger(__name__)


class LinkedInAutoLogin:
    """Handle automatic LinkedIn login with email and password."""

    LINKEDIN_URL = "https://www.linkedin.com"
    LOGIN_URL = "https://www.linkedin.com/login"

    def __init__(
        self,
        page: Page,
        url: str = LINKEDIN_URL,
        email: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30000,  # 30 seconds
    ) -> None:
        """
        Initialize the LinkedIn auto login handler.

        Args:
            page: Playwright Page object
            email: LinkedIn email (if None, reads from LINKEDIN_EMAIL env var)
            password: LinkedIn password (if None, reads from LINKEDIN_PASSWORD env var)
            timeout: Timeout for operations in milliseconds
        """
        self.page = page       
        self.email = email or  os.getenv("LINKEDIN_EMAIL")
        self.password = password or os.getenv("LINKEDIN_PASSWORD")
        self.timeout = timeout
        self.url = url

        if not self.email or not self.password:
            raise ValueError(
                "LinkedIn credentials not provided. "
                "Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables "
                "or pass them as arguments."
            )
        

    async def ensure_logged_in(self) -> bool:
        """
        Check if the user is already logged in to LinkedIn.

        Returns:
            True if logged in, False otherwise
        """
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

            home_link = self.page.get_by_role(
                "link",
                name="Sign in",
                exact=True,
            )


            return not (
                await join_heading.is_visible(timeout=0)
                or await heading.is_visible(timeout=0)
                or await button.is_visible(timeout=0)
                or await home_link.is_visible(timeout=0)
            )

        except Exception as e:
            logger.exception("Error checking for sign-in prompt: %s", e)
            return False
            
    async def login_fields(self) -> bool:
        """Fill only the email and password fields."""

        if self.page is None:
            return False

        await self.page.wait_for_timeout(2000)

        await self.page.get_by_role(
            "link",
            name="Sign in",
            exact=True,
        ).click()

        await self.page.wait_for_timeout(2000)

        dialogs = self.page.get_by_role("dialog")

        fields = dialogs.locator("""
            input:not([type=hidden]),
            textarea,
            select
        """)

        count = await fields.count()
        logger.info("Found %d input fields on the dialog.", count)
        if count == 0:
            fields = self.page.locator("""
                input:not([type=hidden]),
                textarea,
                select
            """)

        count = await fields.count()
        logger.info("Found %d input fields on the page.", count)

        if count == 0:
            return False

        for index in range(count):
            field = fields.nth(index)

            if not await field.is_visible():
                continue

            info = await field.evaluate("""
            el => ({
                type: el.type || "",
                label:
                    el.labels && el.labels.length
                        ? [...el.labels].map(l => l.innerText.trim()).join(", ")
                        : "",
                ariaLabel: el.getAttribute("aria-label") || "",
                placeholder: el.placeholder || ""
            })
            """)

            logger.info(
                "Field %d: type=%s label=%s placeholder=%s aria-label=%s",
                index,
                info["type"],
                info["label"],
                info["placeholder"],
                info["ariaLabel"],
            )

            label = (
                info["label"]
                or info["ariaLabel"]
                or info["placeholder"]
            ).lower()

            if "email" in label:
                # await field.fill(self.email)
                await field.press_sequentially(self.email, delay=80)
                logger.info("Filled email field")
                await self.page.wait_for_timeout(3000)

            elif "password" in label:
                # await field.fill(self.password)
                await field.press_sequentially(self.password, delay=80)
                logger.info("Filled password field")
            
            await self.page.wait_for_timeout(3000)

        return True

    async def login(self) -> bool:
        """Login to LinkedIn."""

       
        await self.page.goto(
            self.url,
            wait_until="domcontentloaded",
            timeout=self.timeout,
        )

        if await self.ensure_logged_in():
            logger.warning("Already logged in to LinkedIn.")
            return True
        
        sign_in_button = self.page.get_by_role("button", name="Sign in")
        if await sign_in_button.count() > 0 and await sign_in_button.is_visible():
            await sign_in_button.click(timeout=self.timeout)
            logger.info("Clicked Sign in button")

        await self.login_fields()

        logger.info("Filled in email and password.")

        await self.page.wait_for_timeout(3000)

        await self.page.get_by_role(
            "button",
            name="Sign in",
            exact=True,
        ).click()
        

        return await self.ensure_logged_in()
