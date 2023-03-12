from typing import Optional
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
import pickle
from datetime import datetime as dt
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import numpy as np
import network as NN
import os
import csv

@dataclass
class Form:
    # Same for both sources
    filing_date: Optional[str] = None
    trade_date: Optional[str] = None
    ticker: Optional[str] = None
    price: Optional[float] = None
    qty_bought: Optional[float] = None
    qty_owned: Optional[float] = None

    #Source: openinsider.com
    insider_name_link: Optional[str] = None 
    company_link: Optional[str] = None
    buyer_title: Optional[str] = None
    
    #Source: SEC Bulk Data
    accession_number: Optional[str] = None
    insider_name: Optional[str] = None 
    company_name: Optional[str] = None
    insider_relationship: Optional[str] = None 
    insider_title: Optional[str] = None 

    def delta_own(self):
        if self.qty_owned is None or self.qty_bought is None: return -1

        if self.qty_owned - self.qty_bought == 0:
            return 100
        else:
            return float(self.qty_bought / (self.qty_owned - self.qty_bought)) * 100

    def days_ago(self) -> int:
        assert self.filing_date is not None and self.trade_date is not None
        fd = dt.strptime(self.filing_date, "%Y-%m-%d")
        td = dt.strptime(self.trade_date,  "%Y-%m-%d")
        return (fd - td).days
    
    def __eq__(self, other) -> bool:
        return self.filing_date == other.filing_date and self.trade_date == other.trade_date and self.ticker == other.ticker and self.price == other.price and self.qty_bought == other.qty_bought and self.qty_owned == self.qty_owned
    
    def __ne__(self, other) -> bool:
        return not self.__eq__(other)


def get_data(n_pages) -> list[Form]:
    forms = []
    for page_number in range(1, n_pages + 1): # plus one because upper range is not inclusive 
        URL = f"http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=730&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=3&xp=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page={page_number}"
        page = requests.get(URL)
        soup = BeautifulSoup(page.content, "html.parser")

        table = soup.find("table", class_="tinytable").find("tbody")

        for row in table.find_all("tr"):
            form = Form("", "", "", -1.0, -1, -1, -1, "", "", "")
            for i, td in enumerate(row.find_all("td")):
                text = td.get_text().strip()
                if i == 1:
                    form.filing_date = text.split(" ")[0]
                if i == 2:
                    form.trade_date = text.split(" ")[0] # dt.strptime(text.split(" ")[0], "%Y-%m-%d")
                if i == 3:
                    form.ticker = text
                if i == 5:
                    form.insider_name_link = td.find("a")["href"]
                    form.insider_name_link = "http://openinsider.com" + form.insider_name_link
                if i == 6:
                    form.buyer_title = text
                if i == 8:
                    form.price = float(text[1:].replace(",", "")) # remove dollar sign and cast to float
                if i == 9:
                    form.qty_bought = int(text[1:].replace(",", "")) # remove plus sign at front of number and cast to int
                if i == 10:
                    form.qty_owned = int(text.replace(",", ""))

                form.company_link = f"http://openinsider.com/{form.ticker}"

            forms.append(form)

    return forms

def save_data(data, fname):
    with open(f"src/OpenInsider/Assets/{fname}.pkl", "wb") as file:
        pickle.dump(data, file)

def load_data(fname) -> list:
    with open(f"src/OpenInsider/Assets/{fname}.pkl", "rb") as file:
        data = pickle.load(file)
        return data

def tickers_from_data(forms: list[Form]):
    tickers = {}
    for form in forms:
        tickers[form.ticker] = 1

    return [key for key in tickers.keys()]

@dataclass
class Candle:
    date: str
    o: float
    c: float
    h: float
    l: float
    v: int

@dataclass
class Trade:
    form: Form
    candles: list[Candle]

    def calc_profit(self):
        profit: float = 0.0

        closes = [c.c for c in self.candles]
        _, peaks = get_peaks(closes)
        
        if len(peaks) != 0:
            for peak in peaks:
                profit += self.candles[peak].c
                profit /= len(peaks)
                return (profit / self.candles[0].c * 100) - 100
        
        # function needs to return a value so the sorted() function doesn't yell at me
        return sum_(closes) / len(closes)
        # return None


