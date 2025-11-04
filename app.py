import json
import re
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st

# >>> Simulator importieren (Dateiname anpassen, falls deiner anders heißt)
import PlayoffSerie as sim


# ------------------------------------------------------------
#  STREAMLIT GRUNDEINSTELLUNG
# ------------------------------------------------------------
st.set_page_config(page_title="Liga-Simulator GUI", page_icon="🏒", layout="wide")

# ------------------------------------------------------------
#  SIDEBAR – AKTIONEN
# ------------------------------------------------------------
with st.sidebar:
    st.title("🏒 Liga-Simulator")
    st.caption("HIGHspeed · NOVADELTA")

    if st.button("▶️ Nächsten Spieltag simulieren", use_container_width=True):
        res = sim.step_regular_season_once()
        if res.get("status") == "season_over":
            st.toast("Regular Season ist schon beendet. Starte die Playoffs 👇", icon="⚠️")
        elif res.get("status") == "ok":
            st.toast(f"Spieltag {res['spieltag']-1} simuliert → Jetzt {res['spieltag']}", icon="✅")
        else:
            st.toast("Konnte Spieltag nicht simulieren.", icon="❌")

    if st.button("🏒 Nächste Playoff-Runde (Bo7) simulieren", use_container_width=True):
        res = sim.step_playoffs_round_once()
        if res.get("status") == "ok":
            st.toast(f"Playoff-Runde {res['round']} simuliert. Sieger: {', '.join(res['winners'])}", icon="✅")
        elif res.get("status") == "champion":
            st.toast(
                f"🏆 Champion (Saison {sim.load_state()['season']-1}): "
                f"{res['champion']} • Nächste Saison: {res['next_season']}",
                icon="🏆",
            )
        elif res.get("status") == "regular_not_finished":
            st.toast("Regular Season noch nicht fertig – simuliere erst Spieltage.", icon="⚠️")
        else:
            st.toast(f"Playoff-Step nicht möglich: {res.get('status')}", icon="❌")

    if st.button("🏆 Playoffs simulieren & Saison abschließen", use_container_width=True):
        res = sim.simulate_full_playoffs_and_advance()
        if res.get("status") == "ok":
            st.toast(f"Champion: {res['champion']} · Nächste Saison: {res['next_season']}", icon="🏆")
        else:
            st.toast("Playoffs nicht gestartet – fehlt State?", icon="❌")

    if st.button("⏭️ Ganze Saison in einem Rutsch", use_container_width=True):
        sim.run_simulation(max_seasons=1, interactive=False)
        st.toast("Komplette Saison (inkl. Playoffs) simuliert.", icon="⚡")

    if st.button("🔄 Reload Ansicht", use_container_width=True):
        st.rerun()


# ------------------------------------------------------------
#  HAUPTANSICHT
# ------------------------------------------------------------
st.title("Liga-Simulator – GUI")

# ---------- State & Tabellen laden ----------
info = sim.read_tables_for_ui()

PLAYOFF_DIR = Path("playoffs")


# ------------------------------------------------------------
#  HELFER: PLAYOFF-DATEN LADEN UND ANZEIGEN
# ------------------------------------------------------------
def _available_playoff_seasons() -> List[int]:
    if not PLAYOFF_DIR.exists():
        return []
    seasons: List[int] = []
    for p in PLAYOFF_DIR.iterdir():
        if p.is_dir() and p.name.startswith("saison_"):
            try:
                seasons.append(int(p.name.split("_")[1]))
            except ValueError:
                pass
    return sorted(seasons)


def _load_latest_round(season: int) -> Optional[dict]:
    """Lädt die JSON der neuesten Playoff-Runde einer Saison."""
    folder = PLAYOFF_DIR / f"saison_{season}"
    if not folder.exists():
        return None
    rounds = []
    for f in folder.iterdir():
        m = re.match(r"runde_(\d+)\.json$", f.name)
        if f.is_file() and m:
            rounds.append((int(m.group(1)), f))
    if not rounds:
        return None
    _, newest = sorted(rounds)[-1]
    try:
        return json.loads(newest.read_text(encoding="utf-8"))
    except Exception:
        return None


