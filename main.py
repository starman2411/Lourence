import json
import requests
import pandas as pd
from threading import Thread
from time import sleep
import telebot
from datetime import datetime
from config import *

telegram_bot = telebot.TeleBot('5414698881:AAHUOO1SgvHto-1e_kNFTxMKWEPvoy1W-6U')

def make_true_timestamp(t):
    return datetime.fromtimestamp(int(t[:-3]))

def calc_rsi(data):
    data = list(data)
    up = 0
    down = 0
    for i in range(1, len(data)):
        if data[i] < data[i-1]:
            down += data[i-1] - data[i]
        else:
            up += data[i] - data[i-1]
    rs = up / down if down != 0 else 0
    rsi = round(100 - 100/(1+rs)) if rs != 0 else 100
    return rsi


class TradingBot():
    def __init__(self, profit, bot_name, rsi_window, rsi_threshold):
        self.profit = profit
        self.bot_name = bot_name
        self.eth_balance = 2
        self.btc_balance = 1
        self.order_number = 1
        self.open_orders = {}
        self.closed_orders = {}
        self.rsi_window = rsi_window
        self.rsi_threshold = rsi_threshold
        self.load_orders()
        self.one_trade_eth_amount = 0.03
        self.last_rsi = 0

    def buy(self, price, amount):
        if len(self.open_orders) <= MAX_OPEN_ORDERS:
            self.eth_balance += amount
            self.btc_balance -= amount * price + 0.00155 * (amount * price)
            self.open_orders.update(
                [(str(self.order_number),
                  {'buy_date': str(datetime.now()), 'amount': str(amount), 'buy_price': str(price)})])

            text = (
                f'{self.bot_name} купил 0.03 эфира по цене {price} (order {self.order_number}). Текущий баланс: ETH- {self.eth_balance} BTC- {self.btc_balance}')
            telegram_bot.send_message(chat_id='260049736', text=text)
            print(text)
            self.order_number = len(self.open_orders) + len(self.closed_orders)
            self.save_orders()
        else:
            pass

    def sell(self, price, order):
        time_passed = str(
            datetime.now() - datetime.strptime(self.open_orders[str(order)]['buy_date'], '%Y-%m-%d %H:%M:%S.%f'))
        self.eth_balance -= float(self.open_orders[str(order)]['amount'])
        self.btc_balance += float(self.open_orders[str(order)]['amount']) * price * 0.99845
        self.closed_orders.update([(str(order), {'buy_date': str(self.open_orders[str(order)]['buy_date']),
                                                 'sell_date': str(datetime.now()), 'time_passed': time_passed,
                                                 'amount': self.open_orders[str(order)]['amount'],
                                                 'sell_price': str(price),
                                                 'buy_price': str(self.open_orders[str(order)]['buy_price'])})])

        text = (
            f'{self.bot_name} продал 0.03 эфира по цене {price} ({order}). Текущий баланс: ETH- {self.eth_balance} BTC- {self.btc_balance}  Прошло времени- {time_passed}')
        telegram_bot.send_message(chat_id='260049736', text=text)
        self.open_orders.pop(str(order))
        print(text)
        self.save_orders()

    def save_orders(self):
        try:
            with open(f"orders/{self.bot_name}s_open_orders.json", "w") as json_file:
                json.dump(self.open_orders, json_file)
            with open(f"orders/{self.bot_name}s_closed_orders.json", "w") as json_file:
                json.dump(self.closed_orders, json_file)
        except:
            print('не удалось сохранить ордера')

    def load_orders(self):
        try:
            with open(f"orders/{self.bot_name}s_open_orders.json", 'r') as json_file:
                self.open_orders = json.load(json_file)
            with open(f"orders/{self.bot_name}s_closed_orders.json", 'r') as json_file:
                self.closed_orders = json.load(json_file)
        except:
            print('не удалось загрузить ордера')

    def fill_pool(self):
        if not self.last_rsi:
            try:
                self.last_rsi, _ = get_two_last_rsi(self.rsi_window)
                return 1
            except:
                return 0
        return 0


