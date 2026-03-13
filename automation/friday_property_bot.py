#!/usr/bin/env python3
"""
Friday Property Automation for HomeOption.org (EFDC)

Runs every Friday at 8:57 AM via cron. Logs into homeoption.org,
navigates to View Properties at 9:00 AM, monitors for 5 minutes,
and auto-bids on qualifying properties.

Bidding rules:
  - Bungalow: ALWAYS bid + send Telegram notification
  - Studio/bedsit: NEVER bid
  - Detached 1-bed: Bid if ground floor, >= £600, has garden
  - Any other: Skip unless ground floor, >= £600, has garden
  - NOT ground floor: skip
  - Price < £600: skip
  - No garden: skip
"""

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
# Telegram notification via CallMeBot
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
    # Remove '--headless=new' for first interactive run to debug selectors
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
# Login flow
# ---------------------------------------------------------------------------


def login(driver):
    """Navigate to homeoption.org, select EFDC, and log in."""
    logger.info("Navigating to homeoption.org")
    driver.get(BASE_URL)

    wait = WebDriverWait(driver, 15)

    # NOTE: All selectors below are best-guesses for HomeOption's portal.
    # They MUST be verified by inspecting the live site with browser DevTools.
    # Run the script once with '--headless=new' REMOVED to confirm visually.

    # Step 1: Click "Home Option" in the navigation  # ADJUST selector
    try:
        home_option_link = wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Home Option"))
        )
        home_option_link.click()
        logger.info("Clicked 'Home Option' nav link")
    except TimeoutException:
        # Try partial match or CSS selector
        home_option_link = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(text(), 'Home Option')]")
            )
        )
        home_option_link.click()
        logger.info("Clicked 'Home Option' via XPath")

    # Step 2: Select EFDC as housing provider via 'partner' dropdown  # ADJUST
    try:
        provider_dropdown = wait.until(
            EC.presence_of_element_located((By.ID, "partner"))
            # Fallback IDs to try: (By.NAME, "partner"),
            # (By.CSS_SELECTOR, "select[name='partner']"),
            # (By.CSS_SELECTOR, ".housing-provider-select")
        )
        select = Select(provider_dropdown)
        select.select_by_visible_text("EFDC")
        logger.info("Selected EFDC from partner dropdown")
    except (NoSuchElementException, TimeoutException):
        # EFDC might be a clickable link/button instead of dropdown
        efdc_link = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(), 'EFDC')]")
            )
        )
        efdc_link.click()
        logger.info("Clicked EFDC link/button")

    # Step 3: Enter credentials  # ADJUST selectors
    email_field = wait.until(
        EC.presence_of_element_located((By.ID, "email"))
        # Fallback: (By.NAME, "email"), (By.CSS_SELECTOR, "input[type='email']")
    )
    email_field.clear()
    email_field.send_keys(EMAIL)

    password_field = driver.find_element(By.ID, "password")
    # Fallback: (By.NAME, "password"), (By.CSS_SELECTOR, "input[type='password']")
    password_field.clear()
    password_field.send_keys(PASSWORD)

    # Step 4: Submit login  # ADJUST selector
    login_button = driver.find_element(
        By.CSS_SELECTOR, "button[type='submit']"
        # Fallback: (By.XPATH, "//button[contains(text(), 'Log')]")
    )
    login_button.click()
    logger.info("Login submitted")

    # Wait for page to load after login
    time.sleep(3)

    # Step 5: Click "View Properties"  # ADJUST selector
    view_props = wait.until(
        EC.element_to_be_clickable((By.LINK_TEXT, "View Properties"))
        # Fallback: (By.PARTIAL_LINK_TEXT, "View Propert")
    )
    view_props.click()
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
# Property evaluation
# ---------------------------------------------------------------------------


