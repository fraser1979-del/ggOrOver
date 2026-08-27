import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# Legge i token dalle variabili d'ambiente (locali o GitHub Actions)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "IL_TUO_BOT_TOKEN_LOCALE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "IL_TUO_CHAT_ID_LOCALE")

def send_telegram_message(message):
    """Invia un messaggio di testo formattato a Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Errore nell'invio del messaggio Telegram: {e}")

def scrape_citta_della_spezia():
    """Effettua lo scraping della sezione sagre/eventi di Città della Spezia."""
    url = "https://www.cittadellaspezia.com/tag/sagre/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, lname, Chrome/120.0.0.0 Safari/537.36)"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Errore nel recupero della pagina: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    found_events = []
    
    # Selezione degli articoli contenenti notizie su sagre ed eventi
    articles = soup.find_all("article")
    
    for article in articles:
        title_tag = article.find("h2") or article.find("h3")
        link_tag = article.find("a")
        
        if title_tag and link_tag:
            title = title_tag.text.strip()
            link = link_tag.get("href", "")
            
            # Filtro parole chiave HORECA / Sagre
            keywords = ["sagra", "festa", "fiera", "gastronomia", "degustazione", "cantina", "pro loco"]
            if any(keyword in title.lower() for keyword in keywords):
                found_events.append({
                    "titolo": title,
                    "link": link,
                    "data_rilevamento": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                
    return found_events

def run():
    print("Avvio ricerca sagre ed eventi Provincia di La Spezia...")
    events = scrape_citta_della_spezia()
    
    if not events:
        print("Nessun nuovo evento trovato.")
        return

    # Gestione storico per evitare di rinviare lo stesso evento più volte
    history_file = "eventi_registrati.csv"
    if os.path.exists(history_file):
        df_old = pd.read_csv(history_file)
        known_links = set(df_old["link"].tolist())
    else:
        known_links = set()
        df_old = pd.DataFrame()

    new_events = [e for e in events if e["link"] not in known_links]
    
    if new_events:
        print(f"Trovati {len(new_events)} nuovi eventi!")
        
        for event in new_events:
            msg = (
                f"🚨 *NUOVA SAGRA / EVENTO RILEVATO* 🚨\n\n"
                f"📌 *Titolo:* {event['titolo']}\n"
                f"🔗 *Link:* [Leggi Notizia]({event['link']})\n"
                f"📅 *Rilevato il:* {event['data_rilevamento']}\n\n"
                f"💡 *Azione HORECA:* Contattare la Pro Loco o il Comitato Organizzatore."
            )
            # Decommentare la riga sotto dopo aver impostato il Bot Token Telegram
            # send_telegram_message(msg)
            print(f"Notifica inviata per: {event['titolo']}")

        # Salva i nuovi eventi nello storico CSV
        df_new = pd.DataFrame(new_events)
        df_updated = pd.concat([df_old, df_new], ignore_index=True)
        df_updated.to_csv(history_file, index=False)
    else:
        print("Nessun aggiornamento rispetto all'ultima scansione.")

if __name__ == "__main__":
    run()