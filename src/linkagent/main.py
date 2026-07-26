from __future__ import annotations
import os
import argparse
import asyncio
import sys
from pathlib import Path
import subprocess
from linkagent.utils.logger import setup_logging
from linkagent.browser.browser import playwright_inspector, make_session
from linkagent.workflows.apply_jobs import apply_job_workflow, login_flow

setup_logging()  # Initialize logging configuration

import logging

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]      # project root

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open a URL in Playwright.")
    parser.add_argument("url", nargs="?", default="https://example.com", help="The URL to open.")
    parser.add_argument("--show", action="store_true", help="Run the browser in headed mode.")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Open browser for Playwright inspection."
    )
    parser.add_argument(
        "--make-session",
        action="store_true",
        help="Open browser for Playwright session creation."
    )

    parser.add_argument(
        "--report", action="store_true", help="Generate a report of the job application process."
    )

    parser.add_argument(
        "--auto-login", action="store_true", help="Automatically log in to LinkedIn using stored credentials."
    )

    parser.add_argument(
        "--platform", choices=["linkedin", "indeed"], default="linkedin", help="The platform to use for job applications."
    )

    parser.add_argument(
        "--refill-failed",
        action="store_true",
        help="Refill failed applications in the database.",
    )

    parser.add_argument(
        "--linkedin-job-id",
        type=int,
        help="Open and apply to a specific LinkedIn job ID instead of scanning the jobs page.",
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logger.info("PID: %s", os.getpid())
    logger.info("USER: %s", os.getlogin())
    logger.info("USERPROFILE: %s", os.environ.get("USERPROFILE"))
    logger.info("LOCALAPPDATA: %s", os.environ.get("LOCALAPPDATA"))
    if args.inspect:
        logger.info("Starting Playwright inspector for URL: %s", args.url)
        await playwright_inspector(args.url, headless=False)
        input("Inspect the page, then press Enter to continue...")
        return
    
    if args.make_session:
        logger.info("Starting Playwright session creation for URL: %s", args.url)
        await make_session(args.url, headless=not args.show)
        input("Inspect the page, then press Enter to continue...")
        return
    
    if args.report:
        logger.info(f"Building dashboard ")

        subprocess.run(
            ["npm.cmd", "run", "build"],
            check=True,
        )

        logger.info("Starting dashboard at http://127.0.0.1:8000")

        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "linkagent.dashboard.server:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            check=True,
        )

        return
    
    if args.auto_login:
        logger.info("Starting job application workflow with auto-login for URL: %s", args.url)
        await login_flow(args.url, headless=not args.show)
        return
    
    await apply_job_workflow(
        args.platform,
        args.url,
        headless=not args.show,
        refill_failed=args.refill_failed,
        linkedin_job_id=args.linkedin_job_id,
    )


if __name__ == "__main__":
    asyncio.run(main())