def evaluate_property(prop_element):
    """
    Extract property details and decide whether to bid.

    Returns:
        (should_bid, notify, reason, details)
        - should_bid: place a bid on this property
        - notify: send a Telegram notification

    NOTE: CSS selectors below are placeholders — update after inspecting
    the actual View Properties page in DevTools.
    """
    try:
        # ADJUST all these selectors after first interactive run
        prop_type = prop_element.find_element(
            By.CSS_SELECTOR, ".property-type"
        ).text.strip().lower()

        floor_text = prop_element.find_element(
            By.CSS_SELECTOR, ".property-floor"
        ).text.strip().lower()

        price_text = prop_element.find_element(
            By.CSS_SELECTOR, ".property-price"
        ).text.strip()

        garden_text = prop_element.find_element(
            By.CSS_SELECTOR, ".property-garden"
        ).text.strip().lower()

        # Full property description/features text for room and neighbour checks
        # ADJUST: this selector should capture the description or features list
        try:
            description = prop_element.find_element(
                By.CSS_SELECTOR, ".property-description, .property-features, .property-details"
            ).text.strip().lower()
        except NoSuchElementException:
            description = prop_element.text.strip().lower()

    except NoSuchElementException as e:
        logger.warning(f"Could not extract property details: {e}")
        return False, False, "missing data", {}

    # Parse price
    price = 0.0
    try:
        price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
    except ValueError:
        logger.warning(f"Could not parse price: {price_text}")

    has_garden = 'yes' in garden_text or 'garden' in garden_text
    is_ground = 'ground' in floor_text
    is_bungalow = 'bungalow' in prop_type
    is_studio = 'studio' in prop_type or 'bedsit' in prop_type
    is_detached_1bed = 'detached' in prop_type and '1' in prop_type
    is_maisonette_1bed = 'maisonette' in prop_type and '1' in prop_type
    is_house_1bed = 'house' in prop_type and '1' in prop_type
    is_sheltered = 'sheltered' in prop_type or 'retirement' in prop_type

    # Check for separate rooms
    has_sep_bedroom = 'bedroom' in description
    has_sep_living = 'living' in description or 'lounge' in description or 'sitting room' in description
    has_sep_kitchen = 'kitchen' in description
    has_sep_bathroom = 'bathroom' in description or 'bath' in description
    has_separate_rooms = all([has_sep_bedroom, has_sep_living, has_sep_kitchen, has_sep_bathroom])

    # Check for neighbours above (top floor or no upstairs neighbours)
    has_neighbours_above = not (
        'top floor' in description or 'top-floor' in description
        or 'no neighbo' in description or 'no upstairs' in description
        or is_ground  # ground floor with no one above is handled by floor_text
    )
    # Ground floor flats/maisonettes typically have neighbours above
    # unless description says otherwise — so for ground floor, check explicitly
    if is_ground and ('neighbo' in description and 'above' in description):
        has_neighbours_above = True
    if is_ground and ('no neighbo' in description or 'no upstairs' in description):
        has_neighbours_above = False

    details = {
        'type': prop_type,
        'floor': floor_text,
        'price': price,
        'garden': garden_text,
        'separate_rooms': has_separate_rooms,
        'neighbours_above': has_neighbours_above,
    }

    # Rule: Studio/bedsit — never bid
    if is_studio:
        return False, False, "studio/bedsit - skip", details

    # Rule: Sheltered/retirement — never bid
    if is_sheltered:
        return False, False, "sheltered/retirement - skip", details

    # Rule: Bungalow — always bid (no floor/price/garden filter)
    if is_bungalow:
        return True, True, "bungalow - bid immediately", details

    # General exclusion rules
    if not is_ground:
        return False, False, "not ground floor - skip", details
    if price < 600:
        return False, False, f"price £{price:.0f} < £600 - skip", details
    if not has_garden:
        return False, False, "no garden - skip", details

    # Rule: Detached 1-bed — notify only, do NOT bid
    if is_detached_1bed:
        return False, True, "detached 1-bed (ground, >=£600, garden) - notify only", details

    # Rule: 1-bed maisonette — notify only, do NOT bid
    if is_maisonette_1bed:
        return False, True, "1-bed maisonette (ground, >=£600, garden) - notify only", details

    # Rule: 1-bed house — notify only, do NOT bid
    if is_house_1bed:
        return False, True, "1-bed house (ground, >=£600, garden) - notify only", details

    # Catch-all: any other type that passes ground/price/garden filters
    # Must also have separate bedroom, living room, kitchen, bathroom
    # and no neighbours above
    if not has_separate_rooms:
        return False, False, f"'{prop_type}' - no separate rooms - skip", details
    if has_neighbours_above:
        return False, False, f"'{prop_type}' - neighbours above - skip", details

    return False, True, f"'{prop_type}' (ground, >=£600, garden, sep rooms, no above) - notify", details

# ---------------------------------------------------------------------------
# Bid placement
# ---------------------------------------------------------------------------


def place_bid(driver, prop_element):
    """Click the bid button on a property listing."""
    try:
        # ADJUST: inspect the actual bid button selector
        bid_button = prop_element.find_element(
            By.CSS_SELECTOR, ".bid-button, button[class*='bid'], a[class*='bid']"
        )
        bid_button.click()
        logger.info("Bid button clicked")

        # Handle optional confirmation dialog
        try:
            confirm = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Confirm')]")
                )
            )
            confirm.click()
            logger.info("Bid confirmed")
        except TimeoutException:
            pass  # No confirmation dialog

        return True
    except Exception as e:
        logger.error(f"Failed to place bid: {e}")
        return False

# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------


def monitor_properties(driver, refresh_count=5, interval_seconds=60):
    """Refresh View Properties page and evaluate listings."""
    for i in range(refresh_count):
        logger.info(f"--- Refresh {i + 1}/{refresh_count} ---")
        driver.refresh()
        time.sleep(3)  # Let page load

        # ADJUST: use the actual property card container selector
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR,
                     ".property-card, .property-listing, .property-item")
                )
            )
        except TimeoutException:
            logger.info("No property cards found on this refresh")
            if i < refresh_count - 1:
                time.sleep(interval_seconds)
            continue

        properties = driver.find_elements(
            By.CSS_SELECTOR,
            ".property-card, .property-listing, .property-item"
        )
        logger.info(f"Found {len(properties)} properties")

        for prop in properties:
            should_bid, notify, reason, details = evaluate_property(prop)
            logger.info(f"  Property: {details} -> {reason}")

            if should_bid:
                success = place_bid(driver, prop)
                if success and notify:
                    send_telegram(
                        f"BID PLACED on bungalow! "
                        f"Price: £{details.get('price', 'N/A')}, "
                        f"Type: {details.get('type', 'N/A')}"
                    )
            elif notify:
                send_telegram(
                    f"Property found (no bid): "
                    f"Type: {details.get('type', 'N/A')}, "
                    f"Price: £{details.get('price', 'N/A')}, "
                    f"Floor: {details.get('floor', 'N/A')}"
                )

        if i < refresh_count - 1:
            time.sleep(interval_seconds)


def main():
    if not EMAIL or not PASSWORD:
        logger.error("Missing HOMEOPTION_EMAIL or HOMEOPTION_PASSWORD in .env")
        sys.exit(1)

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