def get_trades_from_data(forms: list[Form]):
    trades = []

    for i, form in enumerate(forms):
        # print(f"{i / len(forms) * 100}%")
        to_date = dt.today()
        url = f"https://api.nasdaq.com/api/quote/{form.ticker}/historical?assetclass=stocks&fromdate=2020-02-27&limit=9999&todate={date(to_date.year, to_date.month, to_date.day)}"
        print(f"Request sent to: {url}")
        headers = {
            "authority": "api.nasdaq.com",
            "method": "GET",
            "path": "/api/quote/AAPL/historical?assetclass=stocks&fromdate=2023-01-22&limit=9999&todate=2023-02-22",
            "scheme": "https",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.5",
            "origin": "https://www.nasdaq.com",
            "referer": "https://www.nasdaq.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"NASDAQ API Request Status: {response.status_code}")

            if response.status_code != 200: 
                print(f"Failed status code: {form.ticker}")
                continue
            if response.json()["data"] is None or response.json()["data"]["tradesTable"] is None or response.json()["data"]["tradesTable"]["rows"] is None: 
                print(f"Json response was none: {form.ticker}; url: {url}")
                continue
            
            trade = Trade(form, [])
            for row in response.json()["data"]["tradesTable"]["rows"]:

                o = row["open"][1:].replace(",", "")
                cl = row["close"][1:].replace(",", "")
                h = row["high"][1:].replace(",", "")
                l = row["low"][1:].replace(",", "")
                v = row["volume"].replace(",", "")

                c = Candle(
                    row["date"], 
                    float(o)  if o  != 'N/A' else -1,
                    float(cl) if cl != 'N/A' else -1, 
                    float(h)  if h  != 'N/A' else -1, 
                    float(l)  if l  != 'N/A' else -1, 
                    int(v)    if v  != 'N/A' else -1
                )
                trade.candles.append(c)

            # find the index of the filing date within trade.candles
            dates = [candle.date for candle in trade.candles]
            fd_components = form.filing_date.replace("-", "/").split("/")

            #NOTE: make sure the data is starting at the filing date!
            new_date = f"{fd_components[1]}/{fd_components[2]}/{fd_components[0]}"
            i = dates.index(new_date)
            # print(f"{new_date} @ {i}")

            data_spread = 100
            if (i - data_spread) >= 0 and (i - data_spread) < len(trade.candles):
                trade.candles = trade.candles[i - data_spread : i]
            else:
                trade.candles = trade.candles[0 : i]

            trade.candles = trade.candles[::-1]
            trades.append(trade)

        except requests.exceptions.RequestException:
            pass
        except ValueError:
            pass
        except:
            pass

    return trades

def sum_(data):
    s: float = 0.0
    for d in data:
        s += d
    return s

def moving_avg(data: list, length: int):
    new_data = []
    window = []
    for d in data:
        if len(window) <= length:
            window.append(d)
        else:
            window = window[1:]
            window.append(d)

        new_data.append(sum_(window)/len(window))
    return new_data

def get_peaks(price_data: list):
    ma = moving_avg(price_data, 7)

    dist = 7
    height_multiplier = 1.05
    peaks, _ = find_peaks(ma, distance=dist, height=ma[0] * height_multiplier, width=5) # one week between peaks and peak must be a 5% increase from day 0

    # if the price didn't go up enough to find a peak with a 5% increase, remove
    # the height multiplier and slowly decrease the distance between peaks until
    # a peak is found. This is necesarry for stagnating stock data (seen in trades[1500:1600:20])
    while len(peaks) == 0 and dist >= 1:
        peaks, _ = find_peaks(ma, distance=dist, width=5) # one week between peaks and peak must be a 5% increase from day 0
        dist -= 1

    if len(peaks) == 0: return [], []

    for i in range(len(peaks)):
        if i < len(peaks) - 1:
            peaks[i] += 1 # shift each peak to the right one because seldom will you exit at the true peak of a stock

    return ma, peaks

def show_trade(trade: Trade, show_peaks: bool):
    prices = pd.DataFrame({
        "high"  : [candle.h  for candle in trade.candles],
        "low"   : [candle.l  for candle in trade.candles],
        "open"  : [candle.o  for candle in trade.candles],
        "close" : [candle.c  for candle in trade.candles]
    })
    green  = prices[prices.close >= prices.open] # green candles
    red    = prices[prices.close < prices.open] # red candles
    w1, w2 = 0.4, 0.02 # width of thick part and width of extrema

    _, ax = plt.subplots()
    # graph green candles (x, height, width, bottom, color)
    ax.bar(green.index, green.close - green.open, w1, green.open, color='green') # thick middle part
    ax.bar(green.index, green.high  - green.close, w2, green.close, color='black') # high price
    ax.bar(green.index, green.low  - green.open, w2, green.open, color='black') # low price
    
    ax.bar(red.index, red.close - red.open, w1, red.open, color='red') # thick middle part
    ax.bar(red.index, red.high  - red.open, w2, red.open, color='black') # high price
    ax.bar(red.index, red.low   - red.close, w2, red.close, color='black') # low price

    if show_peaks:
        ma, peaks = get_peaks(list(prices.close.array))
        ax.plot(ma)
        
        for peak in peaks:
            ax.plot(peak, ma[peak], "bo")

        

    title = f"{trade.form.ticker} @ {trade.candles[0].date} (FD: {trade.form.filing_date}, TD: {trade.form.trade_date})"
    ax.set_title(title)
    plt.show()

def read_in_tsv(file):
    """
    Take in a tsv from the historical form 4s folder and return a dictionary where
    the keys are accession numbers and the values are the rest of the row
    - removes any non-form 4s and transactions that are not purchases
    """

    return 

def get_historical_forms() -> dict[str, Form]:
    base = "src/OpenInsider/Assets/Historical_SEC_Filings"
    folders = os.listdir(base)

    forms: dict[str, Form] = {}

    for folder in folders:
        if not os.path.isdir(f"{base}/{folder}"): continue
        
        print(f"Entering {folder}")
        contents = os.listdir(f"{base}/{folder}")
        SUBMISSION, NON_DERIV_TRANS, REPORTING_OWNER = None, None, None
        fail_count = 0

        with open(f"{base}/{folder}/NONDERIV_TRANS.tsv", "r") as nf:
            NON_DERIV_TRANS = csv.DictReader(nf, delimiter="\t")
            for row in NON_DERIV_TRANS:
                if not (row["TRANS_FORM_TYPE"] == "4" and row["TRANS_CODE"] == "P"): continue

                key = row["ACCESSION_NUMBER"]
                trans_date = dt.strptime(row["TRANS_DATE"], "%d-%b-%Y").strftime("%Y-%m-%d") # format = DD-MONTH_ABREIVATION-YYYY
                share_price = row["TRANS_PRICEPERSHARE"]
                total_shares = row["SHRS_OWND_FOLWNG_TRANS"]
                nshares = row["TRANS_SHARES"]

                try:
                    if key not in forms:
                        form = Form(accession_number=key)
                        form.trade_date = trans_date
                        form.qty_bought = float(nshares)
                        form.qty_owned = float(total_shares)
                        form.price = float(share_price)
                        forms[key] = form
                    else:
                        print(f"DUPLICATE: {key}")
                except:
                    # print(f"failed @ {key}")
                    fail_count += 1
                    continue

        with open(f"{base}/{folder}/SUBMISSION.tsv", "r") as sf:
            SUBMISSION = csv.DictReader(sf, delimiter="\t")
            for row in SUBMISSION:
                if row["DOCUMENT_TYPE"] != "4": continue

                key = row["ACCESSION_NUMBER"]
                filing_date =   row["FILING_DATE"]

                filing_date = dt.strptime(filing_date, "%d-%b-%Y").strftime("%Y-%m-%d")
                try:
                    if key in forms:
                        forms[key].ticker = row["ISSUERTRADINGSYMBOL"]
                        print(forms[key].ticker)
                        forms[key].company_name = row["ISSUERNAME"]
                        forms[key].filing_date = filing_date
                except:
                    # print(f"no form @ {key}")
                    continue

        with open(f"{base}/{folder}/REPORTINGOWNER.tsv", "r") as rf:
            REPORTING_OWNER = csv.DictReader(rf, delimiter="\t")      
            for row in REPORTING_OWNER:
                key = row["ACCESSION_NUMBER"]
                try:
                    if key in forms:
                        forms[key].insider_name = row["RPTOWNERNAME"]
                        forms[key].insider_relationship = row["RPTOWNER_RELATIONSHIP"]
                        forms[key].insider_title = row["RPTOWNER_TITLE"]
                except:
                    # print(f"no form @ {key}")
                    continue  
    
        print(f"{fail_count} Failures")
        break
        
    return forms
    

if __name__ == "__main__":

    # forms: list[Form] = load_data("Forms")

    # trades: list[Trade] = load_data("Trades")

    forms = get_historical_forms()
    for key, value in forms.items():
        print(f"{key}: {value.ticker}")

    forms = [f for f in forms.values()]
    print(len(forms))

    # forms: list[Form] = load_data()
    # print(len(forms))

    print(tickers_from_data(forms))
    print(len(tickers_from_data(forms)))


    #TODO: just download 5 years of data for every ticker

    #NOTE: trade volume falls off as a predictor of profitability near 1 million shares because those big trades
    #      attract the attention of the SEC. Thus, a multi million share trade likely won't be acting on some really 
    #      good insider information because they don't want to get thrown in jail
    # ?

    #TODO: active vs. passive investments by looking at preceding stock movements
    #NOTE: active buy = has dropped less than 10% in the prevoius 6 months. IOW, the trader is *likely* not buying because 
    #      the stock is at a super low point. Hints at an upcoming catalyst 🤑

    #TODO: purchase month signals
    #NOTE: this refers to past buying/selling within the firm

    #TODO: get dictionary of "insider name" : [forms...]
    #! be careful not to get any sales!!!!!

    #TODO: get dictionary of "ticker" : [forms...]

    #TODO: quantify track record of both the insiders and the companies