def _render_series_block(round_json: dict):
    """Zeigt alle Serien einer Runde inkl. Spiele an."""
    st.markdown(f"#### Playoff-Runde {round_json.get('runde')} (Saison {round_json.get('saison')})")
    series_list = round_json.get("series", [])
    if not series_list:
        st.info("Keine Serien in dieser Runde gefunden.")
        return
    for s in series_list:
        a = s["a"]
        b = s["b"]
        result = s["result"]
        winner = s["winner"]
        with st.expander(f"🏟️ {a} vs {b} — Ergebnis: {result}  •  Sieger: {winner}", expanded=True):
            games = s.get("games", [])
            if not games:
                st.write("Keine Einzelspiele gespeichert.")
            else:
                df = pd.DataFrame(
                    [
                        {
                            "Spiel": g["g"],
                            "Home": g["home"],
                            "Away": g["away"],
                            "Score": f"{g['g_home']} : {g['g_away']}",
                        }
                        for g in games
                    ]
                )
                st.dataframe(df, use_container_width=True, hide_index=True)


# ------------------------------------------------------------
#  TABELLEN & TOP-SCORER
# ------------------------------------------------------------
col_l, col_r = st.columns([2, 1], gap="large")

with col_l:
    st.subheader(f"📅 Saison {info['season']} · Spieltag {info['spieltag']}")
    st.caption(f"Rest-Schedule: Nord {info['nsched_len']} · Süd {info['ssched_len']} Paarungen offen")

    tn = pd.DataFrame(info["tables"]["tabelle_nord"])
    ts = pd.DataFrame(info["tables"]["tabelle_sued"])
    st.markdown("### 📊 Tabelle Nord")
    st.dataframe(tn, use_container_width=True, hide_index=True)
    st.markdown("### 📊 Tabelle Süd")
    st.dataframe(ts, use_container_width=True, hide_index=True)

with col_r:
    st.markdown("### ⭐ Top-Scorer (Top 20)")
    tops = pd.DataFrame(info["tables"]["top_scorer"])
    st.dataframe(tops, use_container_width=True, hide_index=True, height=480)

st.divider()

# ------------------------------------------------------------
#  HISTORY
# ------------------------------------------------------------
st.markdown("### 🗂️ Saison-History")
hist = info.get("history", [])
if hist:
    hdf = pd.DataFrame(hist).sort_values("season")
    st.dataframe(hdf, use_container_width=True, hide_index=True)
else:
    st.info("Noch keine abgeschlossene Saison.")

# ------------------------------------------------------------
#  PLAYOFF-ANSICHT
# ------------------------------------------------------------
st.divider()
st.markdown("### 🏆 Playoffs – aktuelle Runde / Saison wählen")

playoff_seasons = _available_playoff_seasons()
if playoff_seasons:
    default_season = playoff_seasons[-1]
    try:
        current_season_from_state = info["season"]
        if current_season_from_state in playoff_seasons:
            default_season = current_season_from_state
        elif (current_season_from_state - 1) in playoff_seasons:
            default_season = current_season_from_state - 1
    except Exception:
        pass

    sel = st.selectbox(
        "Welche Saison anzeigen?",
        options=playoff_seasons,
        index=playoff_seasons.index(default_season),
        format_func=lambda s: f"Saison {s}",
    )

    round_json = _load_latest_round(sel)
    if round_json:
        _render_series_block(round_json)
    else:
        st.info("Für diese Saison existieren noch keine Playoff-Runden.")
else:
    st.info("Noch keine Playoff-Daten gefunden. Simuliere zuerst eine Saison bis in die Playoffs.")
