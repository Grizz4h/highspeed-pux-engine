# app.py — Liga-Simulator GUI (schnell, Logos, History, Bo7, Live-Reload)
# HIGHspeed · NOVADELTA

import json
import re
import hashlib
import unicodedata
import base64
import subprocess
import sys
import os

from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import streamlit as st
from PIL import Image

# ============================================================
# Pfade & Basiskonfig
# ============================================================
BASE_DIR      = Path(__file__).parent.resolve()
SPIELTAG_DIR  = BASE_DIR / "spieltage"
PLAYOFF_DIR   = BASE_DIR / "playoffs"
LOGO_DIR      = BASE_DIR / "assets" / "logos" / "teams"
THUMB_DIR     = BASE_DIR / ".cache_thumbs"
THUMB_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Liga-Simulator GUI", page_icon="🏒", layout="wide")

# ============================================================
# Utils
# ============================================================
def _slugify(name: str) -> str:
    repl = (("ä","ae"),("ö","oe"),("ü","ue"),("Ä","Ae"),("Ö","Oe"),("Ü","Ue"),("ß","ss"))
    for a,b in repl:
        name = name.replace(a,b)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[^a-zA-Z0-9]+","-", name).strip("-").lower()
    return name

def _logo_file_for_team(team: str) -> Optional[Path]:
    if not team:
        return None
    slug = _slugify(str(team))
    for ext in (".webp",".png",".jpg",".jpeg",".gif",".svg"):
        p = LOGO_DIR / f"{slug}{ext}"
        if p.exists():
            return p
    return None

@st.cache_data(show_spinner=False)
def get_logo_thumb_path(team: str, size: int = 24, scale: int = 2) -> Optional[str]:
    """
    Liefert Pfad zu einem WEBP-Thumbnail.
    - size:   Zielgröße in CSS-Pixeln (z. B. 24)
    - scale:  Render-Faktor (2 = Hi-DPI), Bild wird auf size*scale gerendert,
              aber später kleiner angezeigt -> sichtbar schärfer.
    """
    src = _logo_file_for_team(team)
    if not src or src.suffix.lower() == ".svg":
        return None

    slug = _slugify(str(team))
    px   = size * max(1, int(scale))
    out  = THUMB_DIR / f"{slug}_{size}x{scale}.webp"

    try:
        # Neu rendern, wenn nicht vorhanden oder Quelle neuer ist
        if (not out.exists()) or (out.stat().st_mtime < src.stat().st_mtime):
            im = Image.open(src).convert("RGBA")
            im.thumbnail((px, px), Image.LANCZOS)

            # Quadratische Canvas, damit in Tabellen nichts „springt“
            canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
            x = (px - im.width) // 2
            y = (px - im.height) // 2
            canvas.paste(im, (x, y), im)

            # WEBP: etwas höhere Qualität für kleine Logos, trotzdem klein
            canvas.save(out, "WEBP", quality=88, method=6)
        return out.as_posix()
    except Exception:
        return None

def _safe_txt(v: Any) -> str:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        return str(v)
    except Exception:
        return ""

def dir_signature(path: Path) -> str:
    """Hash über Dateinamen + mtime_ns aller JSONs im Ordner (rekursiv). Ändert sich bei neuen/überschriebenen Dateien."""
    if not path.exists():
        return "missing"
    items = []
    for p in path.rglob("*.json"):
        try:
            items.append((p.relative_to(path).as_posix(), p.stat().st_mtime_ns))
        except Exception:
            pass
    items.sort()
    h = hashlib.sha1()
    h.update(str(items).encode("utf-8"))
    return h.hexdigest()

def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".webp":
        return "image/webp"
    if ext == ".png":
        return "image/png"
    return "image/jpeg"

@st.cache_data(show_spinner=False)
def _data_url_cached(path_str: str, mtime_ns: int) -> Optional[str]:
    """
    Baut eine Base64-Data-URL *einmal* und cached sie.
    Cache-Key = (Pfad-String, mtime_ns) -> invalidiert automatisch bei Dateiänderung.
    """
    p = Path(path_str)
    try:
        raw  = p.read_bytes()
        mime = _guess_mime(p)
        b64  = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None

