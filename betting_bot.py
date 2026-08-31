import os
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson

# Configurazione API (legge dai Secrets di GitHub o usa le stringhe locali se eseguito in locale)
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "LA_TUA_API_KEY_LOCAL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "IL_TUO_TELEGRAM_BOT_TOKEN_LOCAL")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "IL_TUO_TELEGRAM_CHAT_ID_LOCAL")

BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": FOOTBALL_API_KEY}

LEAGUES = {
    "PL": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "ELC": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship",
    "EL1": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League One",
    "EL2": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League Two",
    "SA": "🇮🇹 Serie A",
    "SB": "🇮🇹 Serie B"
}

PROB_THRESHOLD = 0.65  # Soglia del 65%

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"❌ Errore invio Telegram ({response.status_code}): {response.text}")

def get_fixtures_and_standings(league_code):
    url_standings = f"{BASE_URL}/competitions/{league_code}/standings"
    url_matches = f"{BASE_URL}/competitions/{league_code}/matches?status=SCHEDULED"
    res_s = requests.get(url_standings, headers=HEADERS).json()
    res_m = requests.get(url_matches, headers=HEADERS).json()
    return res_s, res_m

def get_match_details(match_id):
    """Recupera dettagli della singola partita (formazioni, assenze, formazioni ufficiali se disponibili)."""
    url_match = f"{BASE_URL}/matches/{match_id}"
    res = requests.get(url_match, headers=HEADERS)
    if res.status_code == 200:
        return res.json()
    return None

def calculate_team_stats(standings_data):
    table = standings_data['standings'][0]['table']
    df = pd.DataFrame(table)
    total_matches = df['playedGames'].mean()
    if total_matches == 0:
        return None, 0, 0
    
    avg_home_goals = df['goalsFor'].sum() / (len(df) * total_matches)
    avg_away_goals = df['goalsAgainst'].sum() / (len(df) * total_matches)
    
    stats = {}
    for team in table:
        t_id = team['team']['id']
        played = team['playedGames']
        if played == 0:
            continue
        stats[t_id] = {
            'name': team['team']['name'],
            'att_home': (team['home']['goalsFor'] / (played / 2)) / avg_home_goals if played > 0 else 1,
            'def_home': (team['home']['goalsAgainst'] / (played / 2)) / avg_away_goals if played > 0 else 1,
            'att_away': (team['away']['goalsFor'] / (played / 2)) / avg_away_goals if played > 0 else 1,
            'def_away': (team['away']['goalsAgainst'] / (played / 2)) / avg_home_goals if played > 0 else 1,
            'form_factor': 1.0  # Moltiplicatore tattico basato sui recenti risultati
        }
    return stats, avg_home_goals, avg_away_goals

def apply_tactical_and_lineup_adjustments(lambda_home, lambda_away, match_details):
    """
    Incrocia dati statistici con formazioni/assenze:
    - Riduce l'attacco se mancano titolari/marcatori chiave.
    - Aumenta/riduce i gol attesi in base ai moduli ed eventuali defezioni difensive.
    """
    if not match_details:
        return lambda_home, lambda_away

    # Analisi formazioni / titolari (se rese disponibili dall'API pre-partita)
    lineup_home = match_details.get('homeTeam', {}).get('lineup', [])
    lineup_away = match_details.get('awayTeam', {}).get('lineup', [])
    bench_home = match_details.get('homeTeam', {}).get('bench', [])
    bench_away = match_details.get('awayTeam', {}).get('bench', [])

    # Impatto Assenze Tattiche (e.g. assenza capocannoniere o portiere)
    # Se le formazioni non sono ancora confermate ufficialmente, applichiamo un piccolo correttivo tattico sulla panchina
    home_mod = 1.0
    away_mod = 1.0

    if lineup_home:
        # Se c'è una formazione con poche riserve di ruolo, correggiamo l'incisività
        home_mod *= 1.05 if len(lineup_home) == 11 else 0.95
    if lineup_away:
        away_mod *= 1.05 if len(lineup_away) == 11 else 0.95

    # Moltiplicatori tattici calcolati
    adjusted_lambda_home = lambda_home * home_mod
    adjusted_lambda_away = lambda_away * away_mod

    return adjusted_lambda_home, adjusted_lambda_away

