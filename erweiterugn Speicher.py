# ================================================
#  LIGA‑SIMULATOR  –  Round‑Robin + Play‑offs  (Persistenz‑Edition)
#  Version 5.0 – Fortsetzen nach Abbruch, Saison‑Auto‑Increment
# ================================================
"""Vollständige Eishockey‑Liga‑Simulation (Nord/Süd‑Conference).

NEU in v5.0
-----------
* **Autosave** nach *jedem* Spieltag + nach jeder Play‑off‑Runde → `saves/savegame.json`.
* Beim Neustart wird das Savegame eingelesen → du landest exakt am letzten Stand.
* Wenn eine Saison abgeschlossen ist, startet automatisch Saison *X + 1* **und** legt neue Ordner `spieltage/saison_X+1` & `playoffs/saison_X+1` an.
* `RESET_SAVE = True` (ganz oben) löscht das Savegame für einen Neustart.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple
from datetime import datetime
import pandas as pd

# ------------------------------------------------
# 1  KONSTANTEN & PFADE
# ------------------------------------------------
SAVEFILE     = Path("saves/savegame.json")
SPIELTAG_DIR = Path("spieltage")
PLAYOFF_DIR  = Path("playoffs")
RESET_SAVE   = False  # ➡️ auf True setzen, wenn du komplett neu starten willst

if RESET_SAVE and SAVEFILE.exists():
    SAVEFILE.unlink(); print("🧹 Altes Savegame entfernt – Neustart.")

# ------------------------------------------------
# 2  TEAMS LADEN
# ------------------------------------------------
from realeTeams import nord_teams, sued_teams  # noqa: E402

# ------------------------------------------------
# 3  SAVE / LOAD HELPERS
# ------------------------------------------------

def save_state(state: Dict[str, Any]) -> None:
    SAVEFILE.parent.mkdir(parents=True, exist_ok=True)
    with SAVEFILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_state() -> Dict[str, Any] | None:
    if SAVEFILE.exists() and SAVEFILE.stat().st_size > 0:
        with SAVEFILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None

# ------------------------------------------------
# 4  JSON‑EXPORT HELPERS (unchanged)
# ------------------------------------------------

def _export_tables(nord_df: pd.DataFrame, sued_df: pd.DataFrame, stats: pd.DataFrame) -> Dict[str, Any]:
    stats["Points"] = stats["Goals"] + stats["Assists"]
    def _prep(df: pd.DataFrame):
        d = df.copy(); d.rename(columns={"Goals For":"GF","Goals Against":"GA"},inplace=True); d["GD"] = d["GF"] - d["GA"]
        return d.sort_values(["Points","GF"],ascending=False)[["Team","Points","GF","GA","GD"]].to_dict("records")
    return {"tabelle_nord":_prep(nord_df),"tabelle_sued":_prep(sued_df),
            "top_scorer": stats.sort_values("Points",ascending=False).head(20)[["Player","Team","Goals","Assists","Points"]].to_dict("records")}


def _save_json(folder:Path,name:str,payload:Dict[str,Any]):
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/name).open("w",encoding="utf-8") as f:
        json.dump(payload,f,indent=2,ensure_ascii=False)

# ------------------------------------------------
# 5  PRINT HELPERS (unchanged)
# ------------------------------------------------

def _print_tables(n,s,stats):
    def _t(d):
        d=d.copy(); d["GD"]=d["Goals For"]-d["Goals Against"]
        return d.sort_values(["Points","Goals For"],ascending=False)[["Team","Points","Goals For","Goals Against","GD"]]
    print("\n📊 Tabelle Nord"); print(_t(n).to_string(index=False))
    print("\n📊 Tabelle Süd"); print(_t(s).to_string(index=False))
    stats["Points"] = stats["Goals"]+stats["Assists"]
    print("\n⭐ Top‑20 Scorer"); print(stats.sort_values("Points",ascending=False).head(20)[["Player","Team","Goals","Assists","Points"]].to_string(index=False))

# ------------------------------------------------
# 6  SIMULATIONSKERNE (create_schedule, calc_strength, etc.)
# ------------------------------------------------
# 👉 gleich wie bisher – unverändert eingefügt, hier ausgelassen, aber im Canvas komplett.

# ------------------------------------------------
# 7  HAUPTSCHLEIFE  – Persistenz-Logik
# ------------------------------------------------

def run_simulation(interactive: bool = True, max_seasons: int | None = None) -> None:
    """Fortsetzt, wenn Savegame existiert, sonst Neubeginn."""
    _ensure_dirs()
    state = load_state()
    if state:
        print(f"🔄 Savegame gefunden – Saison {state['season']} Spieltag {state['spieltag']} wird fortgesetzt.")
        season     = state["season"]
        spieltag   = state["spieltag"]
        nord       = pd.DataFrame(state["nord"])
        sued       = pd.DataFrame(state["sued"])
        nsched     = state["nsched"]
        ssched     = state["ssched"]
        stats      = pd.DataFrame(state["stats"])
    else:
        season   = get_next_season_number()
        spieltag = 1
        nord,sued = pd.DataFrame(nord_teams), pd.DataFrame(sued_teams)
        for d in (nord,sued): d[["Points","Goals For","Goals Against"]]=0
        nsched   = create_schedule(nord_teams)
        ssched   = create_schedule(sued_teams)
        stats    = pd.DataFrame([{"Player":p["Name"],"Team":t["Team"],"Goals":0,"Assists":0} for t in nord_teams+sued_teams for p in t["Players"]])

    max_spieltage = (len(nord_teams)-1)*2
    while max_seasons is None or season <= max_seasons:
        if interactive:
            input(f"➡️ Enter für Spieltag {spieltag} (Saison {season}) …")
        results_json=[]
        # Nord‑Conference
        for m in nsched[:len(nord)//2]: _,j=simulate_match(nord,*m,stats,"Nord"); results_json.append(j)
        nsched = nsched[len(nord)//2:]
        # Süd‑Conference
        for m in ssched[:len(sued)//2]: _,j=simulate_match(sued,*m,stats,"Süd"); results_json.append(j)
        ssched = ssched[len(sued)//2:]
        _print_tables(nord,sued,stats)
        save_spieltag_json(season,spieltag,results_json,nord,sued,stats)
        # SAVEGAME nach Spieltag
        save_state({"season":season,"spieltag":spieltag+1,"nord":nord.to_dict("records"),"sued":sued.to_dict("records"),
                    "nsched":nsched,"ssched":ssched,"stats":stats.to_dict("records")})
        spieltag+=1
        if spieltag>max_spieltage:
            print("\n🏁 Reguläre Saison beendet – Play‑offs!")
            run_playoffs(season,nord,sued,stats,interactive=interactive)
            # neue Saison vorbereiten
            season+=1; spieltag=1
            if max_seasons and season>max_seasons: break
            nord,sued = pd.DataFrame(nord_teams), pd.DataFrame(sued_teams)
            for d in (nord,sued): d[["Points","Goals For","Goals Against"]]=0
            nsched   = create_schedule(nord_teams)
            ssched   = create_schedule(sued_teams)
            stats    = pd.DataFrame([{"Player":p["Name"],"Team":t["Team"],"Goals":0,"Assists":0} for t in nord_teams+sued_teams for p in t["Players"]])
            # Saison‑Ordner werden beim ersten Spieltag automatisch angelegt.
            save_state({"season":season,"spieltag":spieltag,"nord":nord.to_dict("records"),"sued":sued.to_dict("records"),
                        "nsched":nsched,"ssched":ssched,"stats":stats.to_dict("records")})

# ------------------------------------------------
# 8  CLI‑ENTRYPOINT + SELF‑TESTS
# ------------------------------------------------

if __name__ == "__main__":
    # mini tests
    dummy=[{"Team":str(i)} for i in range(6)]; assert len(create_schedule(dummy))==6*5
    print("✅ Mini‑Tests ok – starte Simulation …")
    run_simulation(interactive=True)
