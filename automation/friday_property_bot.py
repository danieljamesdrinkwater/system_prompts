#!/usr/bin/env python3
"""
Friday Property Automation for HomeOption.org (EFDC)

Runs every Friday at 8:57 AM via cron. Logs into homeoption.org,
navigates to View Properties at 9:00 AM, monitors for 5 minutes,
and auto-bids on qualifying properties.

Uses OpenRouter AI (Arcee Trinity) to intelligently parse page HTML
and evaluate properties — no fragile CSS selectors needed.

Bidding rules:
  - Bungalow: ALWAYS bid + send Telegram notification
  - Studio/bedsit: NEVER bid
  - Sheltered/retirement: NEVER bid
  - NOT ground floor: skip
  - Price < £600: skip
  - No garden: skip
  - Detached 1-bed, 1-bed maisonette, 1-bed house: Telegram notify only
  - Any other matching criteria (sep rooms, no neighbours above): notify only
"""

import json
import os
import sys
import time
import logging
import urllib.parse
from datetime import datetime

import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Load .env from repo root (one level up from automation/)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

EMAIL = os.getenv('HOMEOPTION_EMAIL')
PASSWORD = os.getenv('HOMEOPTION_PASSWORD')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

# AI model for page parsing and property evaluation
AI_MODEL = 'arcee-ai/trinity-large-preview:free'
# Fallback models if primary is rate-limited
AI_FALLBACK_MODELS = [
    'openrouter/free',
    'mistralai/mistral-small-3.1-24b-instruct:free',
    'google/gemma-3-27b-it:free',
]

BASE_URL = 'https://www.homeoption.org'

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f'run_{datetime.now():%Y%m%d_%H%M}.log')
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenRouter AI
# ---------------------------------------------------------------------------

PROPERTY_EVAL_PROMPT = """You are a property listing analyzer for a housing automation bot.

Given the HTML of a property listing page, extract ALL properties and for EACH one return a JSON object with:
- type: property type (e.g. "bungalow", "flat", "house", "maisonette", "studio", "bedsit", "detached", "sheltered")
- bedrooms: number of bedrooms (integer)
- floor: which floor (e.g. "ground floor", "first floor")
- price: weekly rent as a number (no currency symbol)
- has_garden: true/false
- has_separate_bedroom: true/false
- has_separate_living_room: true/false
- has_separate_kitchen: true/false
- has_separate_bathroom: true/false
- has_neighbours_above: true/false (false if bungalow, top floor, or explicitly stated)
- address: address if available
- should_bid: true/false based on these STRICT rules:
  * Bungalow: ALWAYS true (overrides all other rules)
  * Studio/bedsit: ALWAYS false
  * Sheltered/retirement: ALWAYS false
  * NOT ground floor: false
  * Price less than 600: false
  * No garden: false
  * Everything else: false (notify only)
- should_notify: true/false — send Telegram if:
  * Bungalow: true (always)
  * Detached 1-bed (ground floor, >= £600, garden): true
  * 1-bed maisonette (ground floor, >= £600, garden): true
  * 1-bed house (ground floor, >= £600, garden): true
  * Any other type that is ground floor, >= £600, has garden, has separate bedroom+living room+kitchen+bathroom, and NO neighbours above: true
  * Otherwise: false
- reason: brief explanation of the decision

Return a JSON array of objects. If no properties found, return an empty array [].
Reply with ONLY valid JSON, no markdown code fences, no explanation."""

PAGE_PARSE_PROMPT = """You are a web page analyzer. Given the HTML of a login/navigation page, identify:
- login_form: CSS selector or XPath for the login form
- email_field: CSS selector for email/username input
- password_field: CSS selector for password input
- submit_button: CSS selector for login/submit button
- partner_dropdown: CSS selector for housing provider/partner dropdown (if exists)
- efdc_option: how to select EFDC (visible text or value)
- view_properties_link: CSS selector or text for "View Properties" link
- any_navigation: list of main navigation links with text and selectors

Return ONLY valid JSON, no markdown code fences."""


