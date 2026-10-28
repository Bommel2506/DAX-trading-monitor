 
# DAX-Monitor 2.0 - Vorboersenbericht (Testversion)
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

BERLIN = ZoneInfo("Europe/Berlin")


def telegram_senden(nachricht):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
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

    nachricht = (
        "DAX-Monitor 2.0 - TEST\n"
        + bericht
        + "\nDie automatische Nachricht funktioniert."
        + "\nNoch keine Aktienanalyse oder Handelssignale."
    )

    telegram_senden(nachricht)
    print("Telegram-Testbericht versendet.")


if __name__ == "__main__":
    main()