def team_logo_dataurl(team: str, size: int = 24, scale: int = 2) -> Optional[str]:
    thumb = get_logo_thumb_path(team, size, scale)  # <— scale weiterreichen
    if not thumb:
        return None
    p = Path(thumb)
    try:
        return _data_url_cached(p.as_posix(), p.stat().st_mtime_ns)
    except Exception:
        return None

# ============================================================
# Simulator-Backend
# ============================================================
# Wichtig: Das Modul stellt bereit:
# - step_regular_season_once()
# - step_playoffs_round_once()  [Bo7-Fortschritt pro Runde]
# - simulate_full_playoffs_and_advance()
# - run_simulation(max_seasons=..., interactive=False)
# - read_tables_for_ui()
# - load_state()
import LigageneratorV2 as sim

# ============================================================
# Sidebar – Steuerung
# ============================================================
with st.sidebar:
    st.title("🏒 Liga-Simulator")
    st.caption("HIGHspeed · NOVADELTA")

    # --- Regular Season: ein Spieltag ---
    if st.button("▶️ Nächsten Spieltag simulieren", key="btn_spieltag", use_container_width=True):
        try:
            res = sim.step_regular_season_once()
        except Exception as e:
            st.error(f"Fehler beim Simulieren des Spieltags: {e}")
        else:
            status = res.get("status")
            if status == "ok":
                st.toast(f"Spieltag {res['spieltag']-1} simuliert → Jetzt {res['spieltag']}", icon="✅")
                st.cache_data.clear()
                st.rerun()
            elif status == "season_over":
                st.toast("Regular Season ist beendet. Starte die Playoffs 👇", icon="⚠️")
            else:
                st.toast(f"Konnte Spieltag nicht simulieren (Status: {status}).", icon="❌")

    # --- Playoffs: eine Runde Bo7 ---
    if st.button("🏒 Nächste Playoff-Runde (Bo7) simulieren", key="btn_po_round", use_container_width=True):
        try:
            res = sim.step_playoffs_round_once()
        except Exception as e:
            st.error(f"Fehler beim Simulieren der Playoff-Runde: {e}")
        else:
            status = res.get("status")
            if status == "ok":
                st.toast(f"Playoff-Runde {res['round']} simuliert. Sieger: {', '.join(res['winners'])}", icon="✅")
                st.cache_data.clear()
                st.rerun()
            elif status == "champion":
                st.toast(
                    f"🏆 Champion (Saison {sim.load_state()['season']-1}): {res['champion']} • Nächste Saison: {res['next_season']}",
                    icon="🏆",
                )
                st.cache_data.clear()
                st.rerun()
            elif status == "regular_not_finished":
                st.toast("Regular Season noch nicht fertig – simuliere erst Spieltage.", icon="⚠️")
            else:
                st.toast(f"Playoff-Step nicht möglich: {status}", icon="❌")

    # --- Playoffs komplett + Saisonabschluss ---
    if st.button("🏆 Playoffs simulieren & Saison abschließen", key="btn_po_full", use_container_width=True):
        try:
            res = sim.simulate_full_playoffs_and_advance()
        except Exception as e:
            st.error(f"Fehler beim Playoffs-Durchlauf: {e}")
        else:
            if res.get("status") == "ok":
                st.toast(f"Champion: {res['champion']} · Nächste Saison: {res['next_season']}", icon="🏆")
                st.cache_data.clear()
                st.rerun()
            else:
                st.toast("Playoffs nicht gestartet – fehlt State?", icon="❌")

    # --- Komplette Saison in einem Rutsch ---
    if st.button("⏭️ Ganze Saison in einem Rutsch", key="btn_full_season", use_container_width=True):
        try:
            sim.run_simulation(max_seasons=1, interactive=False)
        except Exception as e:
            st.error(f"Fehler beim Komplett-Simulationslauf: {e}")
        else:
            st.toast("Komplette Saison (inkl. Playoffs) simuliert.", icon="⚡")
            st.cache_data.clear()
            st.rerun()

        # --- Pipeline aktualisieren (mit Emojis, UTF-8 sicher) ---
    if st.button("🛠 Pipeline aktualisieren", key="btn_pipeline", use_container_width=True):
        with st.spinner("Pipeline läuft..."):
            try:
                env = os.environ.copy()
                # Subprozess-Output erzwingen auf UTF-8
                env["PYTHONIOENCODING"] = "utf-8"

                result = subprocess.run(
                    [sys.executable, str(BASE_DIR / "run_pipeline.py")],
                    cwd=str(BASE_DIR),
                    capture_output=True,
                    text=False,          # <-- WICHTIG: keine Auto-Dekodierung
                    env=env,
                )

                # Manuell mit UTF-8 dekodieren (fehlerrobust)
                stdout = (result.stdout or b"").decode("utf-8", errors="replace")
                stderr = (result.stderr or b"").decode("utf-8", errors="replace")

            except Exception as e:
                st.toast("Pipeline konnte nicht gestartet werden.", icon="❌")
                st.error(f"Fehler beim Starten von run_pipeline.py: {e}")
            else:
                if result.returncode == 0:
                    st.toast("Pipeline erfolgreich durchgelaufen.", icon="✅")
                    # optional: stdout anzeigen, wenn du willst
                    # st.text(stdout)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.toast(f"Pipeline fehlgeschlagen (Exit-Code {result.returncode}).", icon="❌")
                    st.error(
                        "STDOUT:\n"
                        + stdout
                        + "\n\nSTDERR:\n"
                        + stderr
                    )


    # --- Cache neu laden ---
    if st.button("🔄 Daten neu laden (Cache leeren)", key="btn_reload", use_container_width=True):
        st.cache_data.clear()
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

    # === Tabelle Nord (mit Logos) ===
    st.markdown("### 📊 Tabelle Nord")
    tn = pd.DataFrame(info["tables"]["tabelle_nord"]).copy()
    tn.insert(0, "Logo", tn["Team"].apply(lambda t: team_logo_dataurl(t, 24, 2)))
    tn.rename(columns={"Points": "P"}, inplace=True)

    st.dataframe(
        tn[["Logo","Team","P","GF","GA","GD"]],
        width="stretch",
        hide_index=True,
        column_config={
            "Logo": st.column_config.ImageColumn(" ", width="small"),
            "Team": st.column_config.TextColumn("Team"),
            "P":    st.column_config.NumberColumn("P"),
            "GF":   st.column_config.NumberColumn("GF"),
            "GA":   st.column_config.NumberColumn("GA"),
            "GD":   st.column_config.NumberColumn("GD"),
        }
    )

    # === Tabelle Süd (mit Logos) ===
    st.markdown("### 📊 Tabelle Süd")
    ts = pd.DataFrame(info["tables"]["tabelle_sued"]).copy()
    ts.insert(0, "Logo", ts["Team"].apply(lambda t: team_logo_dataurl(t, 24, 2)))
    ts.rename(columns={"Points": "P"}, inplace=True)

    st.dataframe(
        ts[["Logo","Team","P","GF","GA","GD"]],
        width="stretch",
        hide_index=True,
        column_config={
            "Logo": st.column_config.ImageColumn(" ", width="small"),
            "Team": st.column_config.TextColumn("Team"),
            "P":    st.column_config.NumberColumn("P"),
            "GF":   st.column_config.NumberColumn("GF"),
            "GA":   st.column_config.NumberColumn("GA"),
            "GD":   st.column_config.NumberColumn("GD"),
        }
    )

