import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

###############################################################################
# Helpers to parse the "Trending Companies" page for stock info
###############################################################################

def parse_company_card(card):
    """
    Given one <a class="CompanyListCard_card__jDLs9"> element,
    extract relevant fields (ticker, price, etc.) and return as a dict.
    """
    data = {}

    # Ticker
    ticker_div = card.find("div", class_="CompanyListCard_companySymbolBox__FHwrJ")
    data["ticker"] = ticker_div.get_text(strip=True) if ticker_div else None

    # Price
    price_div = card.find("div", class_="CompanyListCard_priceBox__1rDHN")
    data["price"] = price_div.get_text(strip=True) if price_div else None

    # Price Change (absolute & percent)
    price_change_container = card.find("div", class_="PriceChangeIndicator_container__E_A2I")
    if price_change_container:
        amount_elem = price_change_container.find("div", class_="PriceChangeIndicator_priceChangeAmount__mOUmj")
        data["price_change_amount"] = amount_elem.get_text(strip=True) if amount_elem else None

        percent_elem = price_change_container.find("div", class_="PriceChangeIndicator_percent__NNfl9")
        data["price_change_percent"] = percent_elem.get_text(strip=True) if percent_elem else None
    else:
        data["price_change_amount"] = None
        data["price_change_percent"] = None

    # High / Low
    high_low_box = card.find("div", class_="CompanyListCard_highLowBox__LsL8c")
    if high_low_box:
        divs = high_low_box.find_all("div")
        if len(divs) == 2:
            high_text = divs[0].get_text(strip=True)  # e.g. "H 1.14"
            low_text  = divs[1].get_text(strip=True)  # e.g. "L 0.89"
            data["high"] = high_text.replace("H", "").strip()
            data["low"]  = low_text.replace("L", "").strip()
        else:
            data["high"] = None
            data["low"]  = None
    else:
        data["high"] = None
        data["low"]  = None

    # Ask / Bid
    ask_div = card.find("div", class_="CompanyListCard_ask__yjnk6")
    bid_div = card.find("div", class_="CompanyListCard_bid__u9Irm")
    data["ask"] = ask_div.get_text(strip=True) if ask_div else None
    data["bid"] = bid_div.get_text(strip=True) if bid_div else None

    # Company Name
    name_span = card.find("span", class_="CompanyListCard_companyNameBox__CIYvK")
    data["company_name"] = name_span.get_text(strip=True) if name_span else None

    # Volume
    vol_span = card.find("span", class_="CompanyListCard_volume__wIfA1")
    data["volume"] = vol_span.get_text(strip=True) if vol_span else None

    return data


def get_top_5_stocks_info():
    """
    Visits the trending companies page, extracts the top 5 company cards,
    parses each card’s info (ticker, price, volume, etc.) and returns a list
    of dicts with that stock information.
    """
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        url = "https://ceo.ca/content/companies?exchange=all&sort_by=trending&sector=All"
        page.goto(url, wait_until="networkidle")
        time.sleep(3)

        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        container_divs = soup.find_all("div", class_="CompanyList_companyList__dhW2O CompanyList_oneCol__8FaIu")
        if not container_divs:
            print("No container_div found. Possibly site structure changed.")
            browser.close()
            return []

        # Extract company cards in the first container
        company_cards = container_divs[0].find_all("a", class_="CompanyListCard_card__jDLs9")
        # Just top 5
        top_5_cards = company_cards[:5]

        for card in top_5_cards:
            card_data = parse_company_card(card)
            results.append(card_data)

        browser.close()

    return results


###############################################################################
# Helpers to parse chat messages from a CEO.ca symbol channel
###############################################################################