def ai_query(prompt, html_content, model=None):
    """Send a query to OpenRouter AI with HTML content."""
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY missing in .env")
        return None

    models_to_try = [model or AI_MODEL] + AI_FALLBACK_MODELS

    for m in models_to_try:
        try:
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': m,
                    'messages': [
                        {'role': 'user', 'content': f"{prompt}\n\nHTML:\n{html_content[:15000]}"}
                    ],
                    'max_tokens': 2000,
                },
                timeout=60
            )
            data = resp.json()
            if 'choices' in data:
                content = data['choices'][0]['message'].get('content', '')
                if content:
                    logger.info(f"AI response from {m} ({len(content)} chars)")
                    return content
                logger.warning(f"Empty response from {m}, trying next...")
            else:
                err = data.get('error', {}).get('message', 'unknown')
                logger.warning(f"AI error from {m}: {err}, trying next...")
        except Exception as e:
            logger.warning(f"AI request to {m} failed: {e}, trying next...")

    logger.error("All AI models failed")
    return None


def parse_ai_json(response):
    """Parse JSON from AI response, handling markdown fences."""
    if not response:
        return None
    cleaned = response.strip()
    # Strip markdown code fences
    if cleaned.startswith('```'):
        cleaned = cleaned.split('\n', 1)[-1]
    if cleaned.endswith('```'):
        cleaned = cleaned.rsplit('```', 1)[0]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI JSON: {e}")
        logger.debug(f"Raw response: {response[:500]}")
        return None

# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------


