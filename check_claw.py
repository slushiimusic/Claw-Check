#!/usr/bin/env python3
"""
Single-shot Best Buy stock check (product-page HTML version).

Last-ditch approach for cloud runners: instead of the heavily bot-guarded
button-state API, fetch the product page like a real browser and scan the
embedded data for the stock signal.

Reads from environment variables (set as GitHub Secrets):
  TELEGRAM_TOKEN
  TELEGRAM_CHAT_ID
  SKU            (optional, defaults to the Claw)
"""

import os
import time
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SKU = os.environ.get("SKU", "6680914")  # MSI Claw 8 EX AI

PRODUCT_URL = f"https://www.bestbuy.com/product/J3P7TXTKW3/sku/{SKU}"

TIMEOUT = 30
RETRIES = 2

# Full browser header set to look as un-script-like as possible.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Connection": "keep-alive",
}


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=15,
    )


def fetch_html():
    session = requests.Session()
    session.headers.update(HEADERS)
    last_err = None
    for attempt in range(1, RETRIES + 2):
        try:
            r = session.get(PRODUCT_URL, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.text
            print(f"Attempt {attempt}: HTTP {r.status_code}")
            last_err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            print(f"Attempt {attempt}: {e}")
            last_err = str(e)
        time.sleep(3)
    print(f"All attempts failed: {last_err}")
    return None


def interpret(html):
    """
    Return True (buyable), False (sold out), or None (couldn't tell).
    Checks several signals in priority order.
    """
    h = html

    # 1. schema.org availability (most reliable when present)
    if "schema.org/InStock" in h:
        return True
    if "schema.org/OutOfStock" in h or "schema.org/SoldOut" in h:
        return False

    # 2. Best Buy's own button-state strings embedded in the page JSON
    if '"buttonState":"ADD_TO_CART"' in h or '"buttonState":"PRE_ORDER"' in h:
        return True
    if '"buttonState":"SOLD_OUT"' in h or '"buttonState":"COMING_SOON"' in h:
        return False

    # 3. Visible-text fallback (least reliable)
    low = h.lower()
    if "sold out" in low:
        return False
    if "add to cart" in low:
        return True

    return None


def main():
    html = fetch_html()
    if html is None:
        # Network blocked/timed out. No alert; just record it.
        print("Could not fetch page (likely blocked). Skipping run.")
        return

    result = interpret(html)
    if result is True:
        print("Signal: BUYABLE")
        send_telegram(f"IN STOCK\nMSI Claw 8 EX AI\n{PRODUCT_URL}")
        print("Alert sent.")
    elif result is False:
        print("Signal: sold out, no alert.")
    else:
        # Page loaded but we couldn't find a known signal. Worth knowing.
        print("Page loaded but stock signal not found (page format may have "
              "changed, or it's a bot-challenge page).")


if __name__ == "__main__":
    main()
