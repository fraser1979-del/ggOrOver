import os
import requests
import numpy as np
from scipy.stats import poisson

# Configurazione API (recupera le variabili d'ambiente se impostate, altrimenti usa i valori di default)
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "INSERISCI_QUI_LA_TUA_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "INSERISCI_QUI_IL_TUO_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "INSERISCI_QUI_IL_TUO_CHAT_ID")

BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": FOOTBALL_API_KEY}

# Leghe principali supportate dal piano FREE di Football-Data.org
LEAGUES = {
    "PL": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "SA": "🇮🇹 Serie A",
    "PD": "🇪🇸 La Liga",
    "FL1": "🇫🇷 Ligue 1",
    "BL1": "🇩🇪 Bundesliga"
}

# Soglie di probabilità per generare i segnali
THRESHOLDS = {
    'OV_1.5': 0.65,
    'OV_2.5': 0.50,
    'GG':     0.50
}

def send_telegram_message(message):
    """Invia un messaggio Telegram senza formattazione speciale per evitare errori di parsing."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"❌ Errore invio Telegram ({response.status_code}): {response.text}")

def get_fixtures_and_standings(league_code):
    """Recupera la classifica e le partite programmate per la lega specificata."""
    url_standings = f"{BASE_URL}/competitions/{league_code}/standings"
    url_matches = f"{BASE_URL}/competitions/{league_code}/matches?status=SCHEDULED"
    res_s = requests.get(url_standings, headers=HEADERS).json()
    res_m = requests.get(url_matches, headers=HEADERS).json()
    return res_s, res_m

def parse_form_factor(form_string):
    """Calcola un moltiplicatore di forma basato sugli ultimi 5 risultati."""
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
    """Estrae le metriche di attacco/difesa per ciascuna squadra."""
    if 'standings' not in standings_data or not standings_data['standings']:
        return None, 0, 0
        
    table = standings_data['standings'][0]['table']
    
    total_goals = sum(t.get('goalsFor', 0) for t in table)
    total_matches = sum(t.get('playedGames', 0) for t in table)
    
    if total_matches == 0:
        return None, 0, 0
    
    avg_goals_per_team = total_goals / total_matches
    
    stats = {}
    for team in table:
        t_id = team['team']['id']
        played = team.get('playedGames', 0)
        
        if played == 0:
            continue
            
        form_multiplier = parse_form_factor(team.get('form', ''))
        
        h_data = team.get('home', {})
        a_data = team.get('away', {})
        
        h_played = h_data.get('playedGames', played / 2) if h_data.get('playedGames', 0) > 0 else (played / 2)
        a_played = a_data.get('playedGames', played / 2) if a_data.get('playedGames', 0) > 0 else (played / 2)
        
        goals_for_h = h_data.get('goalsFor', team.get('goalsFor', 0) / 2)
        goals_against_h = h_data.get('goalsAgainst', team.get('goalsAgainst', 0) / 2)
        goals_for_a = a_data.get('goalsFor', team.get('goalsFor', 0) / 2)
        goals_against_a = a_data.get('goalsAgainst', team.get('goalsAgainst', 0) / 2)
        
        stats[t_id] = {
            'name': team['team']['name'],
            'att_home': ((goals_for_h / max(h_played, 1)) / avg_goals_per_team) * form_multiplier,
            'def_home': ((goals_against_h / max(h_played, 1)) / avg_goals_per_team) / form_multiplier,
            'att_away': ((goals_for_a / max(a_played, 1)) / avg_goals_per_team) * form_multiplier,
            'def_away': ((goals_against_a / max(a_played, 1)) / avg_goals_per_team) / form_multiplier
        }
    return stats, avg_goals_per_team, avg_goals_per_team

def dixon_coles_adjustment(h, a, l_home, l_away, rho=-0.13):
    """Applicazione correzione Dixon-Coles per punteggi bassi (0-0, 1-0, 0-1, 1-1)."""
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
    """Calcola la matrice di probabilità di Poisson con correzione Dixon-Coles."""
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
    
    prob_under15 = prob_matrix[0,0] + prob_matrix[1,0] + prob_matrix[0,1]
    prob_ov15 = 1 - prob_under15
    
    prob_under25 = np.sum([prob_matrix[h, a] for h in range(3) for a in range(3) if h + a <= 2])
    prob_ov25 = 1 - prob_under25
    
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
    total_matches_checked = 0
    
    for league_code, league_name in LEAGUES.items():
        try:
            standings, matches = get_fixtures_and_standings(league_code)
            if 'standings' not in standings or 'matches' not in matches:
                continue
                
            stats, avg_home_g, avg_away_g = calculate_team_stats(standings)
            if not stats:
                continue
                
            upcoming = matches.get('matches', [])[:15]
            
            for match in upcoming:
                h_id = match['homeTeam']['id']
                a_id = match['awayTeam']['id']
                
                if h_id in stats and a_id in stats:
                    total_matches_checked += 1
                    pred = predict_match(stats[h_id], stats[a_id], avg_home_g, avg_away_g)
                    
                    high_prob_markets = []
                    if pred['OV_1.5'] >= (THRESHOLDS['OV_1.5'] * 100):
                        high_prob_markets.append(f"Over 1.5: {pred['OV_1.5']}%")
                    if pred['OV_2.5'] >= (THRESHOLDS['OV_2.5'] * 100):
                        high_prob_markets.append(f"Over 2.5: {pred['OV_2.5']}%")
                    if pred['GG'] >= (THRESHOLDS['GG'] * 100):
                        high_prob_markets.append(f"Goal/Goal: {pred['GG']}%")
                        
                    if high_prob_markets:
                        match_str = (
                            f"🏆 {league_name}\n"
                            f"⚔️ {match['homeTeam']['name']} vs {match['awayTeam']['name']}\n"
                            f"📊 xG: {pred['xG_Home']} - {pred['xG_Away']}\n"
                            + "\n".join([f"  • {m}" for m in high_prob_markets])
                        )
                        signals.append(match_str)
        except Exception as e:
            print(f"❌ Errore nella lega {league_name}: {e}")
            
    print(f"\n📊 Scansione completata. Partite analizzate con successo: {total_matches_checked}")
    
    if signals:
        send_telegram_message(f"🚨 VALUE BET STATISTICHE TROVATE: {len(signals)} 🚨")
        
        for msg in signals:
            send_telegram_message(msg)
            
        print(f"✅ {len(signals)} notifiche inviate con successo su Telegram!")
    else:
        send_telegram_message(f"🤖 Bot Pronostici: Scansione di {total_matches_checked} partite completata. Nessun segnale sopra le soglie.")
        print("Nessun segnale ad alta probabilità trovato.")

if __name__ == "__main__":
    run_automation()