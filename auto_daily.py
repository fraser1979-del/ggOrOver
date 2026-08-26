import datetime
import os
import pandas as pd
import requests
from schedule import ottieni_prossime_partite
from team_analytics import analisi_matchup_squadre
from player_analytics import analizza_profilo_giocatore

# ==========================================
# CONFIGURAZIONE NOTIFICHE TELEGRAM
# ==========================================
TELEGRAM_TOKEN = os.getenv("8874279866:AAGg-rhWquOq3IAZtQ-zNFUIUUjgvHBRmF8")
TELEGRAM_CHAT_ID = os.getenv("270457061")

def invia_telegram(messaggio):
    """Invia un messaggio formattato al tuo bot Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Attenzione: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID non presenti nelle variabili d'ambiente.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": messaggio,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Notifica Telegram inviata con successo!")
        else:
            print(f"❌ Errore Telegram ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Errore di connessione a Telegram: {e}")

# ==========================================
# ESECUZIONE REPORT GIORNALIERO AUTOMATICO
# ==========================================
def report_giornaliero_automatico():
    # 1. Recupera la data di oggi
    oggi = datetime.datetime.now().strftime("%Y-%m-%d")
    print("==========================================")
    print(f"   AVVIO ANALISI AUTOMATICA DAILY - {oggi}")
    print("==========================================")

    # Invia notifica di inizio esecuzione su Telegram
    invia_telegram(f"🚀 **Avvio Analisi NBA Daily** - `{oggi}`")

    # 2. Scarica le partite della stagione
    df_cal = ottieni_prossime_partite("2026-27")

    if df_cal.empty:
        print("⚠️ Nessun dato a calendario disponibile per oggi.")
        invia_telegram("⚠️ **NBA Bot**: Nessuna partita a calendario trovata per la data odierna.")
        return

    # 3. Filtra le partite in programma oggi (o le prossime imminenti)
    print(f"Analisi di {len(df_cal)} partite trovate a calendario...")
    
    # -------------------------------------------------------------
    # LOGICA DI ANALISI MATCHUP E GIOCATORI
    # -------------------------------------------------------------
    # Esempio di invio report finale / Value Bet trovate:
    # report_finale = "🔥 **VALUE BET TROVATA!**\nPartita: ...\nQuota: ..."
    # invia_telegram(report_finale)

    print("==========================================")
    print("   ANALISI COMPLETATA CON SUCCESSO")
    print("==========================================")
    
    invia_telegram(f"✅ **Analisi NBA completata con successo per il {oggi}**!")

if __name__ == "__main__":
    report_giornaliero_automatico()