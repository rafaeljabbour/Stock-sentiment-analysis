import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

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
        # Typically two <div>s: one for high, one for low
        if len(divs) == 2:
            high_text = divs[0].get_text(strip=True)  # e.g. "H 1.14"
            low_text = divs[1].get_text(strip=True)   # e.g. "L 0.89"
            data["high"] = high_text.replace("H", "").strip()
            data["low"] = low_text.replace("L", "").strip()
        else:
            data["high"] = None
            data["low"] = None
    else:
        data["high"] = None
        data["low"] = None

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

def scrape_ceo_ca():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://ceo.ca/content/companies?exchange=all&sort_by=trending&sector=All", wait_until="networkidle")
        time.sleep(3)

        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        container_divs = soup.find_all("div", class_="CompanyList_companyList__dhW2O CompanyList_oneCol__8FaIu")
        print("Found container_divs:", len(container_divs))

        if container_divs:
            company_cards = container_divs[0].find_all("a", class_="CompanyListCard_card__jDLs9")
            print(f"Found {len(company_cards)} company cards.")

            all_data = []
            for card in company_cards:
                card_data = parse_company_card(card)
                all_data.append(card_data)

            # Print the first 5 entries in a more readable format
            for entry in all_data[:5]:
                print("----------------------------------------")
                print(f"Ticker:            {entry.get('ticker', '')}")
                print(f"Price:             {entry.get('price', '')}")
                print(f"Change (amt):      {entry.get('price_change_amount', '')}")
                print(f"Change (percent):  {entry.get('price_change_percent', '')}")
                print(f"High:              {entry.get('high', '')}")
                print(f"Low:               {entry.get('low', '')}")
                print(f"Ask:               {entry.get('ask', '')}")
                print(f"Bid:               {entry.get('bid', '')}")
                print(f"Company Name:      {entry.get('company_name', '')}")
                print(f"Volume:            {entry.get('volume', '')}")
                print("----------------------------------------")
                #print(entry)
                
        else:
            print("No containers found for company list.")

        browser.close()

if __name__ == "__main__":
    scrape_ceo_ca()