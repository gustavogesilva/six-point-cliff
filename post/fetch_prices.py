"""Download the daily prices behind the market chart (Yahoo Finance chart API) into data/prices/.

Usage (from the repo root):  python post/fetch_prices.py
Prices are not committed to the repo; Yahoo's terms don't allow redistributing them.
"""
import json, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICKERS = ['OWL', 'BX', 'KKR', 'ARES', 'APO', 'FSK', 'OBDC', 'BIZD', 'CRWV', 'STT', 'KRE', 'JPM', 'BKLN', 'HYG', '^GSPC', '^VIX',
           # listed BDCs used for the market-implied loan mark (P/NAV rolled forward from 6 Oct 2026)
           'ARCC', 'OTF', 'BXSL', 'GBDC', 'PSEC', 'MAIN', 'HTGC', 'MSDL', 'TSLX', 'GSBD', 'OCSL', 'BBDC', 'CGBD', 'KBDC', 'NMFC', 'TCPC']
START, END = 1776556800, 1792540800   # 19 Apr 2026 to 21 Oct 2026 (UTC)

out = ROOT / 'data' / 'prices'; out.mkdir(parents=True, exist_ok=True)
for t in TICKERS:
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}?period1={START}&period2={END}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        (out / f'{t}.json').write_bytes(r.read())
    print('saved', t); time.sleep(0.3)