with col_r:
    # === Top-Scorer (mit Team-Logos, Nummer & Position) ===
    st.markdown("### ⭐ Top-Scorer (Top 20)")
    tops = pd.DataFrame(info["tables"]["top_scorer"]).copy().head(20)

    # Logo-Spalte
    tops.insert(0, "Logo", tops["Team"].apply(lambda t: team_logo_dataurl(t, 22, 2)))
    # Anzeigename
    tops["Spieler"] = tops["Player"] + " (" + tops["Team"] + ")"

    # Nummer & Position aus dem Backend
    # (Fallbacks, falls alte Datenstruktur ohne Spalten)
    if "Number" not in tops.columns:
        tops["Number"] = None
    if "PositionGroup" not in tops.columns:
        tops["PositionGroup"] = None

    tops.rename(columns={
        "Number": "#",
        "PositionGroup": "Pos"
    }, inplace=True)

    st.dataframe(
        tops[["Logo", "Spieler", "#", "Pos", "Goals", "Assists", "Points"]],
        width="stretch",
        hide_index=True,
        column_config={
            "Logo":    st.column_config.ImageColumn(" ", width="small"),
            "Spieler": st.column_config.TextColumn("Spieler"),
            "#":       st.column_config.NumberColumn("#"),
            "Pos":     st.column_config.TextColumn("Pos"),
            "Goals":   st.column_config.NumberColumn("G"),
            "Assists": st.column_config.NumberColumn("A"),
            "Points":  st.column_config.NumberColumn("P"),
        }
    )

