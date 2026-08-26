import datetime
import os
import pandas as pd
from schedule import ottieni_prossime_partite
from team_analytics import analisi_matchup_squadre
from player_analytics import analizza_profilo_giocatore

def report_giornaliero_automatico():
    # 1. Recupera la data di oggi
    oggi = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"==================================================")
    print(f"   AVVIO ANALISI AUTOMATICA DAILY - {oggi}")
    print(f"==================================================")

    # 2. Scarica le partite della stagione
    df_cal = ottieni_prossime_partite("2026-27")
    
    if df_cal.empty:
        print("⚠️ Nessun dato a calendario disponibile per oggi.")
        return

    # 3. Filtra le partite in programma oggi (o le prossime imminenti)
    df_cal['GAME_DATE_STR'] = pd.to_datetime(df_cal['GAME_DATE']).dt.strftime("%Y-%m-%d")
    partite_oggi = df_cal[df_cal['GAME_DATE_STR'] == oggi]

    # Se oggi non ci sono gare (es. giorno di riposo), prende le prime 3 a calendario
    if partite_oggi.empty:
        print(f"Nessuna partita programmata esattamente per oggi ({oggi}). Recupero i primi incontri a calendario...")
        partite_target = df_cal.head(5)
    else:
        partite_target = partite_oggi

    # 4. Cartella di output per i report
    os.makedirs("Report_Giornalieri", exist_ok=True)
    nome_excel = os.path.join("Report_Giornalieri", f"NBA_Daily_Report_{oggi}.xlsx")

    # 5. Genera analisi per ciascun matchup
    risultati_matchup = []
    
    for _, match in partite_target.iterrows():
        matchup_str = match['MATCHUP']  # es. "BOS vs. MIA" o "LAL @ GS"
        print(f"\n[+] Elaborazione Matchup: {matchup_str}")
        
        # Estrai le abbreviazioni dei team
        teams = matchup_str.replace("@", "vs.").split(" vs. ")
        if len(teams) == 2:
            team_a, team_b = teams[0].strip(), teams[1].strip()
            df_matchup = analisi_matchup_squadre(team_a, team_b)
            if df_matchup is not None:
                risultati_matchup.append(df_matchup)

    # 6. Salva l'output in Excel
    if risultati_matchup:
        df_finale = pd.concat(risultati_matchup, ignore_index=True)
        with pd.ExcelWriter(nome_excel, engine='openpyxl') as writer:
            df_finale.to_excel(writer, sheet_name="Matchup_Oggi", index=False)
        print(f"\n✅ REPORT AUTOMATICO GENERATO: {nome_excel}")
    else:
        print("\nImpossibile completare l'estrazione automatica.")

if __name__ == "__main__":
    report_giornaliero_automatico()