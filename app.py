import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title='DAX Aktienmonitor', page_icon='📈', layout='wide')
BERLIN=ZoneInfo('Europe/Berlin')
WATCH={
'SAP':'SAP.DE','Siemens':'SIE.DE','Rheinmetall':'RHM.DE','Allianz':'ALV.DE',
'Deutsche Bank':'DBK.DE','Deutsche Telekom':'DTE.DE','BMW':'BMW.DE',
'Mercedes-Benz':'MBG.DE','BASF':'BAS.DE','Infineon':'IFX.DE',
'Munich Re':'MUV2.DE','Siemens Energy':'ENR.DE','Adidas':'ADS.DE',
'Volkswagen Vz.':'VOW3.DE','DHL Group':'DHL.DE'}

@st.cache_data(ttl=240,show_spinner=False)
def load(ticker):
    data=yf.download(ticker,period='5d',interval='5m',auto_adjust=True,progress=False,prepost=False,threads=False)
    if data.empty:return pd.DataFrame()
    if isinstance(data.columns,pd.MultiIndex):data.columns=data.columns.get_level_values(0)
    data=data[['Open','High','Low','Close','Volume']].dropna().copy()
    data.index=pd.to_datetime(data.index)
    if data.index.tz is None:data.index=data.index.tz_localize('UTC')
    data.index=data.index.tz_convert(BERLIN)
    return data.between_time('09:00','17:30')

def calc(name,ticker,index_data):
    d=load(ticker)
    if len(d)<60:return {'Aktie':name,'Status':'DATEN FEHLEN','Grund':'Zu wenig 5-Minuten-Daten','Ticker':ticker}
    now=datetime.now(BERLIN)
    today=d[d.index.date==now.date()].copy()
    if len(today)<6:return {'Aktie':name,'Status':'DATEN FEHLEN','Grund':'Keine ausreichenden heutigen Kurse','Ticker':ticker}
    close=d.Close.astype(float)
    e20=close.ewm(span=20,adjust=False).mean()
    e50=close.ewm(span=50,adjust=False).mean()
    cur=float(today.Close.iloc[-1]); first=float(today.Open.iloc[0])
    dayreturn=(cur/first-1)*100
    idx_today=index_data[index_data.index.date==now.date()] if not index_data.empty else pd.DataFrame()
    idx_return=(float(idx_today.Close.iloc[-1])/float(idx_today.Open.iloc[0])-1)*100 if len(idx_today)>=6 else None
    relative=dayreturn-idx_return if idx_return is not None else None
    vol=float(today.Volume.iloc[-1]); prev=d[(d.index.date!=now.date())&(d.index.strftime('%H:%M')==today.index[-1].strftime('%H:%M'))]
    rv=vol/float(prev.Volume.mean()) if len(prev)>=2 and prev.Volume.mean()>0 else None
    typical=(today.High+today.Low+today.Close)/3
    cumvol=today.Volume.cumsum()
    vwap=float((typical*today.Volume).cumsum().iloc[-1]/cumvol.iloc[-1]) if cumvol.iloc[-1]>0 else None
    bull=bool(e20.iloc[-1]>e50.iloc[-1] and e20.iloc[-1]>e20.iloc[-4] and cur>e20.iloc[-1])
    abovevwap=vwap is not None and cur>vwap
    # Conservative observable proxy, not a fully verified pullback setup.
    proxy=bool(len(today)>=8 and today.Low.iloc[-7:-1].min()<=float(e20.iloc[-2])*1.003 and today.Close.iloc[-1]>today.High.iloc[-2])
    gates={'Trend':bull,'Relativ':relative is not None and relative>0,'VWAP':abovevwap,'Volumen':rv is not None and rv>=1.3,'M5 Trigger':proxy}
    score=sum(gates.values())
    # No automated BUY authorization: news, support, CRV and broker execution must be verified manually.
    status='KANDIDAT PRÜFEN' if score==5 else ('BEOBACHTEN' if score>=3 else 'KEIN SETUP')
    return {'Aktie':name,'Status':status,'Score':f'{score}/5','Kurs (€)':round(cur,2),'Seit 09:00 (%)':round(dayreturn,2),
            'Relativ zum DAX (PP)':round(relative,2) if relative is not None else None,
            'Rel. Volumen':round(rv,2) if rv is not None else None,'VWAP (€)':round(vwap,2) if vwap is not None else None,
            'Letzte Kerze':str(today.index[-1].strftime('%d.%m. %H:%M')),'Ticker':ticker,'Grund':', '.join(k for k,v in gates.items() if not v) or 'Alle automatischen Filter positiv'}

