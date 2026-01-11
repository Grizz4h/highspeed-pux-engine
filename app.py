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
import urllib.request

from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import streamlit as st
from PIL import Image

import pandas as pd
import streamlit as st
from PIL import Image

DATA_REPO_PATH = Path("/opt/highspeed/data")
PUBLISHER_DIR  = Path("/opt/highspeed/publisher")
SCRIPT_PULL    = PUBLISHER_DIR / "data_pull.sh"
SCRIPT_PUSH    = PUBLISHER_DIR / "data_push.sh"
SCRIPT_REPLAY_PUSH = PUBLISHER_DIR / "replay_push.sh"
SCRIPT_PUBLISH = PUBLISHER_DIR / "publish_live.sh"  # optional, falls vorhanden

# Neues Pointer-Repo für saubere Trennung
POINTERS_REPO_PATH = Path("/opt/highspeed/data_pointers")

SERVER_MODE = (
    os.name != "nt"
    and Path("/opt/highspeed").exists()
    and PUBLISHER_DIR.exists()
)

# ---- Mode / Guards ----
HIGHSPEED_MODE = (os.environ.get("HIGHSPEED_MODE") or "").strip().lower()
DATA_ROOT_ENV = os.environ.get("HIGHSPEED_DATA_ROOT")

def is_sandbox_mode() -> bool:
    return HIGHSPEED_MODE == "sandbox"

def is_ssot_root() -> bool:
    # Wenn du auf dem Pi bist, ist das die "echte" SSOT
    # (resolve, um Symlinks/relative Pfade zu normalisieren)
    try:
        return Path(DATA_ROOT_ENV or "").resolve() == Path("/opt/highspeed/data").resolve()
    except Exception:
        return False

def mode_badge() -> str:
    if is_sandbox_mode():
        return "🧪 SANDBOX"
    if is_ssot_root():
        return "🚀 LIVE/SSOT"
    return "⚙️ CUSTOM"

# Fatal Guard: Sandbox darf nicht auf SSOT zeigen
if is_sandbox_mode() and is_ssot_root():
    st.error("FATAL: SANDBOX mode but DATA_ROOT points to SSOT. Fix systemd env.", icon="🛑")
    st.stop()

# Setze den Port für die Sandbox auf 9502
if is_sandbox_mode():
    st.set_page_config(page_title="PUX Liga Simulator (Sandbox)")
else:
    st.set_page_config(page_title="PUX Liga Simulator")



# ============================================================
# Pfade & Basiskonfig
# ============================================================
# APP_DIR = Repository-Root der Engine (für Assets/Tools, die NICHT ins Data-Repo gehören)
APP_DIR = Path(__file__).parent.resolve()

# DATA_DIR = Single Source of Truth für dynamische Outputs (Spieltage, Saves, Stats, Replays, Playoffs, Schedules, ...)
# Wenn HIGHSPEED_DATA_ROOT gesetzt ist, nutzen wir das (z.B. C:\Webseite\highspeed-pux-data).
# Wenn nicht gesetzt, fällt es auf APP_DIR zurück (altes Verhalten).
DATA_DIR = Path(os.environ.get("HIGHSPEED_DATA_ROOT", str(APP_DIR))).resolve()

# Dynamische Daten (kommen aus dem Data-Repo)
SPIELTAG_DIR = DATA_DIR / "spieltage"
PLAYOFF_DIR  = DATA_DIR / "playoffs"

# Statische Assets bleiben im Engine-Repo (nicht im Data-Repo!)
LOGO_DIR  = APP_DIR / "assets" / "logos" / "teams"
THUMB_DIR = APP_DIR / ".cache_thumbs"
THUMB_DIR.mkdir(exist_ok=True)

SAVEGAME_PATH = DATA_DIR / "saves" / "savegame.json"

# ============================================================
# Utils
# ============================================================
def season_folder(season: int) -> str:
    return f"saison_{int(season):02d}"


def spieltag_index(value) -> int:
    """
    Extrahiert eine Zahl aus Spieltag-IDs wie:
    - 12
    - "12"
    - "Playoff_Runde_1"
    - "Spieltag_03"
    Fallback: 0
    """
    m = re.search(r"(\d+)", str(value))
    return int(m.group(1)) if m else 0

