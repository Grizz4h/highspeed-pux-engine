# ================================================
#  LIGA‑SIMULATOR  –  Round‑Robin + Play‑offs
#  Version 4.0 – stabil, interaktiv & web‑export
# ================================================
"""Simulation einer Eishockey‑Liga (Nord/Süd‑Conference).

✅  INTERAKTIVE SPIELTAGE – <Enter> startet immer nur *einen* Spieltag.
✅  JSON‑Exports nach jedem Spieltag *und* jeder Play‑off‑Runde:
    
```json
{
  "timestamp": "2025‑07‑14T15:04:05",
  "saison": 1,
  "spieltag": 3,
  "results": [
    {"home": "Iserlohn", "away": "Berlin", "g_home": 4, "g_away": 2, "conference": "Nord"},
    ...
  ],
  "tabelle_nord": [{"Team": "…", "Points": 9, "GF": 14, "GA": 8, "GD": 6}, …],
  "tabelle_sued": […],
  "top_scorer": [{"Player": "…", "Team": "…", "Goals": 5, "Assists": 4, "Points": 9}, …]
}
```

Die Datei ist **vollständig** und enthält Self‑Tests. Bei Wunsch nach
Massen‑Simulation kann `interactive=False` verwendet werden.
"""

from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

# ------------------------------------------------
# 1  KONSTANTEN & PFADE
# ------------------------------------------------
SAVEFILE     = Path("saves/savegame.json")
SPIELTAG_DIR = Path("spieltage")
PLAYOFF_DIR  = Path("playoffs")

# ------------------------------------------------
# 2  TEAMS LADEN
# ------------------------------------------------
from realeTeams import nord_teams, sued_teams  # noqa: E402

# ------------------------------------------------
# 3  HILFSFUNKTIONEN SPEICHERN / LADEN
# ------------------------------------------------

def _ensure_dirs() -> None:
    for p in (SAVEFILE.parent, SPIELTAG_DIR, PLAYOFF_DIR):
        p.mkdir(parents=True, exist_ok=True)

def get_next_season_number() -> int:
    if not SPIELTAG_DIR.exists():
        return 1
    nums = [
        int(p.name.split("_")[1])
        for p in SPIELTAG_DIR.iterdir()
        if p.is_dir() and p.name.startswith("saison_") and p.name.split("_")[1].isdigit()
    ]
    return max(nums, default=0) + 1

# ------------------------------------------------
# 4  JSON‑EXPORT HELPERS
# ------------------------------------------------

def _export_tables(nord_df: pd.DataFrame, sued_df: pd.DataFrame, stats: pd.DataFrame) -> Dict[str, Any]:
    stats["Points"] = stats["Goals"] + stats["Assists"]

    def _prep(df: pd.DataFrame) -> List[Dict[str, Any]]:
        d = df.copy()
        d.rename(columns={"Goals For": "GF", "Goals Against": "GA"}, inplace=True)
        d["GD"] = d["GF"] - d["GA"]
        return d.sort_values(["Points", "GF"], ascending=False)[["Team", "Points", "GF", "GA", "GD"]].to_dict("records")

    return {
        "tabelle_nord": _prep(nord_df),
        "tabelle_sued": _prep(sued_df),
        "top_scorer": stats.sort_values("Points", ascending=False)
            .head(20)[["Player", "Team", "Goals", "Assists", "Points"]]
            .to_dict("records"),
    }


def save_spieltag_json(
    saison: int,
    spieltag: int,
    results: List[Dict[str, Any]],
    nord_df: pd.DataFrame,
    sued_df: pd.DataFrame,
    stats: pd.DataFrame,
) -> None:
    folder = SPIELTAG_DIR / f"saison_{saison}"
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / f"spieltag_{spieltag:02}.json"
    data = {
        "timestamp": datetime.now().isoformat(),
        "saison": saison,
        "spieltag": spieltag,
        "results": results,
        **_export_tables(nord_df, sued_df, stats),
    }
    with file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("📦 JSON gespeichert →", file)


def save_playoff_json(
    saison: int,
    runde: int,
    results: List[str],
    nord_df: pd.DataFrame,
    sued_df: pd.DataFrame,
    stats: pd.DataFrame,
) -> None:
    folder = PLAYOFF_DIR / f"saison_{saison}"
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / f"runde_{runde:02}.json"
    data = {
        "timestamp": datetime.now().isoformat(),
        "saison": saison,
        "runde": runde,
        "spiele": results,
        **_export_tables(nord_df, sued_df, stats),
    }
    with file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("📦 Play‑off‑JSON gespeichert →", file)