st.divider()

# ============================================================
# Signaturen für Live-Reload (ändern sich bei neuen JSONs)
# ============================================================
SIG_SPIELTAGE = dir_signature(SPIELTAG_DIR)
SIG_PLAYOFFS  = dir_signature(PLAYOFF_DIR)

# ============================================================
# Spieltag-Browser (History & Download) — live
# ============================================================
@st.cache_data(show_spinner=False)
def list_spieltage_seasons(_sig: str) -> List[int]:
    if not SPIELTAG_DIR.exists():
        return []
    vals=[]
    for p in SPIELTAG_DIR.iterdir():
        if p.is_dir() and re.match(r"(?i)saison_\d+$", p.name):
            try:
                vals.append(int(p.name.split("_")[1]))
            except:
                pass
    return sorted(vals)

@st.cache_data(show_spinner=False)
def list_gamedays(season: int, _sig_season: str) -> List[int]:
    folder = SPIELTAG_DIR / f"saison_{season}"
    if not folder.exists():
        return []
    vals=[]
    for f in folder.iterdir():
        m = re.match(r"(?i)spieltag_(\d+).*\.json$", f.name)
        if f.is_file() and m:
            vals.append(int(m.group(1)))
    return sorted(set(vals))

@st.cache_data(show_spinner=False)
def load_gameday_json(season: int, gameday: int, _sig_season: str) -> Optional[dict]:
    folder = SPIELTAG_DIR / f"saison_{season}"
    if not folder.exists():
        return None
    candidates = [
        f for f in folder.iterdir()
        if f.is_file() and re.match(rf"(?i)spieltag_0*{gameday}\D*\.json$", f.name)
    ]
    if not candidates:
        return None
    f = sorted(candidates, key=lambda p: p.name.lower())[0]
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None

st.markdown("### 🧾 Spieltag-Browser (History & Download)")

# Session-State stabil halten
if "sel_season" not in st.session_state:
    st.session_state.sel_season = max(list_spieltage_seasons(SIG_SPIELTAGE) or [info["season"]])
if "sel_gameday" not in st.session_state:
    gds0 = list_gamedays(
        st.session_state.sel_season,
        dir_signature(SPIELTAG_DIR / f"saison_{st.session_state.sel_season}")
    )
    st.session_state.sel_gameday = (gds0[-1] if gds0 else 1)

cols = st.columns([1,2,1,1,1])
with cols[0]:
    seasons_avail = list_spieltage_seasons(SIG_SPIELTAGE)
    st.session_state.sel_season = st.selectbox(
        "Saison",
        options=seasons_avail or [info["season"]],
        index=(
            seasons_avail.index(st.session_state.sel_season)
            if seasons_avail and st.session_state.sel_season in seasons_avail
            else (len(seasons_avail)-1 if seasons_avail else 0)
        ),
        format_func=lambda s: f"Saison {s}",
        key="dd_season_browser"
    )
with cols[1]:
    sig_season = dir_signature(SPIELTAG_DIR / f"saison_{st.session_state.sel_season}")
    gds = list_gamedays(st.session_state.sel_season, sig_season)
    cprev, csel, cnext = st.columns([1,3,1])
    with cprev:
        if st.button("◀", key="gd_prev") and gds:
            cur = st.session_state.get("sel_gameday", gds[-1])
            idx = gds.index(cur) if cur in gds else len(gds)-1
            st.session_state.sel_gameday = gds[max(0, idx-1)]
    with csel:
        st.session_state.sel_gameday = st.selectbox(
            "Spieltag",
            options=gds or [1],
            index=(
                gds.index(st.session_state.sel_gameday)
                if gds and st.session_state.sel_gameday in gds
                else (len(gds)-1 if gds else 0)
            ),
            key="dd_gameday_browser"
        )
    with cnext:
        if st.button("▶", key="gd_next") and gds:
            cur = st.session_state.get("sel_gameday", gds[-1])
            idx = gds.index(cur) if cur in gds else len(gds)-1
            st.session_state.sel_gameday = gds[min(len(gds)-1, idx+1)]