def spielplan_path(season: int) -> Path:
    # Spielplan liegt bei den dynamischen Daten (Data-Repo)
    return DATA_DIR / "schedules" / season_folder(season) / "spielplan.json"


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
    - scale:  Render-Faktor (2 = Hi-DPI)
    """
    src = _logo_file_for_team(team)
    if not src or src.suffix.lower() == ".svg":
        return None

    slug = _slugify(str(team))
    px   = size * max(1, int(scale))
    out  = THUMB_DIR / f"{slug}_{size}x{scale}.webp"

    try:
        if (not out.exists()) or (out.stat().st_mtime < src.stat().st_mtime):
            im = Image.open(src).convert("RGBA")
            im.thumbnail((px, px), Image.LANCZOS)

            canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
            x = (px - im.width) // 2
            y = (px - im.height) // 2
            canvas.paste(im, (x, y), im)

            canvas.save(out, "WEBP", quality=88, method=6)
        return out.as_posix()
    except Exception:
        return None

def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".webp":
        return "image/webp"
    if ext == ".png":
        return "image/png"
    return "image/jpeg"

@st.cache_data(show_spinner=False)
def _data_url_cached(path_str: str, mtime_ns: int) -> Optional[str]:
    p = Path(path_str)
    try:
        raw  = p.read_bytes()
        mime = _guess_mime(p)
        b64  = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None

def team_logo_dataurl(team: str, size: int = 24, scale: int = 2) -> Optional[str]:
    thumb = get_logo_thumb_path(team, size, scale)
    if not thumb:
        return None
    p = Path(thumb)
    try:
        return _data_url_cached(p.as_posix(), p.stat().st_mtime_ns)
    except Exception:
        return None

def dir_signature(path: Path) -> str:
    """Hash über Dateinamen + mtime_ns aller JSONs im Ordner (rekursiv)."""
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

@st.cache_data(show_spinner=False)
def load_spielplan(path: Path) -> Optional[dict]:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def list_seasons_from_data_root(_sig_a: str, _sig_b: str) -> List[int]:
    """Seasons aus spieltage/ und playoffs/ zusammenführen."""
    seasons = set()

    if SPIELTAG_DIR.exists():
        for p in SPIELTAG_DIR.iterdir():
            if p.is_dir() and re.match(r"(?i)saison_\d+$", p.name):
                try:
                    seasons.add(int(p.name.split("_")[1]))
                except Exception:
                    pass

    if PLAYOFF_DIR.exists():
        for p in PLAYOFF_DIR.iterdir():
            if p.is_dir() and re.match(r"(?i)saison_\d+$", p.name):
                try:
                    seasons.add(int(p.name.split("_")[1]))
                except Exception:
                    pass

    return sorted(seasons)

def ui_current_matchday(raw_spieltag: int | str | None) -> int:
    """
    Engine liefert oft den 'next pointer' (0-basiert / next matchday).
    UI soll den zuletzt simulierten Spieltag anzeigen.

    Regel: UI = max(0, raw - 1)
    Beispiele:
      raw=0 -> UI=0 (noch nichts simuliert)
      raw=1 -> UI=0
      raw=4 -> UI=3 (du hast den 3. simuliert)
      raw=5 -> UI=4 (du hast den 4. simuliert)
    """
    try:
        n = int(raw_spieltag) if raw_spieltag is not None else 0
    except Exception:
        n = 0
    return max(0, n - 1)


# ============================================================
# Simulator-Backend
# ============================================================
import LigageneratorV2 as sim


# ============================================================
# Session defaults
# ============================================================
if "pipeline_status" not in st.session_state:
    st.session_state.pipeline_status = None  # "ok" | "error"
    st.session_state.pipeline_stdout = ""
    st.session_state.pipeline_stderr = ""

if "names_status" not in st.session_state:
    st.session_state.names_status = None  # "ok" | "error"
    st.session_state.names_stdout = ""
    st.session_state.names_stderr = ""

if "migrate_status" not in st.session_state:
    st.session_state.migrate_status = None  # "ok" | "error"
    st.session_state.migrate_stdout = ""
    st.session_state.migrate_stderr = ""

if "browser_season" not in st.session_state:
    st.session_state.browser_season = None

def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()
# ============================================================
# Sidebar – Steuerung
# ============================================================
with st.sidebar:
    st.title("🏒 HIGHspeeΔ PUX! Engine")
    st.caption("HIGHspeed · NOVADELTA")

    badge = mode_badge()
    st.caption(f"Mode: **{badge}**")

    if is_sandbox_mode():
        st.warning(
            "SANDBOX-Modus aktiv: Git/Publish/Pointer sind **deaktiviert**.\n"
            "Du kannst hier sicher simulieren, ohne SSOT zu berühren.",
            icon="🧪",
        )
    elif is_ssot_root():
        st.info(
            "LIVE/SSOT aktiv: Änderungen wirken auf echte Daten.\n"
            "Publish/Reset nur mit Bestätigung.",
            icon="🚀",
        )

    with st.expander("📌 Pfade (Debug)", expanded=False):
        st.code(f"APP_DIR  = {APP_DIR}\nDATA_DIR = {DATA_DIR}\nSAVE    = {SAVEGAME_PATH}")

        if not os.environ.get("HIGHSPEED_DATA_ROOT"):
            st.warning("HIGHSPEED_DATA_ROOT ist NICHT gesetzt → DATA_DIR fällt auf APP_DIR zurück.")

    # --- SIM BUTTONS (arbeiten immer gegen den aktuellen Save-State) ---
    st.markdown("### Simulation (aktive Saison)")

    if st.button(
        "▶️ Nächsten Spieltag simulieren",
        key="btn_spieltag",
        use_container_width=True
    ):
        try:
            res = sim.step_regular_season_once()
        except Exception as e:
            st.error(f"Fehler beim Simulieren des Spieltags: {e}")
        else:
            status = res.get("status")

            # "letzter simulierter" Spieltag für UI / Commit
            try:
                raw_md = int(sim.load_state().get("spieltag", 0) or 0)  # next pointer
            except Exception:
                raw_md = 0
            last_simulated = max(1, raw_md - 1)  # MD01.., nie 0 in commits

            if status == "ok":
                # Immer nach dev pushen
                msg = f"MD{last_simulated:02d} simulated"
                if os.name != "nt" and SCRIPT_PUSH.exists():
                    code, out = _run([str(SCRIPT_PUSH), "dev", msg])
                    if code == 0:
                        st.toast(f"🚀 {msg} → DEV gepusht", icon="✅")
                    else:
                        st.error("Auto-Push nach DEV fehlgeschlagen")
                    if out:
                        st.code(out)
                else:
                    st.warning("data_push.sh fehlt oder lokaler Run → kein Auto-Push möglich.", icon="⚠️")

                st.cache_data.clear()
                st.rerun()

            elif status == "season_over":
                st.toast("Regular Season ist beendet. Starte die Playoffs 👇", icon="⚠️")

            else:
                st.toast(f"Konnte Spieltag nicht simulieren (Status: {status}).", icon="❌")
 

    if is_sandbox_mode():
        st.markdown("### 🗑️ Reset Sandbox")
        if st.button(
            "🗑️ Alle Daten löschen & neu starten",
            key="btn_reset",
            use_container_width=True
        ):
            import shutil
            if DATA_DIR.exists():
                shutil.rmtree(DATA_DIR)
                st.success(f"🗑️ Gelöscht: {DATA_DIR}")
            st.success("✅ Sandbox zurückgesetzt! Seite neu laden.")
            st.cache_data.clear()
            st.rerun()


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

    if st.button("⏭️ Ganze Saison in einem Rutsch", key="btn_full_season", use_container_width=True):
        try:
            sim.run_simulation(max_seasons=1, interactive=False)
        except Exception as e:
            st.error(f"Fehler beim Komplett-Simulationslauf: {e}")
        else:
            st.toast("Komplette Saison (inkl. Playoffs) simuliert.", icon="⚡")
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # --- Browser Season (UI only) ---
    st.markdown("### Browser (UI-Saison)")
    sig_a = dir_signature(SPIELTAG_DIR)
    sig_b = dir_signature(PLAYOFF_DIR)
    seasons_avail = list_seasons_from_data_root(sig_a, sig_b)

    # Fallback: wenn gar nichts da, nimm die aktuelle Engine-Season aus dem State
    try:
        cur_state = sim.load_state()
        cur_season = int(cur_state.get("season", 1) or 1)
    except Exception:
        cur_season = 1

    if st.session_state.browser_season is None:
        st.session_state.browser_season = (seasons_avail[-1] if seasons_avail else cur_season)

    st.session_state.browser_season = st.selectbox(
        "Saison anzeigen",
        options=seasons_avail or [cur_season],
        index=((seasons_avail.index(st.session_state.browser_season)) if (seasons_avail and st.session_state.browser_season in seasons_avail) else 0),
        format_func=lambda s: f"Saison {s}",
        key="sb_browser_season"
    )

    st.divider()

    # --- Pipeline ---
    st.markdown("### Tools")
    if st.button("🛠 Pipeline aktualisieren", key="btn_pipeline", use_container_width=True):
        with st.spinner("Pipeline läuft..."):
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"

                result = subprocess.run(
                    [sys.executable, str(APP_DIR / "run_pipeline.py")],
                    cwd=str(APP_DIR),
                    capture_output=True,
                    text=False,
                    env=env,
                )

                stdout = (result.stdout or b"").decode("utf-8", errors="replace")
                stderr = (result.stderr or b"").decode("utf-8", errors="replace")

                st.session_state.pipeline_stdout = stdout
                st.session_state.pipeline_stderr = stderr

                if result.returncode == 0:
                    st.session_state.pipeline_status = "ok"
                    st.cache_data.clear()
                else:
                    st.session_state.pipeline_status = "error"

            except Exception as e:
                st.session_state.pipeline_status = "error"
                st.session_state.pipeline_stderr = str(e)

    if st.button("🔄 Daten neu laden (Cache leeren)", key="btn_reload", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if st.button("👤 Spieler-Namen aktualisieren", key="btn_update_names", use_container_width=True):
        with st.spinner("Spieler-Namen werden aktualisiert..."):
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"

                result = subprocess.run(
                    [sys.executable, str(APP_DIR / "update_player_names.py")],
                    cwd=str(APP_DIR),
                    capture_output=True,
                    text=False,
                    env=env,
                )

                stdout = (result.stdout or b"").decode("utf-8", errors="replace")
                stderr = (result.stderr or b"").decode("utf-8", errors="replace")

                st.session_state.names_stdout = stdout
                st.session_state.names_stderr = stderr

                if result.returncode == 0:
                    st.session_state.names_status = "ok"
                    st.cache_data.clear()
                else:
                    st.session_state.names_status = "error"

            except Exception as e:
                st.session_state.names_status = "error"
                st.session_state.names_stderr = str(e)

    if st.button("🔄 Stats migrieren (player_id)", key="btn_migrate_stats", use_container_width=True):
        with st.spinner("Stats werden migriert..."):
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"

                result = subprocess.run(
                    [sys.executable, str(APP_DIR / "migrate_stats.py")],
                    cwd=str(APP_DIR),
                    capture_output=True,
                    text=False,
                    env=env,
                )

                stdout = (result.stdout or b"").decode("utf-8", errors="replace")
                stderr = (result.stderr or b"").decode("utf-8", errors="replace")

                st.session_state.migrate_stdout = stdout
                st.session_state.migrate_stderr = stderr

                if result.returncode == 0:
                    st.session_state.migrate_status = "ok"
                    st.cache_data.clear()
                else:
                    st.session_state.migrate_status = "error"

            except Exception as e:
                st.session_state.migrate_status = "error"
                st.session_state.migrate_stderr = str(e)

    # --- Reset Save ---
    st.markdown("### Danger Zone")
    if st.button("🧨 Reset Savegame (löscht saves/savegame.json)", key="btn_reset_save", use_container_width=True):
        try:
            if SAVEGAME_PATH.exists():
                SAVEGAME_PATH.unlink()
                st.toast("Savegame gelöscht. Engine startet beim nächsten Run neu.", icon="🧨")
            else:
                st.toast("Kein Savegame gefunden (nichts zu löschen).", icon="⚠️")
        except Exception as e:
            st.error(f"Konnte Savegame nicht löschen: {e}")
        st.cache_data.clear()
        st.rerun()


# Pipeline-Status Anzeige (unter Sidebar-Buttons, aber im Main ok sichtbar)
if st.session_state.pipeline_status == "ok":
    st.success("✅ Pipeline erfolgreich durchgelaufen.")
elif st.session_state.pipeline_status == "error":
    st.error("❌ Pipeline fehlgeschlagen.")
    with st.expander("🔍 Details anzeigen"):
        if st.session_state.pipeline_stdout:
            st.markdown("**STDOUT**")
            st.code(st.session_state.pipeline_stdout)
        if st.session_state.pipeline_stderr:
            st.markdown("**STDERR**")
            st.code(st.session_state.pipeline_stderr)

if st.session_state.names_status == "ok":
    st.success("✅ Spieler-Namen erfolgreich aktualisiert.")
elif st.session_state.names_status == "error":
    st.error("❌ Spieler-Namen-Update fehlgeschlagen.")
    with st.expander("🔍 Details anzeigen"):
        if st.session_state.names_stdout:
            st.markdown("**STDOUT**")
            st.code(st.session_state.names_stdout)
        if st.session_state.names_stderr:
            st.markdown("**STDERR**")
            st.code(st.session_state.names_stderr)

if st.session_state.migrate_status == "ok":
    st.success("✅ Stats erfolgreich migriert.")
elif st.session_state.migrate_status == "error":
    st.error("❌ Stats-Migration fehlgeschlagen.")
    with st.expander("🔍 Details anzeigen"):
        if st.session_state.migrate_stdout:
            st.markdown("**STDOUT**")
            st.code(st.session_state.migrate_stdout)
        if st.session_state.migrate_stderr:
            st.markdown("**STDERR**")
            st.code(st.session_state.migrate_stderr)

# ============================================================
# Data Repo Controls (SSOT) — safe, explicit, self-explaining
# ============================================================

def _run_in(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()

def data_git(*args: str) -> tuple[int, str]:
    return _run_in(["git", *args], DATA_REPO_PATH)

def pointers_git(*args: str) -> tuple[int, str]:
    return _run_in(["git", *args], POINTERS_REPO_PATH)


def list_data_commits(limit: int = 30) -> tuple[int, list[dict[str, str]] | str]:
    """Liest die letzten Commits aus dem DATA-Repo für Rollback-Auswahl."""
    code, out = data_git("--no-pager", "log", "--oneline", f"-n{limit}")
    if code != 0:
        return code, out

    commits: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = line.strip().split(maxsplit=1)
        if not parts:
            continue
        sha = parts[0]
        subj = parts[1] if len(parts) > 1 else "(kein Betreff)"
        commits.append({"sha": sha, "subj": subj})

    return 0, commits


# --- Rollback Daten-Repo auf Commit ---
st.markdown("### Rollback Daten (Spieltage/Saves)")
code_commits, commits = list_data_commits(limit=40)
if code_commits != 0:
    st.warning(f"Konnte Commits nicht laden: {commits}")
elif not commits:
    st.info("Keine Commits gefunden.")
else:
    options = [f"{c['sha'][:10]} · {c['subj']}" for c in commits]
    sel = st.selectbox("Commit auswählen", options=options, key="sb_rollback_commit")
    chosen = commits[options.index(sel)]

    confirm_rb = st.checkbox(
        "Ja, Daten-Repo (spieltage/saves/etc.) hart auf diesen Commit zurücksetzen.",
        value=False,
        key="cb_confirm_rb"
    )

    force_push_rb = st.checkbox(
        "⚠️ Force-Push nach Rollback (überschreibt Remote-History, alte Commits werden gelöscht)",
        value=False,
        key="cb_force_push_rb"
    )

    if force_push_rb:
        st.warning("⚠️ WICHTIG: Nach Force-Push müssen alle Pointer (dev/prod/replay) neu gesetzt werden, da alte Commits nicht mehr existieren!")

    st.session_state.rollback_chosen = chosen if st.button("⏪ Rollback auf Commit", key="btn_rollback", use_container_width=True, disabled=not confirm_rb) else st.session_state.get("rollback_chosen")
    st.session_state.rollback_force_push = force_push_rb if st.session_state.get("rollback_chosen") else False


def _trigger_workflow_dispatch(repo_owner: str, repo_name: str, event_type: str, token: str) -> tuple[int, str]:
    """
    Triggert einen repository_dispatch Event im angegebenen Repo.
    """
    if not token:
        return 1, "ERROR: No token provided for dispatch"
    
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/dispatches"
    payload = json.dumps({"event_type": event_type}).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 204:
                return 0, f"Dispatch {event_type} triggered successfully"
            else:
                return response.status, f"Unexpected response: {response.status}"
    except urllib.error.HTTPError as e:
        return e.code, f"HTTP Error: {e.reason}"
    except Exception as e:
        return 1, f"ERROR: {str(e)}"


def set_pointer(which: str, source_branch: str, full_sha: str) -> tuple[int, str]:
    """
    Setzt Pointer in pointers/dev.json, pointers/prod.json oder pointers/replay.json auf den gegebenen commit.
    Arbeitet nur im Pointers-Repo, ohne Engine-Repo zu berühren.
    Nach erfolgreichem Push wird ein repository_dispatch Event gefeuert (für replay Pointer).
    """
    if DATA_REPO_PATH.resolve() == POINTERS_REPO_PATH.resolve():
        return 1, "ERROR: Pointer repo darf nicht data repo sein. Konfiguration prüfen!"
    
    if which not in ("dev", "prod", "replay"):
        return 1, f"Invalid which: {which}"
    if len(full_sha) != 40 or not all(c in "0123456789abcdef" for c in full_sha):
        return 1, f"Invalid full SHA: {full_sha}"

    import datetime
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    pointer_data = {
        "source_branch": source_branch,
        "source_commit": full_sha,
        "updated_at": timestamp
    }

    steps = [
        (["git", "fetch", "origin"], "fetch origin"),
        (["git", "checkout", "pointers"], "checkout pointers"),
        (["git", "reset", "--hard", "origin/pointers"], "reset pointers -> origin/pointers"),
        (["sh", "-c", f"mkdir -p pointers && echo '{json.dumps(pointer_data, indent=2)}' > pointers/{which}.json"], f"write pointers/{which}.json"),
        (["git", "add", f"pointers/{which}.json"], f"add pointers/{which}.json"),
        (["git", "commit", "-m", f"chore(pointer): set {which} -> {full_sha[:10]} ({source_branch})"], f"commit pointer {which}"),
        (["git", "push", "origin", "pointers"], f"push pointers"),
    ]

    out_all = []
    for cmd, label in steps:
        code, out = _run_in(cmd, POINTERS_REPO_PATH)
        out_all.append(f"$ {' '.join(cmd)}\n{out}".strip())
        if code != 0:
            return code, "\n\n".join(out_all) + f"\n\n[FAIL] step: {label}"
    
    # After successful push, trigger dispatch for replay pointer
    result_msg = f"[OK] {which.upper()} pointer set to {full_sha[:10]}"
    if which == "replay":
        token = os.environ.get("HIGHSPEED_PAT", "")
        dispatch_code, dispatch_msg = _trigger_workflow_dispatch(
            "Grizz4h",
            "highspeed-pux-data",
            "replay-pointer-updated",
            token
        )
        out_all.append(f"\n[Dispatch] {dispatch_msg} (code={dispatch_code})")
        if dispatch_code != 0:
            result_msg += f" [Dispatch FAILED: {dispatch_msg}]"
        else:
            result_msg += f" [Dispatch sent ✓]"
    
    return 0, "\n\n".join(out_all) + f"\n\n{result_msg}"

    

def get_repo_status(branch: str) -> dict:
    if not DATA_REPO_PATH.exists():
        return {"ok": False, "err": "Data repo path not found."}
    data_git("fetch", "origin")
    code_b, b = data_git("rev-parse", "--abbrev-ref", "HEAD")
    code_h, h = data_git("rev-parse", "--short", "HEAD")
    code_m, msg = data_git("log", "-1", "--pretty=%s")
    # remote head of branch
    code_r, rh = data_git("rev-parse", "--short", f"origin/{branch}")
    return {
        "ok": True,
        "branch": b if code_b == 0 else "?",
        "head": h if code_h == 0 else "?",
        "last_msg": msg if code_m == 0 else "",
        "remote_head": rh if code_r == 0 else "?",
    }

@st.cache_data(show_spinner=False)
def list_dev_md_commits(limit: int = 50) -> list[dict]:
    """
    Liefert DEV Commits mit 'MDxx' im Commit-Subject, neueste zuerst.
    """
    if not DATA_REPO_PATH.exists():
        return []
    data_git("fetch", "origin")
    # Nur subjects + hash, dann filtern
    code, out = _run_in(
        ["git", "log", "origin/dev", f"-n{limit}", "--pretty=%H|%B%n---COMMIT_END---"],
        DATA_REPO_PATH
    )
    if code != 0 or not out:
        return []
    rows = []
    commits = out.split("---COMMIT_END---")
    for commit in commits:
        commit = commit.strip()
        if not commit or "|" not in commit:
            continue
        try:
            full_hash, full_msg = commit.split("|", 1)
            full_hash = full_hash.strip()
            full_msg = full_msg.strip()
        except ValueError:
            continue
        # Extract subject (first line) for MD detection
        subj = full_msg.split("\n")[0] if full_msg else ""
        m = re.search(r"\b(MD\d{2})\b", subj)
        if not m:
            continue
        rows.append({
            "md": m.group(1),
            "hash_short": full_hash[:10],
            "hash_full": full_hash,
            "subject": subj,
            "full_message": full_msg
        })

    # dedupe per md: keep newest occurrence
    seen = set()
    uniq = []
    for r in rows:
        if r["md"] in seen:
            continue
        seen.add(r["md"])
        uniq.append(r)
    return uniq

GIT_CONTROLS_ENABLED = SERVER_MODE and (not is_sandbox_mode())

with st.sidebar:
    st.markdown("## 📦 SSOT Data Repo")
    st.caption("Wichtig: Diese Buttons arbeiten am **Data-Repo**. Nicht an der Engine.")

    st.write(f"Data dir: `{DATA_DIR}`")
    if not os.environ.get("HIGHSPEED_DATA_ROOT"):
        st.warning("HIGHSPEED_DATA_ROOT ist NICHT gesetzt → Engine könnte ins Repo schreiben. Fix das zuerst.", icon="⚠️")

    if not SERVER_MODE:
        st.info("Lokaler Streamlit-Run erkannt → Deploy/Push ist disabled (Sicherheits-Guard).", icon="🧷")

    # Statusbox
    s_dev  = get_repo_status("dev")  if SERVER_MODE else {"ok": False}
    s_main = get_repo_status("main") if SERVER_MODE else {"ok": False}

    with st.expander("🔎 Status (Data Repo)", expanded=True):
        if SERVER_MODE and s_dev.get("ok"):
            st.markdown(
                f"**Repo-Branch (lokal):** `{s_dev['branch']}`  \n"
                f"**HEAD:** `{s_dev['head']}`  \n"
                f"**Letzter Commit:** {s_dev['last_msg']}"
            )
            st.markdown(
                f"**origin/dev:** `{s_dev['remote_head']}`  \n"
                f"**origin/main:** `{s_main['remote_head']}`"
            )
        else:
            st.write("Status nicht verfügbar (nicht auf dem Raspberry oder Repo fehlt).")

    st.divider()

    # =========== ROLLBACK HANDLER ===========
    # Execute rollback if button was clicked
    if st.session_state.get("rollback_chosen"):
        chosen = st.session_state.rollback_chosen
        force_push_rb = st.session_state.get("rollback_force_push", False)
        
        with st.spinner("Rollback läuft..."):
            steps = [
                ("git fetch origin", data_git("fetch", "origin")),
                ("git checkout main", data_git("checkout", "main")),
                (f"git reset --hard {chosen['sha']}", data_git("reset", "--hard", chosen["sha"])),
                ("git clean -fd", data_git("clean", "-fd")),
            ]

            if force_push_rb:
                steps.append(("git push origin main --force", data_git("push", "origin", "main", "--force")))
                # DEV Branch auch zurücksetzen, damit Pull später nicht überschreibt
                steps.append(("git checkout dev", data_git("checkout", "dev")))
                steps.append((f"git reset --hard {chosen['sha']}", data_git("reset", "--hard", chosen["sha"])))
                steps.append(("git push origin dev --force", data_git("push", "origin", "dev", "--force")))
                steps.append(("git checkout main", data_git("checkout", "main")))

            errors = [(name, rc, out) for name, (rc, out) in steps if rc != 0]
            if errors:
                msg = "\n".join([f"{name}: {out}" for name, rc, out in errors])
                st.error(f"Rollback fehlgeschlagen:\n{msg}")
            else:
                success_msg = f"Rollback auf {chosen['sha'][:10]} abgeschlossen."
                if force_push_rb:
                    success_msg += " Remote-History wurde überschrieben (force-push)."
                
                # Setze Pointer auf neuen Commit
                st.info("Setze Pointer auf neuen Rollback-Commit...")
                
                pointer_errors = []
                
                # DEV-Pointer
                code_dev, out_dev = set_pointer("dev", "dev", chosen["sha"])
                if code_dev != 0:
                    pointer_errors.append(f"DEV-Pointer: {out_dev}")
                else:
                    st.success(f"✅ DEV-Pointer gesetzt → {chosen['sha'][:10]}")
                
                # PROD-Pointer (optional, aber empfohlen bei Rollback)
                code_prod, out_prod = set_pointer("prod", "dev", chosen["sha"])
                if code_prod != 0:
                    pointer_errors.append(f"PROD-Pointer: {out_prod}")
                else:
                    st.success(f"✅ PROD-Pointer gesetzt → {chosen['sha'][:10]}")
                
                if pointer_errors:
                    st.warning("⚠️ Einige Pointer konnten nicht gesetzt werden:\n" + "\n".join(pointer_errors))
                
                st.success(success_msg + " Alle Pointer wurden auf den Rollback-Commit gesetzt. Engine kann ab diesem Stand weiter simulieren.")
                
                # Nach Rollback: State aktualisieren basierend auf Repo
                st.info("Prüfe Spieltag im Repo...")
                try:
                    state = sim.load_state()
                    if state:
                        season = state.get("season", 1)
                        max_spieltag = sim.find_max_spieltag_in_repo(season)
                        if max_spieltag > 0:
                            st.info(f"Setze Spieltag auf {max_spieltag} (höchster im Repo)")
                            state["spieltag"] = max_spieltag
                            sim.save_state(state)
                            st.success(f"✅ State aktualisiert: Spieltag {max_spieltag}")
                        else:
                            st.warning(f"⚠️ Kein Spieltag im Repo gefunden, State bleibt unverändert")
                    else:
                        st.warning("⚠️ State konnte nicht geladen werden")
                except Exception as e:
                    st.error(f"Fehler beim State-Update: {e}")
                
                st.cache_data.clear()
                st.session_state.rollback_chosen = None  # Reset state
                st.rerun()  # Force UI update to show fresh commits

    if is_sandbox_mode():
        st.info("Git/Publish/Pointer sind in SANDBOX deaktiviert.", icon="🧷")
    else:
        # Tabs: Sync / Commit / Pointer Deploy
        tab_sync, tab_commit, tab_live = st.tabs(["🔄 Sync", "✅ Commit & Push", "🔗 Pointer Deploy"])

        # -------------------------
        # Sync Tab
        # -------------------------
        with tab_sync:
            st.markdown("### Sync (holen)")
            st.caption("Pull macht einen harten Reset auf den gewählten Branch (SSOT-Repo).")

            pull_branch = st.radio(
                "Branch",
                options=["dev", "main"],
                horizontal=True,
                index=0
            )

            if st.button(f"⬇️ Pull Data ({pull_branch})", use_container_width=True, disabled=not GIT_CONTROLS_ENABLED):
                cmd = [str(SCRIPT_PULL), pull_branch] if SCRIPT_PULL.exists() else []
                if not cmd:
                    st.error("data_pull.sh nicht gefunden.")
                else:
                    code, out = _run(cmd)
                    if code == 0:
                        st.success("Pull OK")
                        
                        # Nach Pull: State korrigieren basierend auf tatsächlichem Repo
                        try:
                            state = sim.load_state()
                            if state:
                                season = state.get("season", 1)
                                max_spieltag = sim.find_max_spieltag_in_repo(season)
                                if max_spieltag > 0 and state.get("spieltag", 0) > max_spieltag:
                                    st.info(f"State korrigiert: Spieltag {state['spieltag']} → {max_spieltag} (max im Repo)")
                                    state["spieltag"] = max_spieltag
                                    sim.save_state(state)
                                    st.success(f"✅ State aktualisiert")
                        except Exception as e:
                            st.warning(f"Konnte State nicht korrigieren: {e}")
                        
                        st.cache_data.clear()
                    else:
                        st.error("Pull FAIL")
                    if out:
                        st.code(out)

        # -------------------------
        # Commit Tab (DEV only)
        # -------------------------
        with tab_commit:
            st.markdown("### Commit & Push (DEV)")
            st.caption("Nur DEV. Commit-Message muss **MDxx** enthalten (Guard im Script).")

            # Default: MDxx based on current engine state (info ist weiter unten, aber wir haben sim_state)
            try:
                cur_state = sim.load_state()
                raw_md = int(cur_state.get("spieltag", 0) or 0)   # next pointer
            except Exception:
                raw_md = 0

            last_simulated = max(0, raw_md - 1)

            if last_simulated <= 0:
                default_msg = "MD01 simulated"
            else:
                default_msg = f"MD{last_simulated:02d} simulated"


            msg = st.text_input("Commit-Message", value=default_msg, help="Beispiel: MD04 simulated")

            if st.button("⬆️ Commit & Push DEV", use_container_width=True, disabled=not GIT_CONTROLS_ENABLED):
                cmd = [str(SCRIPT_PUSH), "dev", msg.strip()] if SCRIPT_PUSH.exists() else []
                if not cmd:
                    st.error("data_push.sh nicht gefunden.")
                else:
                    code, out = _run(cmd)
                    if code == 0:
                        st.success("Push OK (dev)")
                        st.cache_data.clear()
                    else:
                        st.error("Push FAIL (dev)")
                    if out:
                        st.code(out)

        # -------------------------
        # Pointer Deploy (setzt Pointers für Deploy)
        # -------------------------
        with tab_live:
            st.markdown("### Pointer Deploy (setzt DEV/LIVE Pointer)")
            st.caption("Du wählst einen DEV-Commit (MDxx) und setzt den Pointer für DEV oder LIVE Deploy.")

            md_rows = list_dev_md_commits(limit=80) if SERVER_MODE else []
            if not md_rows:
                st.warning("Keine DEV-Commits mit MDxx gefunden (oder nicht auf Raspberry).", icon="⚠️")
            else:
                options = [f"{r['md']} · {r['hash_short']} · {r['subject']}" for r in md_rows]
                sel = st.selectbox("Commit auswählen", options=options, index=0)
                chosen = md_rows[options.index(sel)]

                st.markdown(f"**Auswahl:** `{chosen['md']}` → `{chosen['hash_short']}`")

                # Zwei Buttons mit Confirm
                confirm_dev = st.checkbox("Ja, ich will DEV Pointer setzen.", value=False, key="confirm_dev")
                extra_confirm_dev = st.checkbox(
                    "Ich weiß was ich tue: Das wirkt auf LIVE/SSOT.",
                    value=False,
                    key="confirm_live_danger_dev"
                ) if is_ssot_root() else True
                if st.button("🟦 Set DEV Pointer", use_container_width=True, disabled=(not GIT_CONTROLS_ENABLED or not confirm_dev or not extra_confirm_dev)):
                    code, out = set_pointer("dev", "dev", chosen["hash_full"])
                    if code == 0:
                        st.success(f"DEV Pointer gesetzt → {chosen['hash_short']}")
                        st.cache_data.clear()
                        st.session_state.pop("confirm_dev", None)
                        st.rerun()
                    else:
                        st.error("DEV Pointer setzen fehlgeschlagen")
                    if out:
                        st.code(out)

                confirm_live = st.checkbox("Ja, ich will LIVE Pointer setzen.", value=False, key="confirm_live")
                extra_confirm_live = st.checkbox(
                    "Ich weiß was ich tue: Das wirkt auf LIVE/SSOT.",
                    value=False,
                    key="confirm_live_danger_live"
                ) if is_ssot_root() else True
                if st.button("🟪 Set LIVE Pointer", use_container_width=True, disabled=(not GIT_CONTROLS_ENABLED or not confirm_live or not extra_confirm_live)):
                    code, out = set_pointer("prod", "dev", chosen["hash_full"])
                    if code == 0:
                        st.success(f"LIVE Pointer gesetzt → {chosen['hash_short']}")
                        st.cache_data.clear()
                        st.session_state.pop("confirm_live", None)
                        st.rerun()
                    else:
                        st.error("LIVE Pointer setzen fehlgeschlagen")
                    if out:
                        st.code(out)

            st.divider()

            # Replay Pointer (unabhängig von Main-Pointer)
            st.markdown("### Replay-Konferenz Pointer")
            st.caption("Setzt den Replay-Pointer unabhängig vom Main-Pointer. Für Live-Konferenz, die weiter ist als offizieller Stand.")
            
            if not md_rows:
                st.info("Keine Commits verfügbar.")
            else:
                replay_options = [f"{r['md']} · {r['hash_short']} · {r['subject']}" for r in md_rows]
                replay_sel = st.selectbox("Replay-Commit auswählen", options=replay_options, index=0, key="sb_replay_commit")
                replay_chosen = md_rows[replay_options.index(replay_sel)]

                st.markdown(f"**Replay-Auswahl:** `{replay_chosen['md']}` → `{replay_chosen['hash_short']}`")

                confirm_replay = st.checkbox("Ja, ich will Replay Pointer setzen.", value=False, key="confirm_replay")
                extra_confirm_replay = st.checkbox(
                    "Ich weiß was ich tue: Das wirkt auf LIVE/SSOT.",
                    value=False,
                    key="confirm_live_danger_replay"
                ) if is_ssot_root() else True
                
                btn_enabled = GIT_CONTROLS_ENABLED and confirm_replay and extra_confirm_replay
                if not btn_enabled:
                    reasons = []
                    if not GIT_CONTROLS_ENABLED:
                        reasons.append("Git Controls disabled")
                    if not confirm_replay:
                        reasons.append("Erste Checkbox nicht aktiviert")
                    if not extra_confirm_replay:
                        reasons.append("SSOT-Bestätigung fehlt")
                    st.caption(f"⚠️ Button disabled: {', '.join(reasons)}")
                
                if st.button("🎬 Set REPLAY Pointer", use_container_width=True, disabled=not btn_enabled, key="btn_set_replay_pointer"):
                    with st.spinner("Setze Replay Pointer..."):
                        # 1. Pointer setzen
                        code, out = set_pointer("replay", "main", replay_chosen["hash_full"])
                        if code == 0:
                            st.success(f"✅ REPLAY Pointer gesetzt → {replay_chosen['hash_short']}")
                            
                            # 2. Replay-Daten pushen (nur replays/ Ordner)
                            st.info("Pushe Replay-Daten zum Web-Repo...")
                            replay_push_script = PUBLISHER_DIR / "replay_push.sh"
                            if replay_push_script.exists():
                                push_code, push_out = _run([str(replay_push_script), replay_chosen["md"]])
                                if push_code == 0:
                                    st.success(f"✅ Replay-Daten gepusht ({replay_chosen['md']})")
                                else:
                                    st.warning(f"⚠️ Replay-Push fehlgeschlagen (Code {push_code})")
                                if push_out:
                                    with st.expander("Push Output"):
                                        st.code(push_out)
                            else:
                                st.warning("⚠️ replay_push.sh nicht gefunden - Daten wurden nicht gepusht")
                            
                            st.info("Die Konferenz/Replay-Seite folgt jetzt diesem Stand (data-repo MAIN), während die Hauptseite beim PROD-Pointer bleibt.")
                            st.cache_data.clear()
                            st.session_state.pop("confirm_replay", None)
                            st.rerun()
                        else:
                            st.error("❌ REPLAY Pointer setzen fehlgeschlagen")
                        if out:
                            with st.expander("Pointer Output"):
                                st.code(out)


# ============================================================
# Deploy Controls (Web + Toolbox)
# ============================================================
def sudo_systemctl(args: list[str]) -> tuple[int, str]:
    # -n = non-interactive: failt sauber, wenn sudoers nicht passt
    return _run(["sudo", "-n", "/bin/systemctl", *args])

def sudo_journal(service: str) -> tuple[int, str]:
    return _run(["sudo", "-n", "/usr/bin/journalctl", "-u", service, "-n", "120", "--no-pager"])

st.sidebar.markdown("## 🚀 Deploy (Web + Toolbox)")

c1, c2 = st.sidebar.columns(2)
with c1:
    if st.button("DEPLOY · Web jetzt", use_container_width=True):
        code, out = sudo_systemctl(["start", "highspeed-web-deploy.service"])
        st.sidebar.success("OK" if code == 0 else "FAIL")
        if out:
            st.sidebar.code(out)

with c2:
    if st.button("DEPLOY · Toolbox jetzt", use_container_width=True):
        code, out = sudo_systemctl(["start", "highspeed-toolbox-deploy.service"])
        st.sidebar.success("OK" if code == 0 else "FAIL")
        if out:
            st.sidebar.code(out)

st.sidebar.markdown("## ⏱ Auto-Deploy (Timer)")

t1, t2 = st.sidebar.columns(2)
with t1:
    if st.button("Auto AN", use_container_width=True):
        a1 = sudo_systemctl(["enable", "highspeed-web-deploy.timer"])
        a2 = sudo_systemctl(["start", "highspeed-web-deploy.timer"])
        b1 = sudo_systemctl(["enable", "highspeed-toolbox-deploy.timer"])
        b2 = sudo_systemctl(["start", "highspeed-toolbox-deploy.timer"])
        ok = (a1[0]==0 and a2[0]==0 and b1[0]==0 and b2[0]==0)
        st.sidebar.success("OK" if ok else "FAIL")

with t2:
    if st.button("Auto AUS", use_container_width=True):
        a1 = sudo_systemctl(["stop", "highspeed-web-deploy.timer"])
        a2 = sudo_systemctl(["disable", "highspeed-web-deploy.timer"])
        b1 = sudo_systemctl(["stop", "highspeed-toolbox-deploy.timer"])
        b2 = sudo_systemctl(["disable", "highspeed-toolbox-deploy.timer"])
        ok = (a1[0]==0 and a2[0]==0 and b1[0]==0 and b2[0]==0)
        st.sidebar.success("OK" if ok else "FAIL")

st.sidebar.markdown("## 🧾 Deploy-Logs")

service = st.sidebar.selectbox(
    "Service",
    ["highspeed-web-deploy.service", "highspeed-toolbox-deploy.service"],
)
if st.sidebar.button("Logs anzeigen", use_container_width=True):
    code, out = sudo_journal(service)
    if code == 0:
        st.sidebar.code(out or "(leer)")
    else:
        st.sidebar.error("FAIL (keine sudo-Rechte?)")
        if out:
            st.sidebar.code(out)

# ============================================================
# Hauptansicht – Tabs
# ============================================================
st.title("PUX! Engine – GUI")
info = sim.read_tables_for_ui()
# --- UI-normalized matchday (current / last simulated) ---
raw_md = info.get("spieltag", 0)
info["ui_spieltag"] = ui_current_matchday(raw_md)


tab_tables, tab_calendar, tab_gamedays, tab_playoffs, tab_history = st.tabs([
    "📊 Tabellen & Scorer",
    "📅 Spielplan (Kalender)",
    "🧾 Spieltag-Browser",
    "🏆 Playoff-Browser",
    "🗂️ Saison-History",
])


# ============================================================
# TAB: Tabellen / Scorer
# ============================================================
with tab_tables:
    col_l, col_r = st.columns([2, 1], gap="large")

    with col_l:
        st.subheader(f"📅 Saison {info['season']} · Spieltag {info["ui_spieltag"]}")
        st.caption(f"Rest-Schedule: Nord {info['nsched_len']} · Süd {info['ssched_len']} Paarungen offen")

        st.markdown("### 📊 Tabelle Nord")
        tn = pd.DataFrame(info["tables"]["tabelle_nord"]).copy()
        tn.insert(0, "Logo", tn["Team"].apply(lambda t: team_logo_dataurl(t, 24, 2)))
        tn.rename(columns={"Points": "P"}, inplace=True)

        st.dataframe(
            tn[["Logo","Team","P","GF","GA","GD"]],
            use_container_width=True,
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

        st.markdown("### 📊 Tabelle Süd")
        ts = pd.DataFrame(info["tables"]["tabelle_sued"]).copy()
        ts.insert(0, "Logo", ts["Team"].apply(lambda t: team_logo_dataurl(t, 24, 2)))
        ts.rename(columns={"Points": "P"}, inplace=True)

        st.dataframe(
            ts[["Logo","Team","P","GF","GA","GD"]],
            use_container_width=True,
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
        st.markdown("### ⭐ Top-Scorer (Top 20)")
        tops = pd.DataFrame(info["tables"]["top_scorer"]).copy().head(20)

        tops.insert(0, "Logo", tops["Team"].apply(lambda t: team_logo_dataurl(t, 22, 2)))
        tops["Spieler"] = tops["Player"] + " (" + tops["Team"] + ")"

        if "Number" not in tops.columns:
            tops["Number"] = None
        if "PositionGroup" not in tops.columns:
            tops["PositionGroup"] = None

        tops.rename(columns={"Number": "#", "PositionGroup": "Pos"}, inplace=True)

        st.dataframe(
            tops[["Logo", "Spieler", "#", "Pos", "Goals", "Assists", "Points"]],
            use_container_width=True,
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


# ============================================================
# TAB: Spielplan (Kalender)
# ============================================================
with tab_calendar:
    st.subheader("📅 Spielplan / Kalender")

    sel_season = int(st.session_state.browser_season or info.get("season", 1) or 1)
    sp_path = spielplan_path(sel_season)
    sp = load_spielplan(sp_path)

    if not sp:
        st.warning(
            f"Kein Spielplan gefunden unter: {sp_path}\n\n"
            "Hinweis: `spielplan.json` wird bei Saisonstart erstellt und liegt im Data-Repo unter:\n"
            "schedules/saison_<N>/spielplan.json"
        )
    else:
        season = sp.get("season", "?")
        st.caption(f"Saison {season} · Quelle: {sp_path}")

        liga = st.segmented_control("Konferenz", options=["Nord", "Süd"], default="Nord")
        block = sp["nord"] if liga == "Nord" else sp["sued"]

        teams = block.get("teams", [])
        matchdays = block.get("matchdays", [])

        team_filter = st.selectbox("Team-Filter (optional)", options=["(alle)"] + teams, index=0)

        # Aktueller Spieltag nur als Orientierung (Engine-State)
        cur_md = spieltag_index(info.get("spieltag", 1)) or 1


        md_nums = [m.get("matchday") for m in matchdays if isinstance(m.get("matchday"), int)]
        md_nums = [m for m in md_nums if m is not None]

        c1, _ = st.columns([1, 2])
        with c1:
            view_mode = st.radio("Ansicht", ["Nächste Spieltage", "Ein Spieltag", "Alle Spieltage"], index=0)

        def _matches_for_md(md: dict) -> pd.DataFrame:
            rows = []
            for m in md.get("matches", []):
                home = m.get("home", "")
                away = m.get("away", "")
                if team_filter != "(alle)" and team_filter not in (home, away):
                    continue
                rows.append({
                    "HomeLogo": team_logo_dataurl(home, 22, 2),
                    "Home": home,
                    "AwayLogo": team_logo_dataurl(away, 22, 2),
                    "Away": away,
                })
            return pd.DataFrame(rows)

        if view_mode == "Ein Spieltag":
            md_sel = st.selectbox(
                "Spieltag",
                options=md_nums,
                index=(md_nums.index(cur_md) if cur_md in md_nums else 0)
            )
            md_obj = next((m for m in matchdays if m.get("matchday") == md_sel), None)
            if not md_obj:
                st.info("Spieltag nicht gefunden.")
            else:
                st.markdown(f"### {liga} · Spieltag {md_sel}")
                df = _matches_for_md(md_obj)
                if df.empty:
                    st.info("Keine Matches (Filter?)")
                else:
                    st.dataframe(
                        df[["HomeLogo","Home","AwayLogo","Away"]],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "HomeLogo": st.column_config.ImageColumn(" ", width="small"),
                            "Home":     st.column_config.TextColumn("Home"),
                            "AwayLogo": st.column_config.ImageColumn(" ", width="small"),
                            "Away":     st.column_config.TextColumn("Away"),
                        }
                    )

        elif view_mode == "Alle Spieltage":
            for md in matchdays:
                md_no = md.get("matchday")
                if md_no is None:
                    continue
                with st.expander(f"{liga} · Spieltag {md_no}", expanded=False):
                    df = _matches_for_md(md)
                    if df.empty:
                        st.info("Keine Matches (Filter?)")
                    else:
                        st.dataframe(
                            df[["HomeLogo","Home","AwayLogo","Away"]],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "HomeLogo": st.column_config.ImageColumn(" ", width="small"),
                                "Home":     st.column_config.TextColumn("Home"),
                                "AwayLogo": st.column_config.ImageColumn(" ", width="small"),
                                "Away":     st.column_config.TextColumn("Away"),
                            }
                        )
        else:
            next_n = st.slider("Wie viele Spieltage anzeigen?", min_value=1, max_value=8, value=3, step=1)
            start = cur_md
            end = start + next_n - 1

            for md_no in range(start, end + 1):
                md_obj = next((m for m in matchdays if m.get("matchday") == md_no), None)
                if not md_obj:
                    continue
                st.markdown(f"### {liga} · Spieltag {md_no}")
                df = _matches_for_md(md_obj)
                if df.empty:
                    st.info("Keine Matches (Filter?)")
                else:
                    st.dataframe(
                        df[["HomeLogo","Home","AwayLogo","Away"]],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "HomeLogo": st.column_config.ImageColumn(" ", width="small"),
                            "Home":     st.column_config.TextColumn("Home"),
                            "AwayLogo": st.column_config.ImageColumn(" ", width="small"),
                            "Away":     st.column_config.TextColumn("Away"),
                        }
                    )
                st.divider()


# ============================================================
# Signaturen für Live-Reload (ändern sich bei neuen JSONs)
# ============================================================
SIG_SPIELTAGE = dir_signature(SPIELTAG_DIR)
SIG_PLAYOFFS  = dir_signature(PLAYOFF_DIR)


# ============================================================
# TAB: Spieltag-Browser (History & Download) — live
# ============================================================
with tab_gamedays:
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
        folder = SPIELTAG_DIR / season_folder(season)

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
        folder = SPIELTAG_DIR / season_folder(season)
        if not folder.exists():
            return None

        # exakt auf Dateinamen gehen (robust, kein Regex-Gefrickel)
        f = folder / f"spieltag_{int(gameday):02d}.json"
        if not f.exists():
            return None

        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None



    st.markdown("### 🧾 Spieltag-Browser (History & Download)")

    # Default: Browser-Saison nehmen
    seasons_avail = list_spieltage_seasons(SIG_SPIELTAGE)
    sel_season = int(st.session_state.browser_season or (seasons_avail[-1] if seasons_avail else info["season"]))
    sig_season = dir_signature(SPIELTAG_DIR / season_folder(sel_season))

    gds = list_gamedays(sel_season, sig_season)

    # Immer auf letzten verfügbaren Spieltag setzen
    if gds:
        st.session_state.sel_gameday = gds[-1]
    elif "sel_gameday" not in st.session_state:
        st.session_state.sel_gameday = 1

    cols = st.columns([2,3])
    with cols[0]:
        st.caption(f"Aktive Browser-Saison: {sel_season}")
    with cols[1]:
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
                index=(len(gds)-1 if gds else 0),
                key="dd_gameday_browser"
            )
        with cnext:
            if st.button("▶", key="gd_next") and gds:
                cur = st.session_state.get("sel_gameday", gds[-1])
                idx = gds.index(cur) if cur in gds else len(gds)-1
                st.session_state.sel_gameday = gds[min(len(gds)-1, idx+1)]

    gjson = load_gameday_json(sel_season, st.session_state.sel_gameday, sig_season )

    st.write("DEBUG sel_season =", sel_season)
    st.write("DEBUG sel_gameday =", st.session_state.sel_gameday)
    st.write("DEBUG SPIELTAG_DIR =", str(SPIELTAG_DIR))


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

        nord = _prep(res_all[res_all.get("conference")=="Nord"])
        sued = _prep(res_all[res_all.get("conference")=="Süd"])

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Nord")
            st.dataframe(
                nord[["HomeLogo","home","AwayLogo","away","Score","Tag"]] if not nord.empty else pd.DataFrame(),
                use_container_width=True,
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
                sued[["HomeLogo","home","AwayLogo","away","Score","Tag"]] if not sued.empty else pd.DataFrame(),
                use_container_width=True,
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

        st.markdown("#### Download")
        st.download_button(
            "📦 JSON (Original)",
            data=json.dumps(gjson, ensure_ascii=False, indent=2),
            file_name=f"s{gjson['saison']:02}_spieltag_{gjson['spieltag']:02}.json",
            mime="application/json",
            use_container_width=True,
            key="dl_json_gd"
        )
        st.download_button(
            "🧾 CSV (Ergebnisse)",
            data=res_all.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"s{gjson['saison']:02}_spieltag_{gjson['spieltag']:02}.csv",
            mime="text/csv",
            use_container_width=True,
            key="dl_csv_gd"
        )


# ============================================================
# TAB: Playoff-Browser (History & Download)
# ============================================================
with tab_playoffs:
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
        folder = PLAYOFF_DIR / season_folder(season)

        if not folder.exists():
            return []
        vals=[]
        for f in folder.iterdir():
            m = re.match(r"(?i)runde_(\d+).*\.json$", f.name)
            if f.is_file() and m:
                vals.append(int(m.group(1)))
        return sorted(set(vals))

    def load_round_json(season: int, rnd: int, _sig_season: str) -> Optional[dict]:
        folder = PLAYOFF_DIR / season_folder(season)
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

    seasons_po = list_playoff_seasons(SIG_PLAYOFFS)
    sel_po_season = int(st.session_state.browser_season or (seasons_po[-1] if seasons_po else info["season"]))
    sig_po_season = dir_signature(PLAYOFF_DIR / season_folder(sel_po_season))

    rounds = list_rounds(sel_po_season, sig_po_season)

    # Immer auf letzte verfügbare Runde setzen
    if rounds:
        st.session_state.po_round = rounds[-1]
    elif "po_round" not in st.session_state:
        st.session_state.po_round = 1

    st.caption(f"Aktive Browser-Saison: {sel_po_season}")

    if rounds:
        rprev, rsel, rnext = st.columns([1,3,1])
        with rprev:
            if st.button("◀", key="po_prev") and rounds:
                cur = st.session_state.get("po_round", rounds[-1])
                idx = rounds.index(cur) if cur in rounds else len(rounds)-1
                st.session_state.po_round = rounds[max(0, idx-1)]
        with rsel:
            st.session_state.po_round = st.selectbox(
                "Runde",
                options=rounds,
                index=(len(rounds)-1 if rounds else 0),
                key="po_round_sel"
            )
        with rnext:
            if st.button("▶", key="po_next") and rounds:
                cur = st.session_state.get("po_round", rounds[-1])
                idx = rounds.index(cur) if cur in rounds else len(rounds)-1
                st.session_state.po_round = rounds[min(len(rounds)-1, idx+1)]

        po_json = load_round_json(sel_po_season, st.session_state.po_round, sig_po_season)
    else:
        po_json = None

    def _render_series_block(round_json: dict):
        st.markdown(f"#### Playoff-Runde {round_json.get('runde')} (Saison {round_json.get('saison')})")

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
                        p1 = get_logo_thumb_path(a, 96, 2)
                        if p1:
                            st.image(p1, width=96)
                            st.caption(a)
                    with c3:
                        p2 = get_logo_thumb_path(b, 96, 2)
                        if p2:
                            st.image(p2, width=96)
                            st.caption(b)

                    if not df.empty:
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.write("Keine Einzelspiele gespeichert.")
            return

        st.info("Playoff-JSON Format unbekannt / leer.")

    if po_json:
        _render_series_block(po_json)
        st.markdown("#### Download")
        st.download_button(
            "📦 JSON (Playoff-Runde)",
            data=json.dumps(po_json, ensure_ascii=False, indent=2),
            file_name=f"s{po_json['saison']:02}_runde_{po_json['runde']:02}.json",
            mime="application/json",
            use_container_width=True,
            key="dl_json_po"
        )
    else:
        st.info("Noch keine Playoff-Daten gefunden oder Auswahl leer.")


# ============================================================
# TAB: Saison-History
# ============================================================
with tab_history:
    st.markdown("### 🗂️ Saison-History (Champions & Navigation)")
    hist = info.get("history", []) or []
    if hist:
        hdf = pd.DataFrame(hist).sort_values("season")
        st.dataframe(hdf, use_container_width=True, hide_index=True)
    else:
        st.info("Noch keine abgeschlossene Saison – simuliere bis zum Champion.")
