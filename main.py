from datetime import datetime, timedelta
from time import sleep

import pytz
import requests
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json

from decouple import config


COINMARKETCAP_API_TOKEN = config("COINMARKETCAP_API_TOKEN")
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = config("TELEGRAM_CHAT_ID")
MINIMUM_PRICE_CHANGE_TO_ALERT_5M = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_5M"))
MINIMUM_PRICE_CHANGE_TO_ALERT_15M = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_15M"))
MINIMUM_PRICE_CHANGE_TO_ALERT_1H = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_1H"))

INTERVALS = 60
seconds_between_checks = 60
prices: [] = json.loads(open("prices.json", "r").read())
coins: [] = json.loads(open("coins.json", "r").read())


def getIndexOfCoin(coin_name: str):
    id = 0
    for coin_data in prices:
        if coin_data["coin_name"] == coin_name:
            return id
        id += 1
    return -1


def checkIfPriceWasATHorATL(data: [], current_price):
    poland_tz = pytz.timezone('Europe/Warsaw')

    # Define the current time
    current_time = datetime.now(poland_tz)

    # Define the time threshold (1 hour)
    time_threshold = timedelta(hours=1)

    result = {
        "wasATH": True,
        "wasATL": True
    }

    # Iterate over price history
    for entry in data['price_history']:
        # Convert the timestamp string to a datetime object
        timestamp = datetime.strptime(entry['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")
        timestamp = pytz.utc.localize(timestamp).astimezone(poland_tz)

        # Check if the timestamp is within the time threshold
        if current_time - timestamp < time_threshold:
            # Check if the price has changed
            if entry['price'] > current_price:
                result["wasATH"] = False
            elif entry['price'] < current_price:
                result["wasATL"] = False
    return result


# 1 interval = 15s
def checkIfPriceWentUp(coin_name: str, coin_symbol: str, intervals: int, min_price_change_percent: float):
    id = getIndexOfCoin(coin_name)
    current_price = prices[id]["data"]["current_price"]
    if len(prices[id]["data"]["price_history"]) > intervals + 1:
        id_of_historical_price = -1 * intervals
        historic_price = prices[id]["data"]["price_history"][-1 * intervals]["price"]
    else:
        id_of_historical_price = 0
        historic_price = prices[id]["data"]["price_history"][0]["price"]

    ATH_ATL_1H = checkIfPriceWasATHorATL(prices[id]["data"], current_price)
    wasATH_1H = ATH_ATL_1H["wasATH"]
    wasATL_1H = ATH_ATL_1H["wasATL"]
    if current_price > historic_price and wasATH_1H:
        price_change = (current_price / historic_price * 100) - 100
        price_change = float("{:.3f}".format(price_change))
        notification = (f"======================\n"
                        f"{coin_symbol} - {coin_name}\n"
                        f"💹{price_change}%\n"
                        f"{current_price}$\n"
                        f"ATH in last hour\n"
                        f"since {prices[id]['data']['price_history'][id_of_historical_price]['timestamp']}\n"
                        f"======================")
        if price_change >= min_price_change_percent:
            sendTelegramNotification(notification)
    elif current_price < historic_price and wasATL_1H:
        price_change = 100 - (current_price / historic_price * 100)
        price_change = float("{:.3f}".format(price_change))
        notification = (f"======================\n"
                        f"{coin_symbol} - {coin_name}\n"
                        f"📉{price_change}%\n"
                        f"{current_price}$\n"
                        f"ATL in last hour\n"
                        f"since {prices[id]['data']['price_history'][id_of_historical_price]['timestamp']}\n"
                        f"======================")
        if price_change >= min_price_change_percent:
            sendTelegramNotification(notification)
    else:
        price_change = 100 - (current_price / historic_price * 100)
        price_change = float("{:.3f}".format(price_change))
        notification = (f"======================\n"
                        f"{coin_symbol} - {coin_name}\n"
                        f"📉{price_change}%\n"
                        f"{current_price}$\n"
                        f"since {prices[id]['data']['price_history'][id_of_historical_price]['timestamp']}\n"
                        f"======================")
        if price_change >= min_price_change_percent:
            print(notification)


# add saving to file
def addPriceHistory(coin_name: str, coin_symbol: str, date_to_add: str, price_to_add: float):
    id = getIndexOfCoin(coin_name)
    prices[id]["data"]["current_price"] = price_to_add
    prices[id]["data"]["timestamp_of_current_price"] = date_to_add
    prices[id]["data"]["price_history"].append({"timestamp": date_to_add, "price": price_to_add})
    open("prices.json", "w").write(json.dumps(prices, indent=2))
    checkIfPriceWentUp(coin_name, coin_symbol, intervals=INTERVALS, min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_1H)


def sendTelegramNotification(notification: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={notification}"
    requests.get(url).json()


url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest'
parameters = {
    'id': ','.join(map(lambda x: str(x["id"]), coins))
}
headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': COINMARKETCAP_API_TOKEN,
}

session = Session()
session.headers.update(headers)

while True:
    try:
        response = session.get(url, params=parameters)
        data = json.loads(response.text)
        for coin_id in data['data']:
            coin = data['data'][coin_id]
            coin_name = coin['name']
            coin_symbol = coin["symbol"]
            price = float("{:.8f}".format(float(coin['quote']['USD']['price'])))
            date = coin['last_updated']
            if getIndexOfCoin(coin_name) == -1:
                prices.append({"coin_name": coin_name,
                               "symbol": coin["symbol"],
                               "data": {
                                   "current_price": 0.0,
                                   "timestamp_of_current_price": "",
                                   "currency": "USD",
                                   "price_history": []
                               }})
            addPriceHistory(coin_name, coin_symbol, date, price)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)
    sleep(seconds_between_checks)
