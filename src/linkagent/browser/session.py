from __future__ import annotations

import logging

from playwright.async_api import BrowserContext, Page

from .playwright_manager import PlaywrightManager

logger = logging.getLogger(__name__)


class BrowserSession:
    def __init__(self, manager: PlaywrightManager):
        self.manager = manager
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self) -> "BrowserSession":
        if self.manager.context is None:
            raise RuntimeError("Persistent browser context is not available")

        self.context = self.manager.context

        # Reuse existing page if one already exists
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        return self

    async def __aexit__(self, exc_type, exc, tb):
        # Don't close the persistent context here.
        # It is owned by PlaywrightManager.
        pass