class TradingBotReversed(TradingBot):

    def sell(self, price, amount):
        if len(self.open_orders) <= MAX_OPEN_ORDERS:
            self.eth_balance -= amount
            self.btc_balance += amount * price * 0.99845
            self.open_orders.update(
                [(str(self.order_number),
                  {'sell_date': str(datetime.now()), 'amount': str(amount), 'sell_price': str(price)})])

            text = (
                f'{self.bot_name} продал 0.03 эфира по цене {price} (order {self.order_number}). Текущий баланс: ETH- {self.eth_balance} BTC- {self.btc_balance}')
            telegram_bot.send_message(chat_id='260049736', text=text)
            print(text)
            self.order_number = len(self.open_orders) + len(self.closed_orders)
            self.save_orders()
        else:
            pass

    def buy(self, price, order):
        time_passed = str(
            datetime.now() - datetime.strptime(self.open_orders[str(order)]['sell_date'], '%Y-%m-%d %H:%M:%S.%f'))
        self.eth_balance += float(self.open_orders[str(order)]['amount'])
        self.btc_balance -= float(self.open_orders[str(order)]['amount']) * price * 1.00155
        self.closed_orders.update([(str(order), {'sell_date': str(self.open_orders[str(order)]['sell_date']),
                                                 'buy_date': str(datetime.now()), 'time_passed': time_passed,
                                                 'amount': self.open_orders[str(order)]['amount'],
                                                 'buy_price': str(price),
                                                 'sell_price': str(self.open_orders[str(order)]['sell_price'])})])

        text = (
            f'{self.bot_name} купил 0.03 эфира по цене {price} ({order}). Текущий баланс: ETH- {self.eth_balance} BTC- {self.btc_balance}  Прошло времени- {time_passed}')
        telegram_bot.send_message(chat_id='260049736', text=text)
        self.open_orders.pop(str(order))
        print(text)
        self.save_orders()


def get_two_last_rsi(rsi_window):
    params = {
        'interval': 'MINUTE_1',
        'limit': str(rsi_window ),
    }

    response = json.loads(requests.get(f'https://api.poloniex.com/markets/ETH_BTC/candles?', params=params).text)
    df_of_candles = pd.DataFrame(response)
    df_of_candles.columns = [str(i) for i in range(14)]
    df_of_candles = df_of_candles[['0', '1', '2', '3', '5', '13']]
    df_of_candles = df_of_candles.rename(
        columns={'0': 'low', '1': 'high', '2': 'open', '3': 'close', '5': 'volume', '13': 'time'})

    df_of_candles["open"] = df_of_candles['open'].astype('float')
    df_of_candles["close"] = df_of_candles['close'].astype('float')
    df_of_candles["low"] = df_of_candles['open'].astype('float')
    df_of_candles["high"] = df_of_candles['close'].astype('float')
    df_of_candles["volume"] = df_of_candles['volume'].astype('float')
    df_of_candles["time"] = df_of_candles['time'].astype('str')

    df_of_candles['time'] = df_of_candles['time'].apply(make_true_timestamp)
    df_of_candles['time'] = df_of_candles['time'].astype('datetime64[ns, UTC]')

    df_of_candles = pd.concat([df_of_candles[::-1][:rsi_window][::-1]], ignore_index=True)

    for i, row in df_of_candles.iloc[1:].iterrows():
        if (df_of_candles['time'].iloc[i] - df_of_candles['time'].iloc[i - 1]).total_seconds() > 60:
            return 0

    rsi = calc_rsi(df_of_candles['close'].iloc[1:])
    last_price = df_of_candles['close'].iloc[-1]
    return rsi, last_price


def get_last_price():
    price = float(json.loads(requests.get('https://api.poloniex.com/markets/ETH_BTC/price').text)['price'])
    return price


class Melhior(TradingBot):
    def check_buy_opportunity(self):
        rsi1 = self.last_rsi
        rsi2, price = get_two_last_rsi(self.rsi_window)
        self.last_rsi = rsi2
        print(rsi1,' ', rsi2,' ', price, ' ', datetime.now())
        if (rsi2 > self.rsi_threshold) and (rsi1 <= self.rsi_threshold):
            self.buy(price, self.one_trade_eth_amount)
            return 1
        return 0

    def check_sell_opportunity(self):
        last_price = get_last_price()
        print(last_price)
        for key in list(self.open_orders):
            if float(self.open_orders[key]['buy_price']) * (1 + self.profit) <= last_price:
                self.sell(last_price, key)


