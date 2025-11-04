# app.py — Liga-Simulator GUI (schnell, mit Logos, History-Browser, Downloads)

import json
import re
import base64
import unicodedata
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import streamlit as st

# ============================================================
# Pfade
# ============================================================
BASE_DIR      = Path(__file__).parent.resolve()
SPIELTAG_DIR  = BASE_DIR / "spieltage"
PLAYOFF_DIR   = BASE_DIR / "playoffs"
LOGO_DIR      = BASE_DIR / "assets" / "logos" / "teams"

# ============================================================
# Utils: Slug, Logos (gecacht), sichere Texte
# ============================================================
def _slugify(name: str) -> str:
    repl = (("ä","ae"),("ö","oe"),("ü","ue"),("Ä","Ae"),("Ö","Oe"),("Ü","Ue"),("ß","ss"))
    for a,b in repl: name = name.replace(a,b)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[^a-zA-Z0-9]+","-", name).strip("-").lower()
    return name

@st.cache_resource
def _build_logo_b64_map() -> Dict[str, str]:
    """Liest alle Logos EINMAL und liefert slug -> data:image/...;base64 URL."""
    m: Dict[str, str] = {}
    if not LOGO_DIR.exists(): return m
    for f in LOGO_DIR.iterdir():
        if not f.is_file(): continue
        ext = f.suffix.lower().lstrip(".")
        if ext not in {"png","jpg","jpeg","webp","gif","svg"}: continue
        mime = "image/svg+xml" if ext == "svg" else f"image/{'jpeg' if ext in ('jpg','jpeg') else ext}"
        try:
            b64 = base64.b64encode(f.read_bytes()).decode("utf-8")
            m[f.stem] = f"data:{mime};base64,{b64}"
        except Exception:
            pass
    return m

def team_logo_dataurl(team: str, size: int = 18) -> str:
    """O(1): Holt fertige DataURL aus Cache, KEIN Dateizugriff pro Zelle."""
    if team is None or (isinstance(team, float) and pd.isna(team)): return ""
    slug = _slugify(str(team))
    url = _build_logo_b64_map().get(slug)
    if not url: return ""
    return f'<img src="{url}" width="{size}" height="{size}" style="vertical-align:middle;border-radius:4px;margin-right:8px;" />'

def _safe_txt(v: Any) -> str:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)): return ""
        return str(v)
    except Exception:
        return ""

