import time
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats

def ottieni_rating_squadre(season: str = "2025-26") -> pd.DataFrame:
    """Scarica le metriche avanzate di tutte le squadre NBA (Pace, ORtg, DRtg, NetRtg)."""
    print("--> Scaricamento statistiche avanzate delle squadre...")
    time.sleep(0.6)
    
    # Parametro aggiornato: measure_type_detailed_defense="Advanced"
    stats = leaguedashteamstats.LeagueDashTeamStats(
        measure_type_detailed_defense="Advanced",
        season=season
    )
    df = stats.get_data_frames()[0]
    
    colonne = ['TEAM_NAME', 'GP', 'OFF_RATING', 'DEF_RATING', 'NET_RATING', 'PACE', 'TS_PCT']
    df_clean = df[colonne].sort_values(by='NET_RATING', ascending=False)
    return df_clean

def analisi_matchup_squadre(squadra_casa: str, squadra_trasferta: str, season: str = "2025-26"):
    """Mette a confronto i parametri chiave di due squadre."""
    df_teams = ottieni_rating_squadre(season=season)
    
    home = df_teams[df_teams['TEAM_NAME'].str.contains(squadra_casa, case=False, na=False)]
    away = df_teams[df_teams['TEAM_NAME'].str.contains(squadra_trasferta, case=False, na=False)]
    
    if home.empty or away.empty:
        print("❌ Una o entrambe le squadre non sono state trovate.")
        return None

    matchup_df = pd.concat([home, away], ignore_index=True)
    
    print("\n==================================================")
    print(f"   ANALISI MATCHUP SQUADRE: {squadra_casa.upper()} VS {squadra_trasferta.upper()}")
    print("==================================================")
    print(matchup_df.to_string(index=False))
    
    return matchup_df