class Casper(TradingBotReversed):
    def check_sell_opportunity(self):
        rsi1 = self.last_rsi
        rsi2, price = get_two_last_rsi(self.rsi_window)
        self.last_rsi = rsi2
        print(rsi1,' ', rsi2,' ', price, ' ', datetime.now())
        if (rsi2 < self.rsi_threshold) and (rsi1 >= self.rsi_threshold):

            self.sell(price, self.one_trade_eth_amount)
            return 1
        return 0

    def check_buy_opportunity(self):
        last_price = get_last_price()
        print(last_price)
        for key in list(self.open_orders):
            if float(self.open_orders[key]['sell_price']) * (1 - self.profit) >= last_price:
                self.buy(last_price, key)


class BotThread(Thread):
    def __init__(self, bot):
        Thread.__init__(self)
        self.bot = bot
        self.order_delay = 5*60

    def run(self):
        bot_ready = False
        while not bot_ready:
            bot_ready = self.bot.fill_pool()
            if bot_ready:
                break
            else:
                sleep(5)
        telegram_bot.send_message(chat_id='260049736', text=f'{self.bot.bot_name} начал торговлю')
        t = 0
        buy_opportunity_trigger = True
        sleep(60)
        while True:
            try:
                self.bot.check_sell_opportunity()
                sleep(1)
                if buy_opportunity_trigger:
                    if self.bot.check_buy_opportunity():
                        buy_opportunity_trigger = False
                sleep(60)
                if not buy_opportunity_trigger:
                    if t<self.order_delay:
                        t += 60
                    else:
                        t=0
                        buy_opportunity_trigger = True
            except:
                print(f'ошибка у {self.bot.bot_name}')
                sleep(10)

class ReversedBotThread(Thread):
    def __init__(self, bot):
        Thread.__init__(self)
        self.bot = bot
        self.order_delay = 5*60

    def run(self):
        bot_ready = False
        while not bot_ready:
            bot_ready = self.bot.fill_pool()
            if bot_ready:
                break
            else:
                sleep(5)
        telegram_bot.send_message(chat_id='260049736', text=f'{self.bot.bot_name} начал торговлю')
        t = 0
        sell_opportunity_trigger = True
        sleep(60)
        while True:
            try:
                self.bot.check_buy_opportunity()
                sleep(1)
                if sell_opportunity_trigger:
                    if self.bot.check_sell_opportunity():
                        sell_opportunity_trigger = False
                sleep(60)
                if not sell_opportunity_trigger:
                    if t<self.order_delay:
                        t += 60
                    else:
                        t=0
                        sell_opportunity_trigger = True
            except:
                print(f'ошибка у {self.bot.bot_name}')
                sleep(10)

class TelebotThread(Thread):
    def __init__(self, telegram_bot):
        Thread.__init__(self)
        self.bot = telegram_bot

    def run(self):
        self.bot.polling(none_stop=True, interval=0)


@telegram_bot.message_handler(commands=["orders"])
def handle_text(message):
    telegram_bot.send_message(message.chat.id, 'Открытые ордера Мельхиора: \n' + str(melhior.open_orders) + '\n' + 'Закрытые ордера Мельхиора: \n' + str(melhior.closed_orders))
    telegram_bot.send_message(message.chat.id, 'Открытые ордера Каспера: \n' + str(
        casper.open_orders) + '\n' + 'Закрытые ордера Каспера: \n' + str(casper.closed_orders))



melhior = Melhior(0.006, 'Melhior', 30, 25)
casper = Casper(0.006, 'Casper', 30, 75)

thread0 = TelebotThread(telegram_bot)
thread0.start()
sleep(2)
thread1 = BotThread(melhior)
thread1.start()
sleep(2)
thread2 = ReversedBotThread(casper)
thread2.start()