st.title('📈 DAX-Aktienmonitor | Trade Republic')
st.caption('Analyse- und Beobachtungswerkzeug – keine Orderausführung, keine Anlageberatung, keine garantierten Echtzeitdaten.')
with st.sidebar:
    st.header('Einstellungen')
    names=st.multiselect('Aktien',list(WATCH),default=list(WATCH))
    st.info('Zum Aktualisieren auf „Jetzt aktualisieren“ klicken. Optionales Auto-Refresh bei geöffneter Seite unten aktivieren.')
    if st.button('🔄 Jetzt aktualisieren',use_container_width=True):st.cache_data.clear();st.rerun()
    auto=st.checkbox('Automatisch alle 5 Minuten (nur bei offener Seite)',value=True)
    st.divider()
    st.markdown('**Freigabe vor dem Kauf**')
    st.write('☐ Nachrichten prüfen\n\n☐ Unterstützung und Pullback prüfen\n\n☐ Stop und 1,5-%-Ziel prüfen\n\n☐ CRV ≥ 2 nach Kosten\n\n☐ Spread und Trade-Republic-Kurs prüfen')
now=datetime.now(BERLIN)
if now.weekday()>=5 or not (9<=now.hour<18):st.warning('Außerhalb der regulären Xetra-Handelszeit: Daten können veraltet sein.')
if auto:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=300000,key='refresh')
    except ImportError:st.caption('Automatische Aktualisierung erfordert streamlit-autorefresh.')
with st.spinner('Kursdaten werden abgerufen …'):
    try:index_data=load('^GDAXI')
    except Exception:index_data=pd.DataFrame()
    rows=[]
    for name in names:
        try:rows.append(calc(name,WATCH[name],index_data))
        except Exception as exc:rows.append({'Aktie':name,'Status':'DATENFEHLER','Grund':str(exc)[:120],'Ticker':WATCH[name]})
if not rows:st.info('Bitte mindestens eine Aktie auswählen.')
else:
    frame=pd.DataFrame(rows)
    order={'KANDIDAT PRÜFEN':0,'BEOBACHTEN':1,'KEIN SETUP':2,'DATEN FEHLEN':3,'DATENFEHLER':4}
    frame['_sort']=frame.Status.map(order).fillna(5)
    frame=frame.sort_values(['_sort','Aktie']).drop(columns='_sort')
    a,b,c=st.columns(3)
    a.metric('Kandidaten zur Prüfung',int((frame.Status=='KANDIDAT PRÜFEN').sum()))
    b.metric('Beobachten',int((frame.Status=='BEOBACHTEN').sum()))
    c.metric('Analysierte Aktien',len(frame))
    st.dataframe(frame,hide_index=True,use_container_width=True)
    st.download_button('📥 Watchlist als CSV',frame.to_csv(index=False).encode('utf-8-sig'),'dax_watchlist.csv','text/csv')
    candidates=frame[frame.Status=='KANDIDAT PRÜFEN']
    if len(candidates):
        st.warning('Automatische Vorfilter positiv: '+', '.join(candidates.Aktie)+'. Kein Kaufsignal ohne manuelle Pflichtprüfung!')
        st.toast('DAX-Kandidaten zur manuellen Prüfung vorhanden',icon='🔎')
    st.subheader('Einzelaktie')
    chosen=st.selectbox('Chart anzeigen',list(frame.Aktie))
    symbol=WATCH[chosen]
    try:
        chart=load(symbol)
        chart=chart[chart.index.date==now.date()]
        if not chart.empty:st.line_chart(chart.Close)
    except Exception:pass
st.divider()
st.caption(f'Stand der Abfrage: {now:%d.%m.%Y %H:%M} Europe/Berlin. Abfragezeit ist nicht gleich Kurszeit. Datenquelle: Yahoo Finance via yfinance, möglicherweise verzögert oder unvollständig. Der M5-Trigger ist nur ein Screening-Proxy. Kein Backtest, keine Broker-API und keine Hintergrundbenachrichtigung im geschlossenen Browser.')

# Telegram-Verbindung: manueller Funktionstest, keine Hintergrundüberwachung.
st.divider()
st.subheader('📨 Telegram-Testalarm')
st.caption('Dieser Test sendet nur nach einem Klick eine Nachricht. Automatische Alarme bei geschlossenem Browser sind noch nicht eingerichtet.')
if st.button('📲 Testnachricht an Telegram senden', key='telegram_test'):
    try:
        import json
        import urllib.parse
        import urllib.request
        token = str(st.secrets['telegram']['bot_token']).strip()
        chat_id = str(st.secrets['telegram']['chat_id']).strip()
        if not token or not chat_id:
            st.error('Telegram-Zugangsdaten fehlen in Streamlit Secrets.')
        else:
            payload = urllib.parse.urlencode({
                'chat_id': chat_id,
                'text': '✅ DAX-Monitor: Telegram-Test erfolgreich!'
            }).encode('utf-8')
            request = urllib.request.Request(
                f'https://api.telegram.org/bot{token}/sendMessage',
                data=payload,
                method='POST'
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.load(response)
            if result.get('ok'):
                st.success('Die Testnachricht wurde an Telegram gesendet. Bitte den Bot-Chat prüfen.')
            else:
                st.error('Telegram hat die Nachricht nicht bestätigt. Bitte die Secrets prüfen.')
    except KeyError:
        st.error('In Streamlit Secrets fehlen [telegram], bot_token oder chat_id.')
    except Exception:
        st.error('Telegram-Test fehlgeschlagen. Bitte Bot-Token, Chat-ID und /start im Bot-Chat prüfen.')