def parse_relative_time(time_str):
    """
    Parse relative time strings like "about 11 hours ago", "24 minutes ago", etc.
    Return total minutes as an integer.
    """
    if not time_str:
        return 999999

    time_str = time_str.lower().replace("about ", "").strip()
    if time_str.endswith(" ago"):
        time_str = time_str[:-4].strip()

    pattern = r'(\d+)\s+(hour|hours|minute|minutes|second|seconds)'
    match = re.search(pattern, time_str)
    if match:
        number = int(match.group(1))
        unit   = match.group(2)
        if "hour" in unit:
            return number * 60
        elif "minute" in unit:
            return number
        elif "second" in unit:
            # treat <60s as 1 minute
            return 1 if number < 60 else (number // 60)
    else:
        if "just now" in time_str or time_str == '':
            return 0
        # fallback
        return 999999


def parse_chat_messages(soup, time_window_hours=3):
    """
    From a channel page's HTML, parse all chat messages in the last `time_window_hours` hours.
    Returns a list of {username, message, time_text, minutes_ago}.
    """
    messages_data = []
    rows = soup.find_all("div", class_="spielRow Spiel_row__vzSVl")

    for row in rows:
        # Username
        user_span = row.find("span", class_="Spiel_name__OsX_Z ignoreRowExpand")
        username  = user_span.find("a").get_text(strip=True) if (user_span and user_span.find("a")) else None

        # Time text
        time_elem = row.find("time")
        time_str  = time_elem.get_text(strip=True) if time_elem else None
        rel_mins  = parse_relative_time(time_str)

        # Message text
        content_div = row.find("div", class_="Spiel_spielContentContainer__zqxYO")
        if not content_div:
            content_div = row.find("div", class_="Spiel_message__l6_Cz")
        message_text = content_div.get_text(" ", strip=True) if content_div else ""

        if rel_mins <= time_window_hours * 60:
            messages_data.append({
                "username": username,
                "message":  message_text,
                "time_text": time_str,
                "minutes_ago": rel_mins
            })

    return messages_data


def scrape_stock_chat(symbol, time_window_hours=3):
    """
    Given a symbol like "QNC" or "XBOT",
    visits the CEO.ca channel, e.g. https://ceo.ca/XBOT
    scrapes the chat from the last time_window_hours, returns list of messages.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        url = f"https://ceo.ca/{symbol}"
        page.goto(url, wait_until="networkidle")
        time.sleep(3)

        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        messages = parse_chat_messages(soup, time_window_hours)

        browser.close()

    return messages


###############################################################################
# Main script
###############################################################################

def main():
    # 1) Get the top 5 stocks from the trending page
    top_5_data = get_top_5_stocks_info()
    if not top_5_data:
        print("No top 5 data found. Possibly no results or site changed.")
        return

    # 2) For each stock, print the key info, then fetch & print the chat (3h)
    for idx, stock_info in enumerate(top_5_data, start=1):
        ticker_raw = stock_info.get("ticker", "")  # e.g. "$QNC"
        # strip out leading '$' if present
        symbol = ticker_raw.lstrip("$") if ticker_raw else ""

        print("=" * 70)
        print(f"Stock #{idx} of 5: {symbol}")
        print("--- Info from trending page ---")
        print(f"  Ticker:           {stock_info.get('ticker', '')}")
        print(f"  Price:            {stock_info.get('price', '')}")
        print(f"  Change (amt):     {stock_info.get('price_change_amount', '')}")
        print(f"  Change (pct):     {stock_info.get('price_change_percent', '')}")
        print(f"  High / Low:       {stock_info.get('high', '')} / {stock_info.get('low', '')}")
        print(f"  Ask:              {stock_info.get('ask', '')}")
        print(f"  Bid:              {stock_info.get('bid', '')}")
        print(f"  Company Name:     {stock_info.get('company_name', '')}")
        print(f"  Volume:           {stock_info.get('volume', '')}")

        # 3) Now fetch chat for that symbol from last 3 hours
        print("\n--- Recent Chat (past 3h) ---")
        recent_msgs = scrape_stock_chat(symbol, time_window_hours=3)
        if not recent_msgs:
            print("  No messages found in last 3 hours.")
        else:
            for m in recent_msgs:
                print("  ------------------------------------------------")
                print(f"  User:      {m['username']}")
                print(f"  Time:      {m['time_text']}")
                print(f"  Message:   {m['message']}")

        print("\n")  # spacing before next stock


if __name__ == "__main__":
    main()
