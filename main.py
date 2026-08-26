# Importiamo le funzioni create nei moduli precedenti
from schedule import ottieni_prossime_partite
from team_analytics import analisi_matchup_squadre
from player_analytics import analizza_profilo_giocatore

def menu_principale():
    """Mostra un menu a scelta multipla nel terminale di VS Code."""
    print("\n==========================================")
    print("      SISTEMA ANALITICO NBA 2026/27")
    print("==========================================")
    print("1. Visualizza partite a calendario")
    print("2. Analizza un matchup tra due squadre")
    print("3. Analizza profilo singolo giocatore")
    print("4. Esci")
    
    # input() ferma l'esecuzione e attende che tu scriva un numero nel terminale
    scelta = input("\nSeleziona un'opzione (1-4): ").strip()
    
    if scelta == "1":
        # Richiama il modulo schedule.py per scaricare le partite
        df_cal = ottieni_prossime_partite("2026-27")
        if not df_cal.empty:
            print("\nProssimi incontri trovati:")
            print(df_cal.head(20).to_string(index=False))
            
    elif scelta == "2":
        # Chiede i nomi delle due squadre da mettere a confronto
        sq1 = input("Inserisci prima squadra (es. Celtics): ").strip()
        sq2 = input("Inserisci seconda squadra (es. Mavericks): ").strip()
        analisi_matchup_squadre(sq1, sq2)
        
    elif scelta == "3":
        # Chiede il nome del giocatore da analizzare
        giocatore = input("Nome del giocatore (es. Luka Doncic): ").strip()
        sintesi, recenti = analizza_profilo_giocatore(giocatore, ultime_n=5)
        if sintesi:
            print("\n=== SINTESI RENDIMENTO ===")
            for chiave, valore in sintesi.items():
                print(f"{chiave}: {valore}")
                
    elif scelta == "4":
        print("Uscita dal programma.")
        return
    else:
        print("Opzione non valida. Riprova.")

if __name__ == "__main__":
    # Avvia la funzione del menu all'esecuzione del file
    menu_principale()