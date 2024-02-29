import asyncio
import os
import random
import threading
from datetime import datetime, timedelta

import requests
import json
from decouple import config
from typing import List
import aiohttp
from rel import rel

# VERSION 3 - BINANCE REST API
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = config("TELEGRAM_CHAT_ID")
MINIMUM_PRICE_CHANGE_TO_ALERT_5M = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_5M"))
MINIMUM_PRICE_CHANGE_TO_ALERT_15M = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_15M"))
MINIMUM_PRICE_CHANGE_TO_ALERT_1H = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_1H"))
MINIMUM_PRICE_CHANGE_TO_ALERT_4H = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_4H"))
MINIMUM_PRICE_CHANGE_TO_ALERT_8H = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_8H"))
MINIMUM_PRICE_CHANGE_TO_ALERT_24H = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_24H"))
MINIMUM_PRICE_CHANGE_TO_ALERT_7D = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_7D"))
MINIMUM_PRICE_CHANGE_TO_ALERT_30D = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_30D"))


class PriceEntry:
    def __init__(self, price: float, timestamp: datetime):
        self.price = price
        self.timestamp = timestamp


class Token:
    def __init__(self, symbol):
        self.symbol = symbol  # BTC
        self.currency: str = "USD"
        self.price_history: List[PriceEntry] = []

    def getCurrentPrice(self):
        if len(self.price_history) == 0:
            return 0.0
        return self.price_history[-1].price

    def getCurrentPriceDatetime(self):
        if len(self.price_history) == 0:
            return datetime.now()
        return self.price_history[-1].timestamp

    def addPriceEntry(self, price: float, _timestamp: datetime):
        if self.getCurrentPrice() == price:
            return
        self.price_history.append(PriceEntry(price=price, timestamp=_timestamp))
        self.checkIfPriceChanged(time_frame={"minutes": 5},
                                 min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_5M)
        self.checkIfPriceChanged(time_frame={"minutes": 15},
                                 min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_15M)
        self.checkIfPriceChanged(time_frame={"hours": 1},
                                 min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_1H)
        self.checkIfPriceChanged(time_frame={"hours": 4},
                                 min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_4H)
        self.checkIfPriceChanged(time_frame={"hours": 8},
                                 min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_8H)
        self.checkIfPriceChanged(time_frame={"hours": 24},
                                 min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_24H)
        self.checkIfPriceChanged(time_frame={"days": 7},
                                 min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_24H)
        self.checkIfPriceChanged(time_frame={"days": 30},
                                 min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_24H)
        #saveTokensHistoryToFIle()

    def getNearestPriceEntryToTimeframe(self, time_frame):
        # Parse current datetime
        current_datetime = datetime.now()

        # Initialize variables to store the closest entry and its difference
        closest_entry = None
        closest_difference = timedelta.max  # Initialize with a large value

        # Define the timedelta object
        time_delta = timedelta(**time_frame)

        # Get the reference time by subtracting the time delta from the current datetime
        reference_time = current_datetime - time_delta

        # Iterate through each entry in price history
        for entry in self.price_history:
            # Calculate the difference between the timestamp and the current time
            time_difference = abs(entry.timestamp - reference_time)

            # Check if the current entry is closer than the current closest entry
            if time_difference < closest_difference:
                closest_entry = entry
                closest_difference = time_difference

        return closest_entry

    def checkIfPriceChanged(self, time_frame, min_price_change_percent: float):
        historic_price_obj = self.getNearestPriceEntryToTimeframe(time_frame)
        historic_price = historic_price_obj.price
        historic_price_timestamp = historic_price_obj.timestamp

        ATH_ATL = self.checkIfPriceWasATHorATL(time_frame)
        wasATH = ATH_ATL["wasATH"]
        wasATL = ATH_ATL["wasATL"]
        if self.getCurrentPrice() > historic_price and wasATH:
            price_change = (self.getCurrentPrice() / historic_price * 100) - 100
            price_change = float("{:.3f}".format(price_change))
            notification = (f"======================\n"
                            f"{self.symbol}\n"
                            f"💹{price_change}%\n"
                            f"{self.getCurrentPrice()}$\n"
                            f"ATH in {time_frame}\n"
                            f"since {historic_price_timestamp}\n"
                            f"======================")
            if price_change >= min_price_change_percent:
                sendTelegramNotification(notification)
        elif self.getCurrentPrice() < historic_price and wasATL:
            price_change = 100 - (self.getCurrentPrice() / historic_price * 100)
            price_change = float("{:.3f}".format(price_change))
            notification = (f"======================\n"
                            f"{self.symbol}\n"
                            f"📉{price_change}%\n"
                            f"{self.getCurrentPrice()}$\n"
                            f"ATL in {time_frame}\n"
                            f"since {historic_price_timestamp}\n"
                            f"======================")
            if price_change >= min_price_change_percent:
                sendTelegramNotification(notification)
        else:
            price_change = 100 - (self.getCurrentPrice() / historic_price * 100)
            price_change = float("{:.3f}".format(price_change))
            notification = (f"======================\n"
                            f"{self.symbol}\n"
                            f"📉{price_change}%\n"
                            f"{self.getCurrentPrice()}$\n"
                            f"timeframe: {time_frame}\n"
                            f"since {historic_price_timestamp}\n"
                            f"======================")
            if price_change >= min_price_change_percent:
                print(notification)

    def checkIfPriceWasATHorATL(self, time_delta):
        # Define the time threshold (1 hour)
        time_threshold = timedelta(**time_delta)

        result = {
            "wasATH": True,
            "wasATL": True
        }

        # Iterate over price history
        for entry in self.price_history:
            # Check if the timestamp is within the time threshold
            if datetime.now() - entry.timestamp < time_threshold:
                # Check if the price has changed
                if entry.price > self.getCurrentPrice():
                    result["wasATH"] = False
                elif entry.price < self.getCurrentPrice():
                    result["wasATL"] = False
        return result


