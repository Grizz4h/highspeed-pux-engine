# Highspeed Liga Generator

Ein umfassender Eishockey-Liga-Simulator für die fiktive "Highspeed Liga". Simuliert komplette Saisons, Spieltage, Playoffs und generiert detaillierte Stats, Replays und Lineups.

## Übersicht

Dieser Generator simuliert eine Eishockey-Liga mit zwei Conferences (Nord und Süd), 14 Teams und realistischen Spieler-Ratings. Er basiert auf historischen DEL-Daten, aber mit fiktiven Team-Namen und angepassten Ratings. Der Fokus liegt auf narrativen Elementen, detaillierten Replays und kumulierten Statistiken.

### Hauptfeatures
- **Vollständige Saison-Simulation**: Regular Season (26 Spieltage) + Playoffs (Best-of-7).
- **Dynamische Lineups**: Gewichtete Auswahl basierend auf Overall-Rating mit Jitter für Rotation.
- **Spieler-Stats**: Kumulative GP, Goals, Assists, Points – korrekt aus Lineups abgeleitet.
- **Replays & Narrative**: Detaillierte Spielberichte, Starting Six, Erzählungen.
- **Web-Integration**: Exportiert Daten für eine Web-App (unter `stats/public/`).

## Installation & Setup

### Voraussetzungen
- Python 3.8+
- Abhängigkeiten: `pip install -r requirements.txt`
- Daten-Verzeichnis: Standardmäßig `/opt/highspeed/data` (via `HIGHSPEED_DATA_ROOT`)

### Erste Ausführung
1. Klone/Setup das Repo.
2. Stelle sicher, dass `data/` existiert mit Basis-Daten (siehe `data/all_players_baseline.json`).
3. Führe `python LigageneratorV2.py` aus – es generiert automatisch Schedules und startet die Simulation.

### Datenstruktur
- **Basis-Daten**: `data/all_players_baseline.json` (DEL-Spieler mit Ratings).
- **Generierte Daten**: Teams, Ratings, Schedules werden bei Bedarf erstellt.
- **Saison-Daten**: In `data/saison_01/` (Stats, Replays, etc.).

## Verwendung

### Simulation starten
```bash
python LigageneratorV2.py
```
- Simuliert einen Spieltag nach dem anderen.
- Speichert automatisch Fortschritt in `data/saves/savegame.json`.
- Bei Fehlern: Check Logs in `logs/liga_simulation.log`.

### Modi
- **Regular Season**: Läuft automatisch bis Spieltag 26.
- **Playoffs**: Startet nach Regular Season automatisch.
- **Manuell**: Bearbeite `spieltag` in `LigageneratorV2.py` für spezifische Spieltage.

### Ausgaben
- Minimal: Nur kritische Warnungen/Fehler + spezielle NDP-Debug-Ausgaben.
- Replays: In `data/replays/saison_01/spieltag_XX/`.
- Stats: Kumuliert in `stats/public/data/saison_01/league/`.

## Architektur & Funktionsweise

### 1. Datenfluss
1. **Laden/Bauen**: Teams, Spieler-Ratings, Schedule.
2. **Lineup-Generierung**: Pro Spieltag, gewichtet nach Overall-Rating (Jitter=1.0 für Rotation).
3. **Simulation**: `simulate_match()` berechnet Ergebnisse basierend auf Team-Stärken (Summe Player-Overall).
4. **Stats-Aggregation**: Goals/Assists aus Replays → kumulative Player-Stats.
5. **Export**: JSON für Web-App, Replays, Narratives.

### 2. Team- & Spieler-Management
- **Teams**: 14 fiktive Teams, basierend auf DEL-Realitäten (z.B. Novadelta Panther = ERC Ingolstadt).
- **Spieler**: ~25 pro Team, mit Ratings (Offense, Defense, Speed, Chemistry, Overall).
- **Ratings-Berechnung**: Aus historischen DEL-Stats (Goals, Assists, +/-) normiert zu 0-100.
- **Lineups**: 6 Feldspieler + 2 Goalies, gewichtet nach Overall (niedriger Jitter fördert Rotation).

