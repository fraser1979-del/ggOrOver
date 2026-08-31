import os
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson

# Configurazione API
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "LA_TUA_API_KEY_LOCAL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "IL_TUO_TELEGRAM_BOT_TOKEN_LOCAL")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "IL_TUO_TELEGRAM_CHAT_ID_LOCAL")

BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": FOOTBALL_API_KEY}

LEAGUES = {
    # Inghilterra
    "PL": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "ELC": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship",
    "EL1": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League One",
    "EL2": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League Two",
    # Italia
    "SA": "🇮🇹 Serie A",
    "SB": "🇮🇹 Serie B",
    # Spagna
    "PD": "🇪🇸 La Liga",
    "SD": "🇪🇸 Segunda División",
    # Francia
    "FL1": "🇫🇷 Ligue 1",
    "FL2": "🇫🇷 Ligue 2",
    # Germania
    "BL1": "🇩🇪 Bundesliga",
    "BL2": "🇩🇪 2. Bundesliga"
}

# Soglie di probabilità calibrate per mercato
THRESHOLDS = {
    'OV_1.5': 0.70,  # 70% per Over 1.5 (evento ad alta frequenza)
    'OV_2.5': 0.55,  # 55% per Over 2.5 (ottima soglia statistica)
    'GG':     0.55   # 55% per Goal/Goal
}

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

def parse_form_factor(form_string):
    """
    Calcola un moltiplicatore di forma recente (ultime 5 gare).
    W = 3, D = 1, L = 0. Media ponderata normalizzata.
    """
    if not form_string:
        return 1.0
    
    results = form_string.split(',')[-5:]
    if not results:
        return 1.0
    
    points = 0
    weights = [0.1, 0.15, 0.2, 0.25, 0.3]
    active_weights = weights[-len(results):]
    
    for res, w in zip(results, active_weights):
        if 'W' in res:
            points += 3 * w
        elif 'D' in res:
            points += 1 * w
            
    return 0.85 + (points / 3.0) * 0.30

def calculate_team_stats(standings_data):
    table = standings_data['standings'][0]['table']
    
    total_home_goals = sum(t['home']['goalsFor'] for t in table)
    total_away_goals = sum(t['away']['goalsFor'] for t in table)
    total_home_matches = sum(t['home']['playedGames'] for t in table)
    total_away_matches = sum(t['away']['playedGames'] for t in table)
    
    if total_home_matches == 0 or total_away_matches == 0:
        return None, 0, 0
    
    avg_home_goals = total_home_goals / total_home_matches
    avg_away_goals = total_away_goals / total_away_matches
    
    stats = {}
    for team in table:
        t_id = team['team']['id']
        h_played = team['home']['playedGames']
        a_played = team['away']['playedGames']
        
        if h_played == 0 or a_played == 0:
            continue
            
        form_multiplier = parse_form_factor(team.get('form', ''))
        
        stats[t_id] = {
            'name': team['team']['name'],
            'att_home': ((team['home']['goalsFor'] / h_played) / avg_home_goals) * form_multiplier,
            'def_home': ((team['home']['goalsAgainst'] / h_played) / avg_away_goals) / form_multiplier,
            'att_away': ((team['away']['goalsFor'] / a_played) / avg_away_goals) * form_multiplier,
            'def_away': ((team['away']['goalsAgainst'] / a_played) / avg_home_goals) / form_multiplier
        }
    return stats, avg_home_goals, avg_away_goals

def dixon_coles_adjustment(h, a, l_home, l_away, rho=-0.13):
    """
    Applica il fattore di correzione di Dixon-Coles per bilanciare 
    la sottostima dei pareggi e dei punteggi bassi (0-0, 1-0, 0-1, 1-1).
    """
    if h == 0 and a == 0:
        return 1 - (l_home * l_away * rho)
    elif h == 0 and a == 1:
        return 1 + (l_home * rho)
    elif h == 1 and a == 0:
        return 1 + (l_away * rho)
    elif h == 1 and a == 1:
        return 1 - rho
    return 1.0

def predict_match(home_stats, away_stats, avg_home_g, avg_away_g):
    lambda_home = home_stats['att_home'] * away_stats['def_away'] * avg_home_g
    lambda_away = away_stats['att_away'] * home_stats['def_home'] * avg_away_g
    
    max_goals = 7
    prob_matrix = np.zeros((max_goals, max_goals))
    
    for h in range(max_goals):
        for a in range(max_goals):
            p_raw = poisson.pmf(h, lambda_home) * poisson.pmf(a, lambda_away)
            adj = dixon_coles_adjustment(h, a, lambda_home, lambda_away)
            prob_matrix[h, a] = p_raw * adj
            
    prob_matrix /= np.sum(prob_matrix)
    
    # Over 1.5
    prob_under15 = prob_matrix[0,0] + prob_matrix[1,0] + prob_matrix[0,1]
    prob_ov15 = 1 - prob_under15
    
    # Over 2.5
    prob_under25 = np.sum([prob_matrix[h, a] for h in range(3) for a in range(3) if h + a <= 2])
    prob_ov25 = 1 - prob_under25
    
    # Goal/Goal
    prob_gg = np.sum(prob_matrix[1:, 1:])
    
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
                
            # Analizziamo le prossime 15 partite in programma per non limitare la scansione
            upcoming = matches['matches'][:15]
            for match in upcoming:
                h_id = match['homeTeam']['id']
                a_id = match['awayTeam']['id']
                
                if h_id in stats and a_id in stats:
                    pred = predict_match(stats[h_id], stats[a_id], avg_home_g, avg_away_g)
                    
                    high_prob_markets = []
                    if pred['OV_1.5'] >= (THRESHOLDS['OV_1.5'] * 100):
                        high_prob_markets.append(f"🟢 *Over 1.5*: {pred['OV_1.5']}%")
                    if pred['OV_2.5'] >= (THRESHOLDS['OV_2.5'] * 100):
                        high_prob_markets.append(f"🔥 *Over 2.5*: {pred['OV_2.5']}%")
                    if pred['GG'] >= (THRESHOLDS['GG'] * 100):
                        high_prob_markets.append(f"⚽ *Goal/Goal*: {pred['GG']}%")
                        
                    if high_prob_markets:
                        match_str = (
                            f"🏆 *{league_name}*\n"
                            f"⚔️ *{match['homeTeam']['shortName']} vs {match['awayTeam']['shortName']}*\n"
                            f"📊 xG: {pred['xG_Home']} - {pred['xG_Away']}\n"
                        ) + "\n".join(high_prob_markets)
                        signals.append(match_str)
        except Exception as e:
            print(f"Errore nella lega {league_name}: {e}")
            
    if signals:
        header = "🚨 *SEGNALI VALUE BET STATISTICI* 🚨\n___________________________________\n\n"
        full_message = header + "\n\n___________________________________\n".join(signals)
        send_telegram_message(full_message)
        print("✅ Segnali inviati con successo su Telegram!")
    else:
        send_telegram_message("🤖 *Bot Pronostici*: Scansione completata! Nessuna partita supera le soglie attuali.")
        print("Nessun segnale ad alta probabilità trovato.")

if __name__ == "__main__":
    run_automation()