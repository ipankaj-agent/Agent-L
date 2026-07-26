from __future__ import annotations

import logging
import os
from pathlib import Path

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(os.getenv("BROWSER_PROFILE_DIR", "data/browser_profile"))


class PlaywrightManager:
    def __init__(self, headless: bool = False) -> None:
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.headless = headless

    async def __aenter__(self) -> "PlaywrightManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    async def start(self) -> None:
        self.playwright = await async_playwright().start()

        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 80)
        logger.info("Launching browser")
        logger.info("Profile directory : %s", PROFILE_DIR.resolve())
        logger.info("Headless          : %s", self.headless)
        logger.info("Exists            : %s", PROFILE_DIR.exists())
        logger.info("Local State       : %s", (PROFILE_DIR / "Local State").exists())
        logger.info("Default profile   : %s", (PROFILE_DIR / "Default").exists())

        if PROFILE_DIR.exists():
            logger.info("Profile contents:")
            for item in sorted(PROFILE_DIR.iterdir()):
                logger.info("  %s", item.name)

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=self.headless,
            viewport=None,
            channel="chrome",
        )

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        # Dump LinkedIn cookies
        cookies = await self.context.cookies(["https://www.linkedin.com"])

        logger.info("=" * 80)
        logger.info("LinkedIn cookie count: %d", len(cookies))

        if not cookies:
            logger.warning("No LinkedIn cookies found!")

        for cookie in cookies:
            logger.info(
                "Cookie: %-25s Domain=%-25s Expires=%s",
                cookie["name"],
                cookie["domain"],
                cookie["expires"],
            )

        logger.info("=" * 80)

    async def stop(self) -> None:
        if self.context is not None:
            logger.info("Closing browser context")
            await self.context.close()
            self.context = None

        if self.playwright is not None:
            logger.info("Stopping Playwright")
            await self.playwright.stop()
            self.playwright = None