### 3. Simulation-Details
- **Stärke-Berechnung**: `calc_strength()` summiert Top-Player-Overall (Home-Bonus +5).
- **Ergebnis**: Gauss-Verteilung basierend auf Stärke-Differenz (Std variiert mit Ausgeglichenheit).
- **OT/SO**: Bei Unentschieden, zufällig verlängert.
- **GP**: Nur für Spieler in Lineups (dressed) – verhindert "Geister-Torschützen".

### 4. Stats & Exports
- **Player-Stats**: Delta-basiert (aktuelle Goals - vorherige) → kumuliert.
- **GP**: Streng aus Lineups (1 pro Spieltag für dressed Spieler).
- **Exports**: Automatisch nach jedem Spieltag (Snapshots, Latest).

### 5. Narrative & Starting Six
- **Starting Six**: Top-6 Scorer + Goalie pro Conference.
- **Narrative**: KI-generierte Erzählungen pro Spiel (via externe API?).
- **Replays**: Vollständige Spielberichte mit Events.

## Eigenheiten & Wichtige Hinweise

### Bekannte Bugs/Edge-Cases
- **GP-Berechnung**: Spieler ohne Lineup-Eintrag bekommen keine GP – selbst bei Goals/Assists (verhindert Inkonsistenzen).
- **Rotation**: Overall-Gewichtung mit hohem Jitter (1.0) statt GP, um Low-GP-Spieler spielen zu lassen.
- **Ingolstadt/Panther**: Schwache Ratings (basierend auf realer DEL-Schwäche) – oft Letzter.
- **Logging**: Auf WARNING-Level, um Output minimal zu halten (Details in `logs/`).

### Performance
- Simulation: ~1-2 Sek pro Spieltag.
- Speicher: JSON-basiert, skalierbar für Saisons.

### Customization
- **Ratings anpassen**: Bearbeite `data/players_rated.json` (z.B. booste Panther-Overall).
- **Schedules**: In `data/schedules/saison_01/schedule.json`.
- **Lineup-Logic**: In `_weighted_pick_by_overall()` (Jitter, Gewichtung).
- **Narrative**: Deaktivierbar in `LigageneratorV2.py`.

### Troubleshooting
- **Fehler beim Laden**: Check `data/`-Struktur und `HIGHSPEED_DATA_ROOT`.
- **Keine Stats**: Stelle sicher, dass Lineups generiert werden (vor Stats-Export).
- **Panther immer Letzter**: Ratings-Problem – booste manuell.
- **Output zu viel/wenig**: Logging-Level anpassen oder Prints (de)aktivieren.
- **Playoffs starten nicht**: Regular Season muss komplett sein (26 Spieltage).

### Entwicklung
- **Code-Struktur**: Modular (Simulation, Stats, Exports).
- **Tests**: `test_*.py` für Units.
- **Logging**: Detailliert in `logs/`, aber Konsole minimal.
- **API-Integration**: Für Narratives (falls externe KI verwendet).

## Dateien & Ordner

```
data/
├── saison_01/              # Saison-spezifische Daten
│   ├── df_stats_spieltag_XX.json    # Player-Stats pro Spieltag
│   └── stats_dataframe_debug_*.json # Debug-Snapshots
├── all_players_baseline.json        # Basis-Spieler (DEL)
├── players_rated.json               # Berechnete Ratings
├── team_mapping.json                # Team-Mappings (Real → Fiktiv)
└── schedules/saison_01/schedule.json # Spielplan

stats/public/data/saison_01/league/  # Web-Exports
├── players.json                     # Spieler-Liste
├── player_stats_after_spieltag_XX.json # Kumulierte Stats
└── latest.json                      # Aktuelle Stats

logs/                               # Logs
├── liga_simulation.log             # Sim-Details
└── rating_calculation.log          # Rating-Berechnung

LigageneratorV2.py                  # Haupt-Script
player_stats_export.py              # Stats-Logic
build_ratings.py                    # Rating-Berechnung
```

## Fazit

Der Generator ist robust für narrative Eishockey-Simulationen, aber erfordert saubere Daten und gelegentliche manuelle Anpassungen (z.B. Ratings). Bei Fragen: Check Logs oder bearbeite vorsichtig – der Code ist komplex, aber modular.

Viel Spaß beim Simulieren! 🏒