# ------------------------------------------------
# 5  BERECHNUNGEN & SIMULATION
# ------------------------------------------------

def calc_strength(row: pd.Series, home: bool = False) -> float:
    players = row["Players"]
    base = (
        sum(p["Offense"] for p in players)*0.4 +
        sum(p["Defense"] for p in players)*0.3 +
        sum(p["Speed"]   for p in players)*0.2 +
        sum(p["Chemistry"] for p in players)*0.1
    ) / len(players)
    total = base
    total *= 1 + random.uniform(-5,5)/100
    total *= 1 + row.get("Momentum",0)/100
    total *= 1 + (3 if home else 0)/100
    total *= 1 + random.uniform(-1,2)/100
    return round(total,2)


def create_schedule(teams: List[Dict[str,Any]]) -> List[Tuple[str,str]]:
    teams = teams.copy()
    if len(teams)%2:
        teams.append({"Team":"BYE"})
    days, half = len(teams)-1, len(teams)//2
    sched=[]
    for d in range(days*2):
        day=[]
        for i in range(half):
            a,b = teams[i]["Team"],teams[-i-1]["Team"]
            day.append((a,b) if d%2==0 else (b,a))
        sched.extend(day)
        teams.insert(1,teams.pop())
    return sched


def update_player_stats(team:str,goals:int,df:pd.DataFrame,stats:pd.DataFrame)->None:
    roster=df.loc[df["Team"]==team,"Players"].iloc[0]
    roster=random.sample(roster,18) if len(roster)>18 else roster
    names=[p["Name"] for p in roster]
    weights=[max(1,p["Offense"]//5) for p in roster]
    for _ in range(goals):
        scorer=random.choices(names,weights)[0]
        assister=random.choice([n for n in names if n!=scorer])
        stats.loc[stats["Player"]==scorer,"Goals"]+=1
        stats.loc[stats["Player"]==assister,"Assists"]+=1


def simulate_match(df:pd.DataFrame,home:str,away:str,stats:pd.DataFrame,conf:str)->Tuple[str,Dict[str,Any]]:
    r_h,r_a=df[df["Team"]==home].iloc[0],df[df["Team"]==away].iloc[0]
    p_home=calc_strength(r_h,True)/(calc_strength(r_h,True)+calc_strength(r_a))
    g_home=max(0,int(random.gauss(p_home*5,1)))
    g_away=max(0,int(random.gauss((1-p_home)*5,1)))
    # update standings
    df.loc[df["Team"]==home,["Goals For","Goals Against"]]+= [g_home,g_away]
    df.loc[df["Team"]==away,["Goals For","Goals Against"]]+= [g_away,g_home]
    if g_home>g_away:
        df.loc[df["Team"]==home,"Points"]+=3
    elif g_away>g_home:
        df.loc[df["Team"]==away,"Points"]+=3
    else:
        df.loc[df["Team"].isin([home,away]),"Points"]+=1
    update_player_stats(home,g_home,df,stats)
    update_player_stats(away,g_away,df,stats)
    res_str=f"{home} {g_home}:{g_away} {away}"
    res_json={"home":home,"away":away,"g_home":g_home,"g_away":g_away,"conference":conf}
    return res_str,res_json


def init_stats()->pd.DataFrame:
    return pd.DataFrame([
        {"Player":p["Name"],"Team":t["Team"],"Goals":0,"Assists":0}
        for t in nord_teams+sued_teams for p in t["Players"]
    ])

# ---------------- PLAY‑OFFS ---------------------

def simulate_playoff_match(a:str,b:str,nord:pd.DataFrame,sued:pd.DataFrame,stats:pd.DataFrame)->Tuple[str,str]:
    dfA = nord if a in list(nord["Team"]) else sued
    dfB = nord if b in list(nord["Team"]) else sued
    sA,sB=calc_strength(dfA[dfA["Team"]==a].iloc[0]),calc_strength(dfB[dfB["Team"]==b].iloc[0])
    pA=sA/(sA+sB)
    gA=max(0,int(random.gauss(pA*5,1)))
    gB=max(0,int(random.gauss((1-pA)*5,1)))
    update_player_stats(a,gA,dfA,stats)
    update_player_stats(b,gB,dfB,stats)
    res=f"{a} {gA}:{gB} {b}"
    return res,(a if gA>gB else b)


def run_playoffs(season:int,nord:pd.DataFrame,sued:pd.DataFrame,stats:pd.DataFrame)->None:
    nord4=nord.sort_values(["Points","Goals For"],ascending=False).head(4)
    sued4=sued.sort_values(["Points","Goals For"],ascending=False).head(4)
    pair=[
        (nord4.iloc[0]["Team"],sued4.iloc[3]["Team"]),
        (nord4.iloc[1]["Team"],sued4.iloc[2]["Team"]),
        (nord4.iloc[2]["Team"],sued4.iloc[1]["Team"]),
        (nord4.iloc[3]["Team"],sued4.iloc[0]["Team"]),
    ]
    rnd=1
    while True:
        print(f"\n=== PLAY‑OFF RUNDE {rnd} (Saison {season}) ===")
        results=[]; winners=[]
        for a,b in pair:
            res,win=simulate_playoff_match(a,b,nord,sued,stats)
            print(res)
            results.append(res)
            winners.append(win)
        save_playoff_json(season,rnd,results,nord,sued,stats)
        if len(winners)==1:
            print(f"\n🏆 Champion Saison {season}: {winners[0]} 🏆\n")
            break
        pair=[(winners[i],winners[i+1]) for i in range(0,len(winners),2)]
        rnd+=1

# ---------------- SAISON LOOP ------------------

def _init_frames()->Tuple[pd.DataFrame,pd.DataFrame]:
    n=pd.DataFrame(nord_teams)
    s=pd.DataFrame(sued_teams)
    for d in (n,s):
        d[["Points","Goals For","Goals Against"]]=0
    return n,s


def run_simulation(max_seasons:int|None=None,interactive:bool=True)->None:
    _ensure_dirs()
    season=get_next_season_number()
    nord,sued=_init_frames()
    nsched=create_schedule(nord_teams)
    ssched=create_schedule(sued_teams)
    stats=init_stats()
    spieltag=1
    max_spieltage=(len(nord_teams)-1)*2
    while max_seasons is None or season<=max_seasons:
        if interactive:
            input(f"➡️  Enter für Spieltag {spieltag} (Saison {season}) …")
        results_str=[]; results_json=[]
        print("\n— Nord —")
        for m in nsched[:len(nord)//2]:
            s,j=simulate_match(nord,*m,stats,"Nord")
            print(s)
            results_str.append(s)
            results_json.append(j)
        nsched=nsched[len(nord)//2:]
        print("\n— Süd —")
        for m in ssched[:len(sued)//2]:
            s,j=simulate_match(sued,*m,stats,"Süd")
            print(s)
            results_str.append(s)
            results_json.append(j)
        ssched=ssched[len(sued)//2:]
        # Export JSON
        save_spieltag_json(season,spieltag,results_json,nord,sued,stats)
        spieltag+=1
        if spieltag>max_spieltage:
            print("\n🏁 Reguläre Saison beendet – Play‑offs!")
            run_playoffs(season,nord,sued,stats)
            # reset for next season
            season+=1
            if max_seasons is not None and season>max_seasons:
                break
            nord,sued=_init_frames()
            nsched=create_schedule(nord_teams)
            ssched=create_schedule(sued_teams)
            stats=init_stats()
            spieltag=1

# ---------------- SELF‑TESTS -------------------

def _self_tests()->None:
    dummy=[{"Team":str(i)} for i in range(6)]
    assert len(create_schedule(dummy))==6*5, "Schedule wrong"           
    fake_row=pd.Series({"Players":[{"Offense":60,"Defense":60,"Speed":60,"Chemistry":60} for _ in range(5)]})
    assert 0<calc_strength(fake_row)<100, "Strength out of range"
    print("✅ Self‑Tests bestanden")


if __name__=="__main__":
    _self_tests()
    print("\n⚡ Demo‑Saison (interaktiv) startet —")
    run_simulation(max_seasons=1,interactive=True)
    print("\n🎉 Fertig. JSONs sind in den Verzeichnissen 'spieltage' und 'playoffs'.")