gjson = load_gameday_json(
    st.session_state.sel_season,
    st.session_state.sel_gameday,
    dir_signature(SPIELTAG_DIR / f"saison_{st.session_state.sel_season}")
)
if not gjson:
    st.info("Für diese Auswahl existiert (noch) kein Spieltag.")
else:
    st.caption(f"Saison {gjson['saison']} · Spieltag {gjson['spieltag']} • {gjson['timestamp']}")
    res_all = pd.DataFrame(gjson.get("results", []))

    def _prep(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df["HomeLogo"] = df["home"].apply(lambda t: team_logo_dataurl(t, 22, 2))
        df["AwayLogo"] = df["away"].apply(lambda t: team_logo_dataurl(t, 22, 2))
        df["Score"] = df["g_home"].astype(str) + " : " + df["g_away"].astype(str)
        # OT/SO Tag
        def _tag(r: pd.Series) -> str:
            t = str(r.get("type","")).upper()
            if t in ("OT","SO"):
                return t
            if r.get("ot"):
                return "OT"
            if r.get("so"):
                return "SO"
            return ""
        df["Tag"] = df.apply(_tag, axis=1)
        return df

    nord = _prep(res_all[res_all["conference"]=="Nord"])
    sued  = _prep(res_all[res_all["conference"]=="Süd"])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Nord")
        st.dataframe(
            nord[["HomeLogo","home","AwayLogo","away","Score","Tag"]],
            width="stretch",
            hide_index=True,
            column_config={
                "HomeLogo": st.column_config.ImageColumn(" ", width="small"),
                "home":     st.column_config.TextColumn("Home"),
                "AwayLogo": st.column_config.ImageColumn(" ", width="small"),
                "away":     st.column_config.TextColumn("Away"),
                "Score":    st.column_config.TextColumn("Ergebnis", width="small"),
                "Tag":      st.column_config.TextColumn(" "),
            }
        )

    with c2:
        st.markdown("#### Süd")
        st.dataframe(
            sued[["HomeLogo","home","AwayLogo","away","Score","Tag"]],
            width="stretch",
            hide_index=True,
            column_config={
                "HomeLogo": st.column_config.ImageColumn(" ", width="small"),
                "home":     st.column_config.TextColumn("Home"),
                "AwayLogo": st.column_config.ImageColumn(" ", width="small"),
                "away":     st.column_config.TextColumn("Away"),
                "Score":    st.column_config.TextColumn("Ergebnis", width="small"),
                "Tag":      st.column_config.TextColumn(" "),
            }
        )

    # Downloads
    st.markdown("#### Download")
    st.download_button(
        "📦 JSON (Original)",
        data=json.dumps(gjson, ensure_ascii=False, indent=2),
        file_name=f"s{gjson['saison']:02}_spieltag_{gjson['spieltag']:02}.json",
        mime="application/json",
        width="stretch",
        key="dl_json_gd"
    )
    st.download_button(
        "🧾 CSV (Ergebnisse)",
        data=res_all.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"s{gjson['saison']:02}_spieltag_{gjson['spieltag']:02}.csv",
        mime="text/csv",
        width="stretch",
        key="dl_csv_gd"
    )

st.divider()

# ============================================================
# Playoff-Browser (History & Download) — robust, live
# ============================================================
@st.cache_data(show_spinner=False)
def list_playoff_seasons(_sig: str) -> List[int]:
    if not PLAYOFF_DIR.exists():
        return []
    vals=[]
    for p in PLAYOFF_DIR.iterdir():
        if p.is_dir() and re.match(r"(?i)saison_\d+$", p.name):
            try:
                vals.append(int(p.name.split("_")[1]))
            except:
                pass
    return sorted(vals)

@st.cache_data(show_spinner=False)
def list_rounds(season: int, _sig_season: str) -> List[int]:
    folder = PLAYOFF_DIR / f"saison_{season}"
    if not folder.exists():
        return []
    vals=[]
    for f in folder.iterdir():
        m = re.match(r"(?i)runde_(\d+).*\.json$", f.name)
        if f.is_file() and m:
            vals.append(int(m.group(1)))
    return sorted(set(vals))

@st.cache_data(show_spinner=False)
def load_round_json(season: int, rnd: int, _sig_season: str) -> Optional[dict]:
    folder = PLAYOFF_DIR / f"saison_{season}"
    if not folder.exists():
        return None
    candidates = [
        f for f in folder.iterdir()
        if f.is_file() and re.match(rf"(?i)runde_0*{rnd}\D*\.json$", f.name)
    ]
    if not candidates:
        return None
    f = sorted(candidates, key=lambda p: p.name.lower())[0]
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None

st.markdown("### 🏆 Playoff-Browser (History & Download)")
if "po_season" not in st.session_state:
    st.session_state.po_season = max(list_playoff_seasons(SIG_PLAYOFFS) or [info["season"]])
if "po_round" not in st.session_state:
    rs0 = list_rounds(
        st.session_state.po_season,
        dir_signature(PLAYOFF_DIR / f"saison_{st.session_state.po_season}")
    )
    st.session_state.po_round = (rs0[-1] if rs0 else 1)

pc1, pc2, _ = st.columns([2,3,1])
with pc1:
    pos = list_playoff_seasons(SIG_PLAYOFFS)
    st.session_state.po_season = st.selectbox(
        "Saison", options=pos or [info["season"]],
        index=(
            pos.index(st.session_state.po_season)
            if pos and st.session_state.po_season in pos
            else (len(pos)-1 if pos else 0)
        ),
        format_func=lambda s: f"Saison {s}", key="po_season_sel"
    )
with pc2:
    sig_po_season = dir_signature(PLAYOFF_DIR / f"saison_{st.session_state.po_season}")
    rs = list_rounds(st.session_state.po_season, sig_po_season)
    rprev, rsel, rnext = st.columns([1,3,1])
    with rprev:
        if st.button("◀", key="po_prev") and rs:
            cur = st.session_state.get("po_round", rs[-1])
            idx = rs.index(cur) if cur in rs else len(rs)-1
            st.session_state.po_round = rs[max(0, idx-1)]
    with rsel:
        st.session_state.po_round = st.selectbox(
            "Runde", options=rs or [1],
            index=(
                rs.index(st.session_state.po_round)
                if rs and st.session_state.po_round in rs
                else (len(rs)-1 if rs else 0)
            ),
            key="po_round_sel"
        )
    with rnext:
        if st.button("▶", key="po_next") and rs:
            cur = st.session_state.get("po_round", rs[-1])
            idx = rs.index(cur) if cur in rs else len(rs)-1
            st.session_state.po_round = rs[min(len(rs)-1, idx+1)]

po_json = load_round_json(
    st.session_state.po_season,
    st.session_state.po_round,
    dir_signature(PLAYOFF_DIR / f"saison_{st.session_state.po_season}")
) if list_playoff_seasons(SIG_PLAYOFFS) else None

def _render_series_block(round_json: dict):
    st.markdown(f"#### Playoff-Runde {round_json.get('runde')} (Saison {round_json.get('saison')})")

    # 1) NEUES Format: series[{a,b,result,winner,games:[{g,home,away,g_home,g_away}]}]
    if "series" in round_json and isinstance(round_json["series"], list) and round_json["series"]:
        for s in round_json["series"]:
            a = s.get("a",""); b = s.get("b","")
            result = s.get("result",""); winner = s.get("winner","")
            with st.expander(f"{a} vs {b} — Ergebnis: {result}  •  Sieger: {winner}", expanded=True):
                rows = []
                for g in s.get("games", []):
                    rows.append({
                        "Spiel": g.get("g"),
                        "Home": g.get("home"),
                        "Away": g.get("away"),
                        "Score": f"{g.get('g_home',0)} : {g.get('g_away',0)}",
                    })
                df = pd.DataFrame(rows)
                c1, c2, c3 = st.columns([1,1,1])
                with c1:
                    p1 = get_logo_thumb_path(a, 96, 2)  # rendert 192px, Anzeige bleibt 96 → scharf
                    if p1:
                        # zentriert + feste Breite (Höhe folgt dem Seitenverhältnis)
                        st.markdown('<div style="text-align:center">', unsafe_allow_html=True)
                        st.image(p1, width=96)
                        st.caption(a, help=None)
                        st.markdown('</div>', unsafe_allow_html=True)

                with c3:
                    p2 = get_logo_thumb_path(b, 96, 2)
                    if p2:
                        st.markdown('<div style="text-align:center">', unsafe_allow_html=True)
                        st.image(p2, width=96)
                        st.caption(b, help=None)
                        st.markdown('</div>', unsafe_allow_html=True)

                if not df.empty:
                    st.dataframe(df, width="stretch", hide_index=True)
                else:
                    st.write("Keine Einzelspiele gespeichert.")
        return

    # 2) ALTES String-Format: "spiele": ["TeamA 3:2 TeamB", ...]
    if "spiele" in round_json and isinstance(round_json["spiele"], list) and round_json["spiele"]:
        parsed = []
        for s in round_json["spiele"]:
            line = str(s).strip()
            m = re.match(r"(.+?)\s+(\d+)\s*:\s*(\d+)\s+(.+)$", line)
            if m:
                home, gh, ga, away = m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4).strip()
                parsed.append({
                    "HomeLogo": get_logo_thumb_path(home, 24),
                    "Home": home,
                    "AwayLogo": get_logo_thumb_path(away, 24),
                    "Away": away,
                    "Score": f"{gh} : {ga}",
                })
            else:
                parsed.append({"Home": line, "Away": "", "Score": ""})
        df = pd.DataFrame(parsed)
        st.dataframe(
            df[["HomeLogo","Home","AwayLogo","Away","Score"]],
            width="stretch",
            hide_index=True,
            column_config={
                "HomeLogo": st.column_config.ImageColumn(" ", width="small"),
                "Home": st.column_config.TextColumn("Home"),
                "AwayLogo": st.column_config.ImageColumn(" ", width="small"),
                "Away": st.column_config.TextColumn("Away"),
                "Score": st.column_config.TextColumn("Ergebnis", width="small"),
            }
        )
        return

    # 3) Objekt-Format: "results":[{"home","away","g_home","g_away"}]
    if "results" in round_json and isinstance(round_json["results"], list) and round_json["results"]:
        rows = []
        for r in round_json["results"]:
            home, away = r.get("home",""), r.get("away","")
            gh, ga = r.get("g_home",0), r.get("g_away",0)
            rows.append({
                "HomeLogo": get_logo_thumb_path(home, 24),
                "Home": home,
                "AwayLogo": get_logo_thumb_path(away, 24),
                "Away": away,
                "Score": f"{gh} : {ga}",
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df[["HomeLogo","Home","AwayLogo","Away","Score"]],
            width="stretch",
            hide_index=True,
            column_config={
                "HomeLogo": st.column_config.ImageColumn(" ", width="small"),
                "Home": st.column_config.TextColumn("Home"),
                "AwayLogo": st.column_config.ImageColumn(" ", width="small"),
                "Away": st.column_config.TextColumn("Away"),
                "Score": st.column_config.TextColumn("Ergebnis", width="small"),
            }
        )
        return

    st.info("Diese Playoff-JSON enthält weder 'series' noch 'spiele' noch 'results' – Format unbekannt.")

if po_json:
    _render_series_block(po_json)
    st.markdown("#### Download")
    st.download_button(
        "📦 JSON (Playoff-Runde)",
        data=json.dumps(po_json, ensure_ascii=False, indent=2),
        file_name=f"s{po_json['saison']:02}_runde_{po_json['runde']:02}.json",
        mime="application/json",
        width="stretch",
        key="dl_json_po"
    )
    # Für Serienformat zusätzlich CSV der Einzelspiele
    rows=[]
    if po_json.get("series"):
        for s in po_json.get("series", []):
            for g in s.get("games", []):
                rows.append({
                    "Serie_A": s.get("a",""), "Serie_B": s.get("b",""),
                    "Result": s.get("result",""), "Winner": s.get("winner",""),
                    "Game": g.get("g"), "Home": g.get("home"),
                    "Away": g.get("away"), "G_Home": g.get("g_home",0),
                    "G_Away": g.get("g_away",0)
                })
    if rows:
        df_po = pd.DataFrame(rows)
        st.download_button(
            "🧾 CSV (Playoff-Runde, Spiele)",
            data=df_po.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"s{po_json['saison']:02}_runde_{po_json['runde']:02}.csv",
            mime="text/csv",
            width="stretch",
            key="dl_csv_po"
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
    st.dataframe(hdf, width="stretch", hide_index=True)
else:
    st.info("Noch keine abgeschlossene Saison – simuliere bis zum Champion.")
