import asyncio
import time
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup as bs
from playwright.async_api import async_playwright


URL = "https://iut.edupage.org/timetable/"


async def show_svg():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122 Safari/537.36"
            )
        )

        page = await context.new_page()

        # Load page
        await page.goto(URL, timeout=60000, wait_until="networkidle")

        # Click Classes
        await page.wait_for_selector("span[title='Classes']", timeout=30000)
        await page.click("span[title='Classes']")

        # Wait dropdown
        await page.wait_for_selector(".dropDownPanel", timeout=30000)

        items = await page.query_selector_all(".dropDownPanel li")

        if len(items) < 32:
            raise Exception("Not enough classes found")

        # Click your class
        await items[31].click()

        # Let SVG render
        await page.wait_for_timeout(5000)

        html = await page.content()

        await browser.close()

    # Parse
    soup = bs(html, "lxml")

    svg = soup.find("svg")

    if not svg:
        raise Exception("SVG not found")

    svg["width"] = "900"
    svg["height"] = "600"

    g = svg.find("g")
    if g:
        g["transform"] = "scale(0.3)"

    svg_str = str(svg)

    svg_str = svg_str.replace(
        'style="position: absolute; left: 0px; top: 0px; direction: ltr; stroke: rgb(0, 0, 0); stroke-width: 0; fill: rgb(0, 0, 0);"',
        'style="position: relative; direction: ltr; stroke: rgb(0, 0, 0); stroke-width: 0; fill: rgb(0, 0, 0);"'
    )

    now = datetime.now(
        timezone(timedelta(hours=5))
    ).strftime("%H:%M / %Y-%m-%d")

    html_out = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Timetable</title>
    <style>
      body{{
          margin: 0;
          padding: 0;
          width: 100vw;
          box-sizing: border-box;
      }}

      .svg-container {{
          display: flex;
          align-items: center;
          flex-direction: column;
          gap: 8px;
          width: 100%;
          height: 100vh;
        }}

        .last-updated {{
            text-align: center;
            color: #666;
            margin-top: 10px;
            font-size: 20px;
        }}
    </style>
  </head>

  <body>
    <div class="svg-container">
      { svg_str }
<div class="last-updated">Last updated: {datetime.now(timezone(timedelta(hours=5))).strftime("%H:%M / %Y-%m-%d")}</div>
    </div>
  </body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_out)

    print("Timetable updated.")


if __name__ == "__main__":
    asyncio.run(show_svg())
