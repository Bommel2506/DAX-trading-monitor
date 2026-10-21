"""DAX screening notifications for GitHub Actions; not trading advice."""
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

BERLIN = ZoneInfo('Europe/Berlin')
WATCH = {
    'SAP': 'SAP.DE', 'Siemens': 'SIE.DE', 'Rheinmetall': 'RHM.DE',
    'Allianz': 'ALV.DE', 'Deutsche Bank': 'DBK.DE',
    'Deutsche Telekom': 'DTE.DE', 'BMW': 'BMW.DE',
    'Mercedes-Benz': 'MBG.DE', 'BASF': 'BAS.DE',
    'Infineon': 'IFX.DE', 'Munich Re': 'MUV2.DE',
    'Siemens Energy': 'ENR.DE', 'Adidas': 'ADS.DE',
    'Volkswagen Vz.': 'VOW3.DE', 'DHL Group': 'DHL.DE',
}


def load(ticker):
    data = yf.download(ticker, period='5d', interval='5m', auto_adjust=True,
                       progress=False, prepost=False, threads=False)
    if data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().copy()
    data.index = pd.to_datetime(data.index)
    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC')
    data.index = data.index.tz_convert(BERLIN)
    return data.between_time('09:00', '17:30')


def candidate(name, ticker, index_data, now):
    d = load(ticker)
    if len(d) < 60:
        return None
    today = d[d.index.date == now.date()].copy()
    if len(today) < 8:
        return None
    # Do not alert on stale intraday prices.
    last_candle = today.index[-1].to_pydatetime()
    if not timedelta(0) <= now - last_candle <= timedelta(minutes=20):
        return None
    close = d.Close.astype(float)
    e20 = close.ewm(span=20, adjust=False).mean()
    e50 = close.ewm(span=50, adjust=False).mean()
    cur = float(today.Close.iloc[-1])
    first = float(today.Open.iloc[0])
    dayreturn = (cur / first - 1) * 100
    idx_today = index_data[index_data.index.date == now.date()] if not index_data.empty else pd.DataFrame()
    if len(idx_today) < 6:
        return None
    idx_last = idx_today.index[-1].to_pydatetime()
    if not timedelta(0) <= now - idx_last <= timedelta(minutes=20):
        return None
    idx_return = (float(idx_today.Close.iloc[-1]) / float(idx_today.Open.iloc[0]) - 1) * 100
    prev = d[(d.index.date != now.date()) &
             (d.index.strftime('%H:%M') == today.index[-1].strftime('%H:%M'))]
    rv = (float(today.Volume.iloc[-1]) / float(prev.Volume.mean())
          if len(prev) >= 2 and prev.Volume.mean() > 0 else None)
    cumvol = today.Volume.cumsum()
    vwap = (float((((today.High + today.Low + today.Close) / 3) * today.Volume)
                  .cumsum().iloc[-1] / cumvol.iloc[-1]) if cumvol.iloc[-1] > 0 else None)
    bull = bool(e20.iloc[-1] > e50.iloc[-1] and e20.iloc[-1] > e20.iloc[-4] and cur > e20.iloc[-1])
    proxy = bool(today.Low.iloc[-7:-1].min() <= float(e20.iloc[-2]) * 1.003 and
                 today.Close.iloc[-1] > today.High.iloc[-2])
    gates = (bull, dayreturn > idx_return, vwap is not None and cur > vwap,
             rv is not None and rv >= 1.3, proxy)
    if not all(gates):
        return None
    return f'{name} ({ticker}): {cur:.2f} EUR | 5/5 Filter | Kerze {last_candle:%H:%M}'


def send_telegram(message):
    token = os.environ['TELEGRAM_BOT_TOKEN'].strip()
    chat_id = os.environ['TELEGRAM_CHAT_ID'].strip()
    body = urllib.parse.urlencode({'chat_id': chat_id, 'text': message}).encode('utf-8')
    request = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=body)
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f'Telegram HTTP {response.status}')


def main():
    now = datetime.now(BERLIN)
    if now.weekday() >= 5 or not ((now.hour, now.minute) >= (9, 15) and
                                   (now.hour, now.minute) <= (17, 30)):
        print('Außerhalb der Xetra-Prüfzeit; keine Meldung.')
        return
    if not os.getenv('TELEGRAM_BOT_TOKEN') or not os.getenv('TELEGRAM_CHAT_ID'):
        raise RuntimeError('GitHub Actions Secrets TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID fehlen.')
    index_data = load('^GDAXI')
    found = []
    for name, ticker in WATCH.items():
        try:
            result = candidate(name, ticker, index_data, now)
            if result:
                found.append(result)
        except Exception as exc:
            print(f'{ticker}: Datenfehler: {type(exc).__name__}: {exc}', file=sys.stderr)
    if found:
        message = ('DAX-Monitor: Kandidaten zur manuellen Prüfung\n'
                   + '\n'.join(found)
                   + '\nKeine Kaufempfehlung. Kurse ggf. verzögert; Nachrichten, Risiko und Brokerkurs selbst prüfen.')
        send_telegram(message)
        print(f'Telegram-Alarm gesendet: {len(found)} Kandidat(en).')
    else:
        print('Keine Kandidaten mit 5/5 Kriterien.')


if __name__ == '__main__':
    main()
