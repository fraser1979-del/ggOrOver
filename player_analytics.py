import time
import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog

def analizza_profilo_giocatore(nome_giocatore: str, ultime_n: int = 10, season: str = "2025-26"):
    """Scarica e analizza il rendimento recente di un giocatore con metriche avanzate."""
    risultati = players.find_players_by_full_name(nome_giocatore)
    if not risultati:
        print(f"❌ Giocatore '{nome_giocatore}' non trovato.")
        return None
    
    player_id = risultati[0]['id']
    time.sleep(0.6)
    
    gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season)
    df = gamelog.get_data_frames()[0]
    
    if df.empty:
        print(f"Nessun dato disponibile per {nome_giocatore}.")
        return None

    # Calcolo metriche avanzate
    ts_denom = 2 * (df['FGA'] + 0.44 * df['FTA'])
    df['TS%'] = (df['PTS'] / ts_denom * 100).fillna(0).round(1)
    
    efg_denom = df['FGA']
    df['eFG%'] = ((df['FGM'] + 0.5 * df['FG3M']) / efg_denom * 100).fillna(0).round(1)

    recenti = df.head(ultime_n)

    sintesi = {
        "Giocatore": nome_giocatore,
        "Gare Considerate": len(recenti),
        "Media Punti": round(recenti['PTS'].mean(), 1),
        "Media Rimbalzi": round(recenti['REB'].mean(), 1),
        "Media Assist": round(recenti['AST'].mean(), 1),
        "True Shooting (TS%)": round(recenti['TS%'].mean(), 1),
        "Effective FG (eFG%)": round(recenti['eFG%'].mean(), 1),
        "Minuti Medi": round(recenti['MIN'].astype(float).mean(), 1)
    }

    return sintesi, recenti