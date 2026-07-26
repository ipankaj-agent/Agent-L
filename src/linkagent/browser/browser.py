from __future__ import annotations

from .playwright_manager import PlaywrightManager
from .session import BrowserSession

import logging

logger = logging.getLogger(__name__)


async def playwright_inspector(url: str, headless: bool = False) -> None:
    async with PlaywrightManager(headless=headless) as manager:
        async with BrowserSession(manager) as session:
            assert session.page is not None

            await session.page.goto(url, wait_until="domcontentloaded")

            logger.info(f"Opened URL: {url}")

            await session.page.pause()


async def make_session(url: str, headless: bool = False) -> None:
    async with PlaywrightManager(headless=headless) as manager:
        async with BrowserSession(manager) as session:
            assert session.page is not None

            await session.page.goto(url, wait_until="domcontentloaded")

            logger.info(f"Opened URL: {url}")

            print("Login manually, then close the browser.")
            await session.page.pause()

async def getSessionPage(url: str, headless: bool = True):
    async with PlaywrightManager(headless=headless) as manager:
        async with BrowserSession(manager) as session:
            assert session.page is not None
            return session.page