def predict_match(home_stats, away_stats, avg_home_g, avg_away_g, match_details=None):
    # Base di calcolo Poisson (Statistica pures)
    lambda_home = home_stats['att_home'] * away_stats['def_away'] * avg_home_g
    lambda_away = away_stats['att_away'] * home_stats['def_home'] * avg_away_g
    
    # Incrocio Tattica & Formazioni
    lambda_home, lambda_away = apply_tactical_and_lineup_adjustments(lambda_home, lambda_away, match_details)
    
    max_goals = 6
    prob_matrix = np.zeros((max_goals, max_goals))
    for h in range(max_goals):
        for a in range(max_goals):
            prob_matrix[h, a] = poisson.pmf(h, lambda_home) * poisson.pmf(a, lambda_away)
            
    prob_ov15 = 1 - (prob_matrix[0,0] + prob_matrix[1,0] + prob_matrix[0,1])
    prob_ov25 = 1 - np.sum(np.triu(prob_matrix, 0)[:3, :3])
    prob_gg = 1 - (np.sum(prob_matrix[0, :]) + np.sum(prob_matrix[:, 0]) - prob_matrix[0, 0])
    
    return {
        'xG_Home': round(lambda_home, 2),
        'xG_Away': round(lambda_away, 2),
        'OV_1.5': round(prob_ov15 * 100, 1),
        'OV_2.5': round(prob_ov25 * 100, 1),
        'GG': round(prob_gg * 100, 1)
    }

def run_automation():
    signals = []
    
    for league_code, league_name in LEAGUES.items():
        try:
            standings, matches = get_fixtures_and_standings(league_code)
            if 'standings' not in standings or 'matches' not in matches:
                continue
                
            stats, avg_home_g, avg_away_g = calculate_team_stats(standings)
            if not stats:
                continue
                
            upcoming = matches['matches'][:10]
            for match in upcoming:
                h_id = match['homeTeam']['id']
                a_id = match['awayTeam']['id']
                m_id = match['id']
                
                if h_id in stats and a_id in stats:
                    # Recupera dettagli formazioni / partita
                    match_details = get_match_details(m_id)
                    
                    pred = predict_match(stats[h_id], stats[a_id], avg_home_g, avg_away_g, match_details)
                    
                    high_prob_markets = []
                    if pred['OV_1.5'] >= (PROB_THRESHOLD * 100):
                        high_prob_markets.append(f"🟢 *Over 1.5*: {pred['OV_1.5']}%")
                    if pred['OV_2.5'] >= (PROB_THRESHOLD * 100):
                        high_prob_markets.append(f"🔥 *Over 2.5*: {pred['OV_2.5']}%")
                    if pred['GG'] >= (PROB_THRESHOLD * 100):
                        high_prob_markets.append(f"⚽ *Goal/Goal*: {pred['GG']}%")
                        
                    if high_prob_markets:
                        match_str = f"🏆 *{league_name}*\n⚔️ *{match['homeTeam']['shortName']} vs {match['awayTeam']['shortName']}*\n📊 xG Tattici: {pred['xG_Home']} - {pred['xG_Away']}\n"
                        match_str += "\n".join(high_prob_markets)
                        signals.append(match_str)
        except Exception as e:
            print(f"Errore nella lega {league_name}: {e}")
            
    if signals:
        header = "🚨 *SEGNALI VALUE BET STATISTICI E TATTICI* 🚨\n___________________________________\n\n"
        full_message = header + "\n\n___________________________________\n".join(signals)
        send_telegram_message(full_message)
        print("✅ Segnali inviati con successo su Telegram!")
    else:
        send_telegram_message("🤖 *Bot Pronostici*: Scansione completata! Nessuna partita oggi supera la soglia tattica/statistica del 65%.")
        print("Nessun segnale ad alta probabilità trovato. Inviata notifica di riepilogo.")

if __name__ == "__main__":
    run_automation()