def sendTelegramNotification(notification: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={notification}"
    requests.get(url).json()


def loadCoinsToFetchFromFile():
    _coins: [] = json.loads(open("coins.json", "r").read())
    for coin in _coins:
        tokens.append(Token(coin["symbol"]))
    return _coins


def loadTokensHistoryFromFile():
    if not os.path.exists("prices.json"):
        file = open("prices.json", 'w')
        file.write("[]")
        file.close()
    _tokens: [] = json.loads(open("prices.json", "r").read())
    tokens_to_return: List[Token] = []
    for token_from_file in _tokens:
        token = Token(token_from_file["symbol"])
        token.currency = token_from_file["currency"]
        for price_history_entry in token_from_file["price_history"]:
            timestamp_format = "%Y-%m-%d %H:%M:%S"
            # Parse the string into a datetime object
            timestamp = datetime.strptime(price_history_entry["timestamp"], timestamp_format)
            token.price_history.append(PriceEntry(price_history_entry["price"], timestamp))
        tokens_to_return.append(token)
    return tokens_to_return


def saveTokensHistoryToFIle():
    tokens_json = []
    tokens_symbols = []
    for token in tokens:
        token_json = {
            "symbol": token.symbol,
            "currency": token.currency,
            "price_history": []
        }
        token_already_existing = True
        for price_entry in token.price_history:
            if token.symbol not in tokens_symbols or len(token.price_history) != 0:
                token_already_existing = False
                token_json["price_history"].append({"price": price_entry.price,
                                                    "timestamp": price_entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')})
                tokens_symbols.append(token.symbol)
        if not token_already_existing:
            tokens_json.append(token_json)
    open("prices.json", "w").write(json.dumps(tokens_json, indent=4))


def getIndexOfCoin(coin_symbol: str):
    id: int = 0
    for entry in tokens:
        if entry.symbol == coin_symbol:
            return id
        id += 1
    return -1


async def fetch_coin_price(session, coin, semaphore):
    await semaphore.acquire()
    example_output = """
            [
          [
            1499040000000,      // Kline open time
            "0.01634790",       // Open price
            "0.80000000",       // High price
            "0.01575800",       // Low price
            "0.01577100",       // Close price
            "148976.11427815",  // Volume
            1499644799999,      // Kline close time
            "2434.19055334",    // Quote asset volume
            308,                // Number of trades
            "1756.87402397",    // Taker buy base asset volume
            "28.46694368",      // Taker buy quote asset volume
            "0"                 // Unused field. Ignore.
          ]
        ]
    """
    urls = [
        f"https://pexljc3fiphfkworlrtv52mi2q0cqhke.lambda-url.eu-central-1.on.aws/?coin={coin['symbol']}USDT",
        f"https://api.binance.com/api/v3/uiKlines?symbol={coin['symbol']}USDT&interval=1m&limit=1"
    ]
    #print("starting checking " + coin['symbol'])
    try:
        async with session.get(random.choice(urls)) as resp:
            data = await resp.text()
            print(data)
            data = json.loads(data)
            coin_data = data[0]
            current_price = float(coin_data[4])
            token = tokens[getIndexOfCoin(coin["symbol"])]
            token.addPriceEntry(current_price, datetime.now())
            #print(f"{coin_data}")
    except:
        x = "err"
        print(x)
    semaphore.release()


async def fetch_all_coin_prices(coins):
    semaphore = asyncio.Semaphore(25)  # Limiting to 10 concurrent requests
    async with aiohttp.ClientSession() as session:
        while True:  # Run indefinitely
            async with semaphore:
                tasks = [fetch_coin_price(session, coin, semaphore) for coin in coins]
                await asyncio.gather(*tasks)


def save_to_file():
    threading.Timer(60.0, save_to_file).start()  # Run every 30 seconds
    saveTokensHistoryToFIle()
    print(f"Data saved to file at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    tokens: List[Token] = loadTokensHistoryFromFile()
    coins = loadCoinsToFetchFromFile()
    save_to_file()
    asyncio.run(fetch_all_coin_prices(coins))
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