def send_telegram(message):
    """Send a Telegram message via the Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            logger.info(f"Telegram sent: {message}")
            return True
        else:
            logger.error(f"Telegram API error: {data}")
            return False
    except requests.RequestException as e:
        logger.error(f"Telegram send failed: {e}")
        return False

# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------


def create_driver():
    """Create a headless Chrome WebDriver instance with anti-detection."""
    options = Options()
    # Remove '--headless=new' for first interactive run to debug visually
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    # Anti-detection: prevent sites from blocking automated browsers
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Try webdriver-manager first, fall back to system chromedriver
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    except Exception:
        service = Service('/opt/node22/bin/chromedriver')

    driver = webdriver.Chrome(service=service, options=options)
    # Remove webdriver flag from navigator
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    })
    return driver

# ---------------------------------------------------------------------------
# AI-powered login flow
# ---------------------------------------------------------------------------


def login(driver):
    """Navigate to homeoption.org, select EFDC, and log in.

    Uses AI to parse the page HTML and find the correct selectors,
    with hardcoded fallbacks for common patterns.
    """
    logger.info("Navigating to homeoption.org")
    driver.get(BASE_URL)
    time.sleep(5)  # Let JS render

    wait = WebDriverWait(driver, 15)
    page_html = driver.page_source

    # Ask AI to identify page elements
    selectors = None
    if OPENROUTER_API_KEY:
        logger.info("Using AI to parse login page...")
        ai_response = ai_query(PAGE_PARSE_PROMPT, page_html)
        selectors = parse_ai_json(ai_response)
        if selectors:
            logger.info(f"AI identified selectors: {json.dumps(selectors, indent=2)}")

    # Step 1: Click "Home Option" in the navigation
    try:
        if selectors and selectors.get('any_navigation'):
            # Try AI-suggested navigation
            for nav in selectors['any_navigation']:
                if 'home option' in nav.get('text', '').lower():
                    el = driver.find_element(By.CSS_SELECTOR, nav['selector'])
                    el.click()
                    logger.info("Clicked 'Home Option' via AI selector")
                    break
            else:
                raise NoSuchElementException("AI nav not found")
        else:
            raise NoSuchElementException("No AI selectors")
    except (NoSuchElementException, KeyError, TypeError):
        # Fallback: try common patterns
        try:
            link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Home Option")))
            link.click()
            logger.info("Clicked 'Home Option' via link text")
        except TimeoutException:
            link = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(text(), 'Home Option')]")
            ))
            link.click()
            logger.info("Clicked 'Home Option' via XPath")

    time.sleep(2)

    # Step 2: Select EFDC as housing provider
    try:
        if selectors and selectors.get('partner_dropdown'):
            dropdown = driver.find_element(By.CSS_SELECTOR, selectors['partner_dropdown'])
            select = Select(dropdown)
            efdc_text = selectors.get('efdc_option', 'EFDC')
            select.select_by_visible_text(efdc_text)
            logger.info(f"Selected '{efdc_text}' via AI selector")
        else:
            raise NoSuchElementException("No AI dropdown selector")
    except (NoSuchElementException, KeyError, TypeError):
        try:
            dropdown = wait.until(EC.presence_of_element_located((By.ID, "partner")))
            Select(dropdown).select_by_visible_text("EFDC")
            logger.info("Selected EFDC from #partner dropdown")
        except (NoSuchElementException, TimeoutException):
            efdc = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(), 'EFDC')]")
            ))
            efdc.click()
            logger.info("Clicked EFDC link/button")

    time.sleep(2)

    # Step 3: Enter credentials
    try:
        if selectors and selectors.get('email_field'):
            email_el = driver.find_element(By.CSS_SELECTOR, selectors['email_field'])
        else:
            raise NoSuchElementException("No AI email selector")
    except (NoSuchElementException, KeyError, TypeError):
        try:
            email_el = wait.until(EC.presence_of_element_located((By.ID, "email")))
        except TimeoutException:
            email_el = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='email'], input[name='email']")
            ))
    email_el.clear()
    email_el.send_keys(EMAIL)

    try:
        if selectors and selectors.get('password_field'):
            pass_el = driver.find_element(By.CSS_SELECTOR, selectors['password_field'])
        else:
            raise NoSuchElementException("No AI password selector")
    except (NoSuchElementException, KeyError, TypeError):
        try:
            pass_el = driver.find_element(By.ID, "password")
        except NoSuchElementException:
            pass_el = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    pass_el.clear()
    pass_el.send_keys(PASSWORD)

    # Step 4: Submit login
    try:
        if selectors and selectors.get('submit_button'):
            btn = driver.find_element(By.CSS_SELECTOR, selectors['submit_button'])
        else:
            raise NoSuchElementException("No AI submit selector")
    except (NoSuchElementException, KeyError, TypeError):
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        except NoSuchElementException:
            btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Log')]")
    btn.click()
    logger.info("Login submitted")

    time.sleep(3)

    # Step 5: Click "View Properties"
    try:
        if selectors and selectors.get('view_properties_link'):
            vp = driver.find_element(By.CSS_SELECTOR, selectors['view_properties_link'])
        else:
            raise NoSuchElementException("No AI view properties selector")
    except (NoSuchElementException, KeyError, TypeError):
        try:
            vp = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "View Properties")))
        except TimeoutException:
            vp = wait.until(EC.element_to_be_clickable(
                (By.PARTIAL_LINK_TEXT, "View Propert")
            ))
    vp.click()
    logger.info("Navigated to View Properties page")

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


def wait_until_nine():
    """Block until 9:00 AM. Cron starts at 8:57 to allow login time."""
    now = datetime.now()
    target = now.replace(hour=9, minute=0, second=0, microsecond=0)
    remaining = (target - now).total_seconds()
    if remaining > 0:
        logger.info(f"Waiting {remaining:.0f}s until 09:00")
        time.sleep(remaining)
    else:
        logger.info("Already past 09:00, proceeding immediately")

# ---------------------------------------------------------------------------
# AI-powered property evaluation
# ---------------------------------------------------------------------------


def evaluate_properties_with_ai(page_html):
    """Use AI to extract and evaluate all properties from the page HTML.

    Returns a list of property dicts, each with should_bid, should_notify, etc.
    Falls back to empty list if AI fails.
    """
    logger.info("Sending page HTML to AI for property evaluation...")
    ai_response = ai_query(PROPERTY_EVAL_PROMPT, page_html)
    properties = parse_ai_json(ai_response)

    if properties is None:
        logger.warning("AI returned no valid JSON — no properties to process")
        return []

    if not isinstance(properties, list):
        # AI might return a single object instead of array
        properties = [properties]

    logger.info(f"AI identified {len(properties)} properties")
    return properties


def find_bid_button(driver):
    """Try to find and return a bid/place bid button on the page."""
    selectors = [
        "button[class*='bid']", "a[class*='bid']",
        "button[class*='Bid']", "a[class*='Bid']",
        ".bid-button", ".place-bid",
    ]
    for sel in selectors:
        try:
            return driver.find_element(By.CSS_SELECTOR, sel)
        except NoSuchElementException:
            continue

    # Try by text content
    xpaths = [
        "//button[contains(text(), 'Bid')]",
        "//button[contains(text(), 'bid')]",
        "//a[contains(text(), 'Bid')]",
        "//button[contains(text(), 'Place')]",
    ]
    for xp in xpaths:
        try:
            return driver.find_element(By.XPATH, xp)
        except NoSuchElementException:
            continue

    return None

# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------


def monitor_properties(driver, refresh_count=5, interval_seconds=60):
    """Refresh View Properties page and use AI to evaluate listings."""
    for i in range(refresh_count):
        logger.info(f"--- Refresh {i + 1}/{refresh_count} ---")
        driver.refresh()
        time.sleep(5)  # Let JS render

        page_html = driver.page_source

        # Use AI to parse and evaluate all properties
        properties = evaluate_properties_with_ai(page_html)

        if not properties:
            logger.info("No properties found on this refresh")
            if i < refresh_count - 1:
                time.sleep(interval_seconds)
            continue

        for prop in properties:
            should_bid = prop.get('should_bid', False)
            should_notify = prop.get('should_notify', False)
            reason = prop.get('reason', 'no reason given')
            prop_type = prop.get('type', 'unknown')
            price = prop.get('price', 'N/A')
            address = prop.get('address', 'N/A')

            logger.info(f"  Property: {prop_type}, £{price}, {address} -> {reason}")

            if should_bid:
                logger.info("  Attempting to place bid...")
                bid_btn = find_bid_button(driver)
                if bid_btn:
                    bid_btn.click()
                    logger.info("  Bid button clicked")
                    # Handle confirmation dialog
                    try:
                        confirm = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, "//button[contains(text(), 'Confirm')]")
                            )
                        )
                        confirm.click()
                        logger.info("  Bid confirmed")
                    except TimeoutException:
                        pass
                else:
                    logger.warning("  Could not find bid button!")

                if should_notify:
                    send_telegram(
                        f"BID PLACED!\n"
                        f"Type: {prop_type}\n"
                        f"Price: £{price}\n"
                        f"Address: {address}\n"
                        f"Reason: {reason}"
                    )

            elif should_notify:
                send_telegram(
                    f"Property found (no bid):\n"
                    f"Type: {prop_type}\n"
                    f"Price: £{price}\n"
                    f"Address: {address}\n"
                    f"Reason: {reason}"
                )

        if i < refresh_count - 1:
            time.sleep(interval_seconds)


def main():
    if not EMAIL or not PASSWORD:
        logger.error("Missing HOMEOPTION_EMAIL or HOMEOPTION_PASSWORD in .env")
        sys.exit(1)

    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set — AI features disabled, using fallback selectors")

    driver = None
    try:
        driver = create_driver()
        login(driver)
        wait_until_nine()
        monitor_properties(driver)
        logger.info("Monitoring complete")
    except WebDriverException as e:
        logger.error(f"Browser error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        if driver:
            driver.quit()
            logger.info("Browser closed")


if __name__ == '__main__':
    main()
