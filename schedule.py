import time
import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder

def ottieni_prossime_partite(season: str = "2026-27") -> pd.DataFrame:
    """
    Scarica il calendario e le partite in programma per la stagione selezionata.
    """
    print(f"--> Scaricamento calendario partite per la stagione {season}...")
    time.sleep(0.6)
    
    # Richiesta calendario ufficiale
    finder = leaguegamefinder.LeagueGameFinder(season_nullable=season)
    games = finder.get_data_frames()[0]
    
    if games.empty:
        print("⚠️ Calendario non ancora disponibile o dati in fase di aggiornamento.")
        return pd.DataFrame()
        
    # Ordina per data partita
    games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
    games = games.sort_values(by='GAME_DATE', ascending=True)
    
    # Selezione colonne chiave
    colonne = ['GAME_DATE', 'MATCHUP', 'GAME_ID', 'PTS']
    df_clean = games[colonne].drop_duplicates(subset=['GAME_ID'])
    
    return df_clean

if __name__ == "__main__":
    df_sched = ottieni_prossime_partite(season="2026-27")
    if not df_sched.empty:
        print("\n=== PRIME PARTITE IN PROGRAMMA ===")
        print(df_sched.head(15).to_string(index=False))