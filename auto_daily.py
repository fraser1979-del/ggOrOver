import datetime
import os
import pandas as pd
import requests

# Configurazione sessione globale per superare i blocchi di stats.nba.com
session = requests.Session()
session.headers.update({
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'X-NewRelic-ID': 'px3BWV5TCBABU1ZBAgUHNWU=',
    'Referer': 'https://www.nba.com/',
    'Connection': 'keep-alive',
})

from nba_api.stats.endpoints import leaguegamefinder

# ==========================================
# CONFIGURAZIONE NOTIFICHE TELEGRAM
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def invia_telegram(messaggio):
    """Invia un messaggio formattato al tuo bot Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Attenzione: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID non trovati nelle variabili d'ambiente.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": messaggio,
        "parse_mode": "Markdown"
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print("✅ Notifica Telegram inviata con successo!")
        else:
            print(f"❌ Errore Telegram ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Errore di connessione a Telegram: {e}")

# ==========================================
# ESECUZIONE REPORT GIORNALIERO AUTOMATICO
# ==========================================
def report_giornaliero_automatico():
    oggi = datetime.datetime.now().strftime("%Y-%m-%d")
    print("==========================================")
    print(f"   AVVIO ANALISI AUTOMATICA DAILY - {oggi}")
    print("==========================================")

    # Invia notifica di avvio su Telegram
    invia_telegram(f"🚀 **Avvio Analisi NBA Daily** - `{oggi}`")

    # Recupero dati NBA protetto da try/except
    df_cal = pd.DataFrame()
    try:
        game_finder = leaguegamefinder.LeagueGameFinder(
            season_nullable="2026-27",
            proxy=None,
            timeout=45
        )
        df_cal = game_finder.get_data_frames()[0]
    except Exception as e:
        print(f"⚠️ Impossibile collegarsi ai server NBA: {e}")

    # Gestione esito download dati
    if df_cal.empty:
        print("⚠️ Nessun dato a calendario disponibile o timeout API NBA.")
        invia_telegram("⚠️ **NBA Bot**: Server NBA temporaneamente offline o nessun dato presente a calendario.")
        return

    print(f"Analisi di {len(df_cal)} partite trovate a calendario...")

    print("==========================================")
    print("   ANALISI COMPLETATA CON SUCCESSO")
    print("==========================================")
    
    invia_telegram(f"✅ **Analisi NBA completata con successo per il {oggi}**!")

if __name__ == "__main__":
    report_giornaliero_automatico()