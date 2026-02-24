import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from bs4 import BeautifulSoup as bs
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ── Config ────────────────────────────────────────────────────────────────────
URL          = "https://iut.edupage.org/timetable/"
CLASS_INDEX  = 31
OUTPUT_FILE  = Path("index.html")
TIMEZONE_UTC = timedelta(hours=5)
SVG_WIDTH    = 900
SVG_HEIGHT   = 600
SVG_SCALE    = 0.3
MAX_RETRIES  = 3
RETRY_DELAY  = 10   # seconds between retries
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)
TZ = timezone(TIMEZONE_UTC)


def now_str() -> str:
    return datetime.now(TZ).strftime("%H:%M / %Y-%m-%d")


async def fetch_timetable_html() -> str:
    """Launch a headless browser, navigate to the timetable, and return raw HTML."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-gpu",
            ],
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122 Safari/537.36"
                ),
            )
            page = await context.new_page()

            # ── 1. Navigate ───────────────────────────────────────────────────
            # "domcontentloaded" is much more reliable than "networkidle" for
            # SPAs / pages that keep background connections open forever.
            log.info("Loading %s", URL)
            await page.goto(URL, timeout=60_000, wait_until="domcontentloaded")

            # Wait until the Classes button is actually interactive
            log.info("Waiting for 'Classes' button…")
            await page.wait_for_selector("span[title='Classes']", timeout=30_000)

            # ── 2. Open the class dropdown ────────────────────────────────────
            await page.click("span[title='Classes']")
            await page.wait_for_selector(".dropDownPanel", timeout=30_000)

            items = await page.query_selector_all(".dropDownPanel li")
            if len(items) <= CLASS_INDEX:
                raise ValueError(
                    f"Expected at least {CLASS_INDEX + 1} classes, found {len(items)}"
                )

            # ── 3. Select your class ──────────────────────────────────────────
            log.info("Clicking class at index %d", CLASS_INDEX)
            await items[CLASS_INDEX].click()

            # ── 4. Wait for SVG to appear (beats a blind sleep) ───────────────
            log.info("Waiting for SVG to render…")
            await page.wait_for_selector("svg", timeout=30_000)
            # Give any JS animations a moment to settle
            await page.wait_for_timeout(1_500)

            return await page.content()

        except PlaywrightTimeout as exc:
            raise RuntimeError(
                "Playwright timed out — the site may be slow or unreachable."
            ) from exc
        finally:
            await browser.close()


async def fetch_with_retry() -> str:
    """Retry fetch_timetable_html up to MAX_RETRIES times."""
    last_error: Exception = RuntimeError("No attempts made")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("Attempt %d/%d", attempt, MAX_RETRIES)
            return await fetch_timetable_html()
        except Exception as exc:
            last_error = exc
            log.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                log.info("Retrying in %ds…", RETRY_DELAY)
                await asyncio.sleep(RETRY_DELAY)
    raise last_error


def extract_and_patch_svg(html: str) -> str:
    """Parse the HTML, find the SVG, and apply display patches."""
    soup = bs(html, "lxml")
    svg = soup.find("svg")
    if not svg:
        raise ValueError("No <svg> element found in page HTML")

    svg["width"]  = str(SVG_WIDTH)
    svg["height"] = str(SVG_HEIGHT)

    first_g = svg.find("g")
    if first_g:
        first_g["transform"] = f"scale({SVG_SCALE})"

    # Fix absolute positioning that breaks layout inside a flex container
    for tag in svg.find_all(style=True):
        tag["style"] = tag["style"].replace(
            "position: absolute; left: 0px; top: 0px;",
            "position: relative;",
        )

    return str(svg)


HTML_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Timetable</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      padding: 1rem;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      background: #f5f5f5;
      font-family: system-ui, sans-serif;
    }}

    h1 {{
      margin: 0 0 0.5rem;
      font-size: 1.4rem;
      color: #333;
    }}

    .svg-wrapper {{
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,.12);
      padding: 1rem;
      max-width: 100%;
      overflow-x: auto;
    }}

    .last-updated {{
      margin-top: 0.75rem;
      font-size: 0.9rem;
      color: #888;
    }}
  </style>
</head>
<body>
  <h1>IUT Timetable</h1>
  <div class="svg-wrapper">
    {svg}
  </div>
  <p class="last-updated">Last updated: {updated}</p>
</body>
</html>
"""


def build_html(svg_str: str) -> str:
    return HTML_TEMPLATE.format(svg=svg_str, updated=now_str())


async def main() -> None:
    log.info("Fetching timetable…")
    raw_html = await fetch_with_retry()

    log.info("Extracting SVG…")
    svg_str = extract_and_patch_svg(raw_html)

    log.info("Writing %s", OUTPUT_FILE)
    OUTPUT_FILE.write_text(build_html(svg_str), encoding="utf-8")

    log.info("Done — timetable updated at %s", now_str())


if __name__ == "__main__":
    asyncio.run(main())
