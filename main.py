import time
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup as bs

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


def create_driver():
    options = Options()

    # Headless + CI safe flags
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Fake real browser
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)

    # Prevent infinite hang
    driver.set_page_load_timeout(60)

    return driver


def show_svg():
    driver = create_driver()
    wait = WebDriverWait(driver, 30)

    try:
        # Open site
        driver.get("https://iut.edupage.org/timetable/")

        # Wait for "Classes" button
        element = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span[title='Classes']"))
        )
        element.click()

        # Wait for dropdown
        panel = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "dropDownPanel"))
        )

        items = panel.find_elements(By.CSS_SELECTOR, "li")

        # Select item
        items[31].click()

        # Let SVG render
        time.sleep(5)

        html_source = driver.page_source

    finally:
        driver.quit()

    # Parse HTML
    soup = bs(html_source, "lxml")

    svg_tag = soup.find("svg")

    if not svg_tag:
        raise Exception("SVG not found")

    # Resize SVG
    svg_tag["height"] = "600"
    svg_tag["width"] = "900"

    g_tag = svg_tag.find("g")
    if g_tag:
        g_tag["transform"] = "scale(0.3)"

    svg_str = str(svg_tag)

    # Fix inline styles
    svg_str = svg_str.replace(
        'style="position: absolute; left: 0px; top: 0px; direction: ltr; stroke: rgb(0, 0, 0); stroke-width: 0; fill: rgb(0, 0, 0);"',
        'style="position: relative; direction: ltr; stroke: rgb(0, 0, 0); stroke-width: 0; fill: rgb(0, 0, 0);"'
    )

    # Timestamp
    now = datetime.now(timezone(timedelta(hours=5))).strftime("%H:%M / %Y-%m-%d")

    # Build HTML
    html_content = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Timetable</title>

  <style>
    body {{
      margin: 0;
      padding: 0;
      width: 100vw;
      box-sizing: border-box;
      font-family: Arial, sans-serif;
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
    {svg_str}

    <div class="last-updated">
      Last updated: {now}
    </div>
  </div>
</body>
</html>
"""

    # Save file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("Timetable updated successfully.")


if __name__ == "__main__":
    show_svg()
