 
# DAX-Monitor 2.0 - Vorboersenbericht (Testversion)
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import yfinance as yf
BERLIN = ZoneInfo("Europe/Berlin")
AKTIEN = {"Siemens Energy": "ENR.DE"}
def aktienkurs_abrufen(symbol):
    daten = yf.Ticker(symbol).history(period="5d", interval="1d")
    if daten.empty:
        return None  
    return float(daten["Close"].iloc[-1]), str(daten.index[-1].date())
def telegram_senden(nachricht):
    token = os.environ.get("TELEGRAM_BOT_TOKEN").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise RuntimeError("Telegram-Zugangsdaten fehlen.")

    antwort = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": nachricht},
        timeout=20,
    )
    antwort.raise_for_status()
    if not antwort.json().get("ok"):
        raise RuntimeError("Telegram hat die Nachricht abgelehnt.")


def main():
    jetzt = datetime.now(BERLIN)
    kursdaten = aktienkurs_abrufen(AKTIEN["Siemens Energy"])
    if jetzt.weekday() >= 5:
        print("Wochenende - kein Bericht.")
        return

    stunde, minute = jetzt.hour, jetzt.minute

    if stunde == 7 and 30 <= minute <= 59:
        bericht = "07:30 - Erster Vorboersenbericht"
    elif stunde == 8 and 45 <= minute <= 59:
        bericht = "08:45 - Aktualisierter Vorboersenbericht"
    else:
        print("Ausserhalb der Berichtszeiten.")
        return

        kurs_text = "Siemens Energy: Keine Kursdaten verfügbar"
        if kursdaten is not None:
            kurs_text = f"Siemens Energy: Schlusskurs {kursdaten[0]:.2f} EUR vom {kursdaten[1]}"
        nachricht = (
        "DAX-Monitor 2.0 - TEST\n"
        + bericht
            + "\n" + kurs_text
        + "\nDie automatische Nachricht funktioniert."
        + "\nNoch keine Aktienanalyse oder Handelssignale."
    )

    telegram_senden(nachricht)
    print("Telegram-Testbericht versendet.")


if __name__ == "__main__":
    main()
if os.getenv("TELEGRAM_TEST") == "1": telegram_senden("DAX-Monitor 2.0: Telegram-Test erfolgreich!")