@st.cache_data(show_spinner=False)
def _render_html_table_cached(rows: List[Dict[str, Any]], columns: List[tuple]) -> str:
    # deterministischer Cache-Key (Streamlit cached ohnehin über Inputs)
    _ = hashlib.sha1(json.dumps({"rows":rows, "cols":columns}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    th = "".join(f"<th style='text-align:left;padding:8px 12px;'>{label}</th>" for _, label in columns)
    trs = []
    for r in rows:
        tds = []
        for k, _label in columns:
            val = r.get(k, "")
            tds.append(f"<td style='padding:8px 12px;text-align:left'>{val}</td>")
        trs.append(f"<tr>{''.join(tds)}</tr>")
    return (
        "<div style='overflow:auto;border:1px solid #2a2f3a;border-radius:8px;'>"
        "<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
        f"<thead style='background:#181b22;color:#cfd3db'>{th}</thead>"
        f"<tbody>{''.join(trs)}</tbody>"
        "</table></div>"
    )

# ============================================================
# Simulator-Backend
# ============================================================
import PlayoffSerie as sim  # deine Simulations-Logik (Bo7 etc.)

# ============================================================
# Streamlit Setup
# ============================================================
st.set_page_config(page_title="Liga-Simulator GUI", page_icon="🏒", layout="wide")

# ============================================================
# Sidebar – Steuerung
# ============================================================
with st.sidebar:
    st.title("🏒 Liga-Simulator")
    st.caption("HIGHspeed · NOVADELTA")

    if st.button("▶️ Nächsten Spieltag simulieren", key="btn_spieltag", use_container_width=True):
        res = sim.step_regular_season_once()
        if res.get("status") == "season_over":
            st.toast("Regular Season ist beendet. Starte die Playoffs 👇", icon="⚠️")
        elif res.get("status") == "ok":
            st.toast(f"Spieltag {res['spieltag']-1} simuliert → Jetzt {res['spieltag']}", icon="✅")
        else:
            st.toast("Konnte Spieltag nicht simulieren.", icon="❌")

    if st.button("🏒 Nächste Playoff-Runde (Bo7) simulieren", key="btn_po_round", use_container_width=True):
        res = sim.step_playoffs_round_once()
        if res.get("status") == "ok":
            st.toast(f"Playoff-Runde {res['round']} simuliert. Sieger: {', '.join(res['winners'])}", icon="✅")
        elif res.get("status") == "champion":
            st.toast(
                f"🏆 Champion (Saison {sim.load_state()['season']-1}): {res['champion']} • Nächste Saison: {res['next_season']}",
                icon="🏆",
            )
        elif res.get("status") == "regular_not_finished":
            st.toast("Regular Season noch nicht fertig – simuliere erst Spieltage.", icon="⚠️")
        else:
            st.toast(f"Playoff-Step nicht möglich: {res.get('status')}", icon="❌")

    if st.button("🏆 Playoffs simulieren & Saison abschließen", key="btn_po_full", use_container_width=True):
        res = sim.simulate_full_playoffs_and_advance()
        if res.get("status") == "ok":
            st.toast(f"Champion: {res['champion']} · Nächste Saison: {res['next_season']}", icon="🏆")
        else:
            st.toast("Playoffs nicht gestartet – fehlt State?", icon="❌")

    if st.button("⏭️ Ganze Saison in einem Rutsch", key="btn_full_season", use_container_width=True):
        sim.run_simulation(max_seasons=1, interactive=False)
        st.toast("Komplette Saison (inkl. Playoffs) simuliert.", icon="⚡")

    if st.button("🔄 Reload Ansicht", key="btn_reload", use_container_width=True):
        st.rerun()

# ============================================================
# Hauptansicht – Tabellen / Scorer
# ============================================================
st.title("Liga-Simulator – GUI")
info = sim.read_tables_for_ui()

col_l, col_r = st.columns([2, 1], gap="large")

with col_l:
    st.subheader(f"📅 Saison {info['season']} · Spieltag {info['spieltag']}")
    st.caption(f"Rest-Schedule: Nord {info['nsched_len']} · Süd {info['ssched_len']} Paarungen offen")

    # Tabellen (HTML mit Logos, schnell)
    st.markdown("### 📊 Tabelle Nord")
    tn = pd.DataFrame(info["tables"]["tabelle_nord"]).copy()
    tn["TeamHTML"] = tn["Team"].apply(lambda t: f"{team_logo_dataurl(t, 18)}{_safe_txt(t)}")
    tn_rows = tn.rename(columns={"Points":"P"})[["TeamHTML","P","GF","GA","GD"]].to_dict("records")
    st.markdown(_render_html_table_cached(
        tn_rows, [("TeamHTML","Team"), ("P","P"), ("GF","GF"), ("GA","GA"), ("GD","GD")]
    ), unsafe_allow_html=True)

    st.markdown("### 📊 Tabelle Süd")
    ts = pd.DataFrame(info["tables"]["tabelle_sued"]).copy()
    ts["TeamHTML"] = ts["Team"].apply(lambda t: f"{team_logo_dataurl(t, 18)}{_safe_txt(t)}")
    ts_rows = ts.rename(columns={"Points":"P"})[["TeamHTML","P","GF","GA","GD"]].to_dict("records")
    st.markdown(_render_html_table_cached(
        ts_rows, [("TeamHTML","Team"), ("P","P"), ("GF","GF"), ("GA","GA"), ("GD","GD")]
    ), unsafe_allow_html=True)

with col_r:
    st.markdown("### ⭐ Top-Scorer (Top 20)")
    tops = pd.DataFrame(info["tables"]["top_scorer"]).copy()
    tops["PlayerHTML"] = tops.apply(
        lambda r: f"{team_logo_dataurl(r.get('Team'), 16)}{_safe_txt(r.get('Player'))} "
                  f"<span style='opacity:.7'>({_safe_txt(r.get('Team'))})</span>", axis=1
    )
    tops_rows = tops[["PlayerHTML","Goals","Assists","Points"]].to_dict("records")
    st.markdown(_render_html_table_cached(
        tops_rows, [("PlayerHTML","Spieler"), ("Goals","G"), ("Assists","A"), ("Points","P")]
    ), unsafe_allow_html=True)

st.divider()

# ============================================================
# Spieltag-Browser (History & Download)
# ============================================================
@st.cache_data(show_spinner=False)
def list_spieltage_seasons() -> List[int]:
    if not SPIELTAG_DIR.exists(): return []
    vals=[]
    for p in SPIELTAG_DIR.iterdir():
        if p.is_dir() and p.name.startswith("saison_"):
            try: vals.append(int(p.name.split("_")[1]))
            except: pass
    return sorted(vals)

@st.cache_data(show_spinner=False)
def list_gamedays(season: int) -> List[int]:
    folder = SPIELTAG_DIR / f"saison_{season}"
    if not folder.exists(): return []
    vals=[]
    for f in folder.iterdir():
        m = re.match(r"spieltag_(\d+)\.json$", f.name)
        if f.is_file() and m: vals.append(int(m.group(1)))
    return sorted(vals)

@st.cache_data(show_spinner=False)
def load_gameday_json(season: int, gameday: int) -> Optional[dict]:
    f = SPIELTAG_DIR / f"saison_{season}" / f"spieltag_{gameday:02}.json"
    if not f.exists(): return None
    try: return json.loads(f.read_text(encoding="utf-8"))
    except: return None

def tag_chip(entry: dict) -> str:
    t = (entry.get("type") or "").upper()
    ot = bool(entry.get("ot")); so = bool(entry.get("so"))
    label = "SO" if (t=="SO" or so) else ("OT" if (t=="OT" or ot) else "")
    if not label: return ""
    return "<span style='display:inline-block;padding:2px 6px;border-radius:10px;border:1px solid #2a9d8f;margin-left:8px;font-size:11px;color:#9be7e0'>{}</span>".format(label)

def result_row_html(entry: dict) -> str:
    """Kompakte, einzeilige HTML-Zeile (keine Einrückungen/Zeilenumbrüche ⇒ kein Codeblock)."""
    home = entry["home"]; away = entry["away"]
    gh = entry["g_home"]; ga = entry["g_away"]
    chip = tag_chip(entry)
    return (
        "<div style='display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #222a33;'>"
        f"{team_logo_dataurl(home, 20)}<strong style='min-width:220px'>{home}</strong>"
        "<span style='opacity:.7'>vs</span>"
        f"{team_logo_dataurl(away, 20)}<strong style='min-width:220px'>{away}</strong>"
        f"<span style='margin-left:auto;font-weight:700'>{gh} : {ga}</span>{chip}"
        "</div>"
    )

st.markdown("### 🧾 Spieltag-Browser (History & Download)")

# Session-State Defaults
if "sel_season" not in st.session_state:
    st.session_state.sel_season = max(list_spieltage_seasons() or [info["season"]])
if "sel_gameday" not in st.session_state:
    gds = list_gamedays(st.session_state.sel_season)
    st.session_state.sel_gameday = (gds[-1] if gds else 1)

cols = st.columns([1,2,1,1,1])
with cols[0]:
    seasons_available = list_spieltage_seasons()
    st.session_state.sel_season = st.selectbox(
        "Saison", options=seasons_available or [info["season"]],
        index=(len(seasons_available)-1) if seasons_available else 0,
        format_func=lambda s: f"Saison {s}", key="dd_season_browser"
    )
with cols[1]:
    gds = list_gamedays(st.session_state.sel_season)
    cprev, csel, cnext = st.columns([1,3,1])
    with cprev:
        if st.button("◀", key="gd_prev") and gds:
            cur = st.session_state.get("sel_gameday", gds[-1])
            idx = gds.index(cur) if cur in gds else len(gds)-1
            st.session_state.sel_gameday = gds[max(0, idx-1)]
    with csel:
        st.session_state.sel_gameday = st.selectbox(
            "Spieltag", options=gds or [1],
            index=(len(gds)-1 if gds else 0), key="dd_gameday_browser"
        )
    with cnext:
        if st.button("▶", key="gd_next") and gds:
            cur = st.session_state.get("sel_gameday", gds[-1])
            idx = gds.index(cur) if cur in gds else len(gds)-1
            st.session_state.sel_gameday = gds[min(len(gds)-1, idx+1)]

gjson = load_gameday_json(st.session_state.sel_season, st.session_state.sel_gameday)
if not gjson:
    st.info("Für diese Auswahl existiert (noch) kein Spieltag.")
else:
    st.caption(f"Saison {gjson['saison']} · Spieltag {gjson['spieltag']} • {gjson['timestamp']}")
    res = gjson.get("results", [])

    nord_block = "".join(result_row_html(r) for r in res if _safe_txt(r.get("conference")) == "Nord")
    sued_block = "".join(result_row_html(r) for r in res if _safe_txt(r.get("conference")) == "Süd")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Nord")
        st.markdown(f"<div>{nord_block or '<em>Keine Spiele</em>'}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("#### Süd")
        st.markdown(f"<div>{sued_block or '<em>Keine Spiele</em>'}</div>", unsafe_allow_html=True)

    # Downloads
    st.markdown("#### Download")
    st.download_button(
        "📦 JSON (Original)",
        data=json.dumps(gjson, ensure_ascii=False, indent=2),
        file_name=f"s{gjson['saison']:02}_spieltag_{gjson['spieltag']:02}.json",
        mime="application/json", use_container_width=True, key="dl_json_gd"
    )
    df_csv = pd.DataFrame(res)
    st.download_button(
        "🧾 CSV (Ergebnisse)",
        data=df_csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"s{gjson['saison']:02}_spieltag_{gjson['spieltag']:02}.csv",
        mime="text/csv", use_container_width=True, key="dl_csv_gd"
    )

st.divider()

# ============================================================
# Playoff-Browser (History & Download)
# ============================================================
@st.cache_data(show_spinner=False)
def list_playoff_seasons() -> List[int]:
    if not PLAYOFF_DIR.exists(): return []
    vals=[]
    for p in PLAYOFF_DIR.iterdir():
        if p.is_dir() and p.name.startswith("saison_"):
            try: vals.append(int(p.name.split("_")[1]))
            except: pass
    return sorted(vals)

@st.cache_data(show_spinner=False)
def list_rounds(season: int) -> List[int]:
    folder = PLAYOFF_DIR / f"saison_{season}"
    if not folder.exists(): return []
    vals=[]
    for f in folder.iterdir():
        m = re.match(r"runde_(\d+)\.json$", f.name)
        if f.is_file() and m: vals.append(int(m.group(1)))
    return sorted(vals)

@st.cache_data(show_spinner=False)
def load_round_json(season: int, rnd: int) -> Optional[dict]:
    f = PLAYOFF_DIR / f"saison_{season}" / f"runde_{rnd:02}.json"
    if not f.exists(): return None
    try: return json.loads(f.read_text(encoding="utf-8"))
    except: return None

st.markdown("### 🏆 Playoff-Browser (History & Download)")
if "po_season" not in st.session_state:
    st.session_state.po_season = max(list_playoff_seasons() or [info["season"]])
if "po_round" not in st.session_state:
    rs = list_rounds(st.session_state.po_season)
    st.session_state.po_round = (rs[-1] if rs else 1)

pc1, pc2, pc3 = st.columns([2,3,2])
with pc1:
    pos = list_playoff_seasons()
    if pos:
        st.session_state.po_season = st.selectbox(
            "Saison", options=pos, index=(len(pos)-1),
            format_func=lambda s: f"Saison {s}", key="po_season_sel"
        )
with pc2:
    rs = list_rounds(st.session_state.po_season)
    rprev, rsel, rnext = st.columns([1,3,1])
    with rprev:
        if st.button("◀", key="po_prev") and rs:
            cur = st.session_state.get("po_round", rs[-1])
            idx = rs.index(cur) if cur in rs else len(rs)-1
            st.session_state.po_round = rs[max(0, idx-1)]
    with rsel:
        st.session_state.po_round = st.selectbox(
            "Runde", options=rs or [1], index=(len(rs)-1 if rs else 0), key="po_round_sel"
        )
    with rnext:
        if st.button("▶", key="po_next") and rs:
            cur = st.session_state.get("po_round", rs[-1])
            idx = rs.index(cur) if cur in rs else len(rs)-1
            st.session_state.po_round = rs[min(len(rs)-1, idx+1)]

po_json = load_round_json(st.session_state.po_season, st.session_state.po_round) if list_playoff_seasons() else None

def _render_series_block(round_json: dict):
    st.markdown(f"#### Playoff-Runde {round_json.get('runde')} (Saison {round_json.get('saison')})")
    series_list = round_json.get("series", [])
    if not series_list:
        st.info("Keine Serien in dieser Runde gefunden.")
        return
    for s in series_list:
        a = s["a"]; b = s["b"]; result = s["result"]; winner = s["winner"]
        with st.expander(f"{a} vs {b} — Ergebnis: {result}  •  Sieger: {winner}", expanded=True):
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                la = _build_logo_b64_map().get(_slugify(a)); 
                if la: st.image(la, width=96)
                st.caption(a)
            with c2:
                st.markdown(f"**Serie:** {result}<br/>**Sieger:** {winner}", unsafe_allow_html=True)
            with c3:
                lb = _build_logo_b64_map().get(_slugify(b));
                if lb: st.image(lb, width=96)
                st.caption(b)
            games = s.get("games", [])
            if games:
                df = pd.DataFrame([
                    {"Spiel": g["g"], "Home": g["home"], "Away": g["away"],
                     "Score": f"{g['g_home']} : {g['g_away']}"}
                    for g in games
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.write("Keine Einzelspiele gespeichert.")

if po_json:
    _render_series_block(po_json)
    st.markdown("#### Download")
    st.download_button(
        "📦 JSON (Playoff-Runde)",
        data=json.dumps(po_json, ensure_ascii=False, indent=2),
        file_name=f"s{po_json['saison']:02}_runde_{po_json['runde']:02}.json",
        mime="application/json", use_container_width=True, key="dl_json_po"
    )
    rows=[]
    for s in po_json.get("series", []):
        for g in s.get("games", []):
            rows.append({
                "Serie_A": s["a"], "Serie_B": s["b"], "Result": s["result"], "Winner": s["winner"],
                "Game": g["g"], "Home": g["home"], "Away": g["away"], "G_Home": g["g_home"], "G_Away": g["g_away"]
            })
    df_po = pd.DataFrame(rows)
    st.download_button(
        "🧾 CSV (Playoff-Runde, Spiele)",
        data=df_po.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"s{po_json['saison']:02}_runde_{po_json['runde']:02}.csv",
        mime="text/csv", use_container_width=True, key="dl_csv_po"
    )
else:
    st.info("Noch keine Playoff-Daten gefunden oder Auswahl leer.")

st.divider()

# ============================================================
# Saison-History
# ============================================================
st.markdown("### 🗂️ Saison-History (Champions & Navigation)")
hist = info.get("history", []) or []
if hist:
    hdf = pd.DataFrame(hist).sort_values("season")
    st.dataframe(hdf, use_container_width=True, hide_index=True)
else:
    st.info("Noch keine abgeschlossene Saison – simuliere bis zum Champion.")
