from time import sleep

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


# 1 interval = 15s
def checkIfPriceWentUp(coin_name: str, intervals: int, min_price_change_percent: float):
    id = getIndexOfCoin(coin_name)
    current_price = prices[id]["data"]["current_price"]
    if len(prices[id]["data"]["price_history"]) >= intervals + 1:
        historic_price = prices[id]["data"]["price_history"][-1 * intervals]["price"]
    else:
        historic_price = prices[id]["data"]["price_history"][0]["price"]
    if current_price > historic_price:
        price_change = (current_price / historic_price * 100) - 100
        price_change = float("{:.3f}".format(price_change))
        notification = (f"======================\n"
                        f"{coin_name}\n💹{price_change}%\n{historic_price}$ => {current_price}$\n"
                        f"since {prices[id]['data']['price_history'][-1 * intervals]['timestamp']}\n"
                        f"======================")
        if price_change >= min_price_change_percent:
            sendTelegramNotification(notification)

        print(notification)
    elif current_price < historic_price:
        price_change = 100 - (current_price / historic_price * 100)
        price_change = float("{:.3f}".format(price_change))
        notification = (f"======================\n"
                        f"{coin_name}\n📉{price_change}%\n{historic_price}$ => {current_price}$\n"
                        f"since {prices[id]['data']['price_history'][-1 * intervals]['timestamp']}\n"
                        f"======================")
        if price_change >= min_price_change_percent:
            sendTelegramNotification(notification)

        print(notification)


# add saving to file
def addPriceHistory(coin_name: str, date_to_add: str, price_to_add: float):
    id = getIndexOfCoin(coin_name)
    prices[id]["data"]["current_price"] = price_to_add
    prices[id]["data"]["timestamp_of_current_price"] = date_to_add
    prices[id]["data"]["price_history"].append({"timestamp": date_to_add, "price": price_to_add})
    open("prices.json", "w").write(json.dumps(prices, indent=2))
    checkIfPriceWentUp(coin_name, intervals=INTERVALS, min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_1H)


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
            price = float("{:.8f}".format(float(coin['quote']['USD']['price'])))
            date = coin['last_updated']
            if getIndexOfCoin(coin_name) == -1:
                prices.append({"coin_name": coin_name,
                               "data": {
                                   "current_price": 0.0,
                                   "timestamp_of_current_price": "",
                                   "currency": "USD",
                                   "price_history": []
                               }})
            addPriceHistory(coin_name, date, price)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)
    sleep(seconds_between_checks)
