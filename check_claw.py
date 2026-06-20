#!/usr/bin/env python3
"""
Single-shot Best Buy stock check for GitHub Actions.

Runs once, checks the SKU, sends a Telegram message if it's buyable, exits.
GitHub Actions runs this on a schedule (see .github/workflows/monitor.yml).

Reads three values from environment variables (set as GitHub Secrets):
  TELEGRAM_TOKEN
  TELEGRAM_CHAT_ID
  SKU            (optional, defaults to the Claw)
"""

import os
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SKU = os.environ.get("SKU", "6680914")  # MSI Claw 8 EX AI

PRODUCT_URL = f"https://www.bestbuy.com/product/J3P7TXTKW3/sku/{SKU}"
BUTTON_STATE_URL = "https://www.bestbuy.com/button-state/v5/button-states"

# States that mean "you can buy it right now"
BUYABLE = {"ADD_TO_CART", "PRE_ORDER", "PREORDER"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.bestbuy.com",
    "Referer": PRODUCT_URL,
}


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=15,
    )


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    # Prime cookies by hitting the product page first.
    try:
        session.get(PRODUCT_URL, timeout=15)
    except requests.RequestException:
        pass

    try:
        r = session.post(BUTTON_STATE_URL, json={"skuIds": [SKU]}, timeout=15)
    except requests.RequestException as e:
        print(f"Request error: {e}")
        return

    if r.status_code != 200:
        # 403/429 here usually means Best Buy's bot protection blocked the
        # GitHub runner IP. Print and exit quietly (no alert).
        print(f"HTTP {r.status_code} - possible bot block, skipping this run.")
        return

    state = None
    try:
        infos = r.json().get("buttonStateResponseInfos", [])
        for info in infos:
            if str(info.get("skuId")) == SKU:
                state = info.get("buttonState")
    except ValueError:
        print("Could not parse JSON response.")
        return

    print(f"Button state: {state}")

    if state in BUYABLE:
        send_telegram(f"IN STOCK ({state})\nMSI Claw 8 EX AI\n{PRODUCT_URL}")
        print("Alert sent.")
    else:
        print("Not buyable, no alert.")


if __name__ == "__main__":
    main()

