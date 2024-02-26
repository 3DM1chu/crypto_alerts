from datetime import datetime, timedelta
from time import sleep
import requests
import websocket
from rel import rel
import json
from decouple import config
from typing import List
from websocket import WebSocketApp

# VERSION 2 - BINANCE API
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = config("TELEGRAM_CHAT_ID")
MINIMUM_PRICE_CHANGE_TO_ALERT_1H = float(config("MINIMUM_PRICE_CHANGE_TO_ALERT_1H"))
MINIMUM_PRICE_CHANGE_TO_SAVE_ENTRY = float(config("MINIMUM_PRICE_CHANGE_TO_SAVE_ENTRY"))

INTERVALS = 60
seconds_between_checks = 60


# prices: [] = json.loads(open("prices.json", "r").read())


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
        old_price = self.getCurrentPrice()
        self.price_history.append(PriceEntry(price=price, timestamp=_timestamp))
        # open("prices.json", "w").write(json.dumps(prices, indent=2))
        self.checkIfPriceWentUp(old_price, intervals=INTERVALS,
                                min_price_change_percent=MINIMUM_PRICE_CHANGE_TO_ALERT_1H)
        saveTokensHistoryToFIle()

    def checkIfPriceWentUp(self, old_price: float, intervals: int, min_price_change_percent: float):
        if self.getCurrentPrice() == old_price:
            return

        if len(self.price_history) > intervals + 1:
            id_of_historical_price = -1 * intervals
            historic_price = self.price_history[-1 * intervals].price
        else:
            id_of_historical_price = 0
            historic_price = self.price_history[0].price

        ATH_ATL_1H = self.checkIfPriceWasATHorATL()
        wasATH_1H = ATH_ATL_1H["wasATH"]
        wasATL_1H = ATH_ATL_1H["wasATL"]
        if self.getCurrentPrice() > historic_price and wasATH_1H:
            price_change = (self.getCurrentPrice() / historic_price * 100) - 100
            price_change = float("{:.3f}".format(price_change))
            notification = (f"======================\n"
                            f"{self.symbol}\n"
                            f"💹{price_change}%\n"
                            f"{self.getCurrentPrice()}$\n"
                            f"ATH in last hour\n"
                            f"since {self.price_history[id_of_historical_price].timestamp}\n"
                            f"======================")
            if price_change >= min_price_change_percent:
                sendTelegramNotification(notification)
        elif self.getCurrentPrice() < historic_price and wasATL_1H:
            price_change = 100 - (self.getCurrentPrice() / historic_price * 100)
            price_change = float("{:.3f}".format(price_change))
            notification = (f"======================\n"
                            f"{self.symbol}\n"
                            f"📉{price_change}%\n"
                            f"{self.getCurrentPrice()}$\n"
                            f"ATL in last hour\n"
                            f"since {self.price_history[id_of_historical_price].timestamp}\n"
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
                            f"since {self.price_history[id_of_historical_price].timestamp}\n"
                            f"======================")
            if price_change >= min_price_change_percent:
                print(notification)

    def checkIfPriceWasATHorATL(self):
        # Define the time threshold (1 hour)
        time_threshold = timedelta(hours=1)

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
    coins: [] = json.loads(open("coins.json", "r").read())
    for coin in coins:
        tokens.append(Token(coin["symbol"]))
    return coins


def loadTokensHistoryFromFile():
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
    for token in tokens:
        token_json = {
            "symbol": token.symbol,
            "currency": token.currency,
            "price_history": []
        }
        for price_entry in token.price_history:
            token_json["price_history"].append({"price": price_entry.price,
                                                "timestamp": price_entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')})
        tokens_json.append(token_json)
    open("prices.json", "w").write(json.dumps(tokens_json, indent=4))


def getIndexOfCoin(coin_symbol: str):
    id: int = 0
    for entry in tokens:
        if entry.symbol == coin_symbol:
            return id
        id += 1
    return -1


tokens: List[Token] = loadTokensHistoryFromFile()
coins = loadCoinsToFetchFromFile()


def on_message(ws: WebSocketApp, message):
    message_json = json.loads(message)
    if len(message_json) > 5:
        trading_pair = message_json["s"]
        coin_symbol = trading_pair.split("USDT")[0]
        current_price = float(message_json["p"])
        token = tokens[getIndexOfCoin(coin_symbol)]

        first_time = len(token.price_history) == 0
        price_change_too_low = False
        price_change = abs(100 - (token.getCurrentPrice() / current_price * 100))

        if first_time is False and price_change < MINIMUM_PRICE_CHANGE_TO_SAVE_ENTRY:
            price_change_too_low = True

        timestamp_unix = int(message_json["E"])
        timestamp_seconds = int(timestamp_unix / 1000.0)
        datetime_obj = datetime.fromtimestamp(timestamp_seconds)
        # time_difference = datetime_obj - token.getCurrentPriceDatetime()

        if not price_change_too_low:
            # print(f"{trading_pair} at {current_price}")
            token.addPriceEntry(current_price, datetime_obj)


def on_error(ws: WebSocketApp, error):
    print(error)


def on_close(ws: WebSocketApp, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws: WebSocketApp):
    print("Connecting to binance websocket...")
    obj = {
        "method": "SUBSCRIBE",
        "params": [],
        "id": 1
    }
    for coin in coins:
        symbol = str(coin["symbol"]).lower()
        #obj["params"].append(f"{symbol}usdt@aggTrade")
    obj["params"].append("akrousdt@aggTrade")
    print("Setupping coins to subscribe...")
    ws.send(json.dumps(obj))
    print("Sent coins to subscribe...")


# socket = 'wss://stream.binance.com:9443/ws/ckbusdt@kline_1s'
socket = 'wss://stream.binance.com:9443/ws'

if __name__ == "__main__":
    websocket.enableTrace(False)
    ws = WebSocketApp(socket,  # "wss://api.gemini.com/v1/marketdata/BTCUSD",
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever(dispatcher=rel,
                   reconnect=5)  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()

    sleep(seconds_between_checks)
