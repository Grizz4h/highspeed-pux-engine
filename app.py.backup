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

DATA_REPO_PATH = Path("/opt/highspeed/data")
PUBLISHER_DIR  = Path("/opt/highspeed/publisher")
SCRIPT_PULL    = PUBLISHER_DIR / "data_pull.sh"
SCRIPT_PUSH    = PUBLISHER_DIR / "data_push.sh"
SCRIPT_PUBLISH = PUBLISHER_DIR / "publish_live.sh"  # optional, falls vorhanden

SERVER_MODE = (
    os.name != "nt"
    and Path("/opt/highspeed").exists()
    and PUBLISHER_DIR.exists()
)



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

if "sim_intent" not in st.session_state:
    st.session_state.sim_intent = None

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

    with st.expander("📌 Pfade (Debug)", expanded=False):
        st.code(f"APP_DIR  = {APP_DIR}\nDATA_DIR = {DATA_DIR}\nSAVE    = {SAVEGAME_PATH}")

        if not os.environ.get("HIGHSPEED_DATA_ROOT"):
            st.warning("HIGHSPEED_DATA_ROOT ist NICHT gesetzt → DATA_DIR fällt auf APP_DIR zurück.")

    # --- SIM BUTTONS (arbeiten immer gegen den aktuellen Save-State) ---
    st.markdown("### Simulation (aktive Saison)")

    st.markdown("### Simulation Intent (Pflichtauswahl)")

    test_checked = st.checkbox(
        "🧪 Test / Vorlauf (DEV)",
        value=(st.session_state.sim_intent == "test"),
        key="intent_test",
    )

    live_checked = st.checkbox(
        "🚀 Live-relevant vorbereiten",
        value=(st.session_state.sim_intent == "live"),
        key="intent_live",
    )

    # Mutual exclusion + state
    if test_checked and not live_checked:
        st.session_state.sim_intent = "test"
    elif live_checked and not test_checked:
        st.session_state.sim_intent = "live"
    else:
        st.session_state.sim_intent = None

    if st.session_state.sim_intent is None:
        st.warning("Bitte wähle **Test** oder **Live-relevant**, bevor du simulierst.")




    simulate_disabled = (st.session_state.sim_intent is None)

    if st.button(
        "▶️ Nächsten Spieltag simulieren",
        key="btn_spieltag",
        use_container_width=True,
        disabled=simulate_disabled
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
                # Intent-Aktion
                if st.session_state.sim_intent == "test":
                    st.toast(f"🧪 Test: MD{last_simulated:02d} simuliert (kein Push)", icon="✅")

                elif st.session_state.sim_intent == "live":
                    msg = f"MD{last_simulated:02d} simulated"
                    if os.name != "nt" and SCRIPT_PUSH.exists():
                        code, out = _run([str(SCRIPT_PUSH), "dev", msg])
                        if code == 0:
                            st.toast(f"🚀 Live-prep: {msg} → DEV gepusht", icon="✅")
                        else:
                            st.error("Auto-Push nach DEV fehlgeschlagen")
                        if out:
                            st.code(out)
                    else:
                        st.warning("data_push.sh fehlt oder lokaler Run → kein Auto-Push möglich.", icon="⚠️")


                st.cache_data.clear()

                # FAILSAFE: Intent zurücksetzen (one-shot)
                st.session_state.sim_intent = None
                st.session_state.pop("intent_test", None)
                st.session_state.pop("intent_live", None)
                st.rerun()
                st.rerun()

            elif status == "season_over":
                st.toast("Regular Season ist beendet. Starte die Playoffs 👇", icon="⚠️")

                # Intent auch hier zurücksetzen (sonst bleibt's hängen)
                st.session_state.sim_intent = None
  

            else:
                st.toast(f"Konnte Spieltag nicht simulieren (Status: {status}).", icon="❌")

                st.session_state.sim_intent = None
 


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

# ============================================================
# Data Repo Controls (SSOT) — safe, explicit, self-explaining
# ============================================================

def _run_in(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()

def data_git(*args: str) -> tuple[int, str]:
    return _run_in(["git", *args], DATA_REPO_PATH)

def reset_dev_to_main() -> tuple[int, str]:
    """
    Setzt Data-Repo DEV exakt auf origin/main.
    Achtung: überschreibt DEV-History (force-with-lease).
    """
    steps = [
        (["git", "fetch", "origin"], "fetch origin"),
        (["git", "checkout", "dev"], "checkout dev"),
        (["git", "reset", "--hard", "origin/main"], "reset dev -> origin/main"),
        (["git", "clean", "-fd"], "clean"),
        (["git", "push", "origin", "dev", "--force-with-lease"], "push dev (force-with-lease)"),
    ]

    out_all = []
    for cmd, label in steps:
        code, out = _run_in(cmd, DATA_REPO_PATH)
        out_all.append(f"$ {' '.join(cmd)}\n{out}".strip())
        if code != 0:
            return code, "\n\n".join(out_all) + f"\n\n[FAIL] step: {label}"
    return 0, "\n\n".join(out_all) + "\n\n[OK] DEV == MAIN"

    

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
        ["git", "log", "origin/dev", f"-n{limit}", "--pretty=%H|%s"],
        DATA_REPO_PATH
    )
    if code != 0 or not out:
        return []
    rows = []
    for line in out.splitlines():
        try:
            full, subj = line.split("|", 1)
        except ValueError:
            continue
        m = re.search(r"\b(MD\d{2})\b", subj)
        if not m:
            continue
        rows.append({"md": m.group(1), "hash": full[:10], "subject": subj})
    # dedupe per md: keep newest occurrence
    seen = set()
    uniq = []
    for r in rows:
        if r["md"] in seen:
            continue
        seen.add(r["md"])
        uniq.append(r)
    return uniq

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
    st.markdown("### 🔧 Data Repo Admin")

    if not SERVER_MODE:
        st.info("DEV=MAIN Reset ist nur auf dem Raspberry verfügbar.")
    else:
        # Status anzeigen (kurz, hilfreich)
        try:
            data_git("fetch", "origin")
            _, main_h = data_git("rev-parse", "--short", "origin/main")
            _, dev_h  = data_git("rev-parse", "--short", "origin/dev")
            st.caption(f"origin/main: `{main_h}`  ·  origin/dev: `{dev_h}`")
        except Exception:
            pass

        confirm_reset = st.checkbox(
            "Ja, ich will DEV auf MAIN zurücksetzen (überschreibt DEV).",
            value=False,
            key="confirm_reset_dev_main"
        )

        if st.button(
            "🔁 Reset DEV = MAIN (Data Repo)",
            use_container_width=True,
            disabled=not confirm_reset
        ):
            code, out = reset_dev_to_main()
            if code == 0:
                st.success("DEV wurde exakt auf MAIN gesetzt.")
                st.cache_data.clear()

                # Checkbox wieder “one-shot” zurücksetzen, ohne Widget-State direkt zu setzen:
                st.session_state.pop("confirm_reset_dev_main", None)
                st.rerun()
            else:
                st.error("Reset fehlgeschlagen.")
            if out:
                st.code(out)


    # Tabs: Sync / Commit / Publish Live
    tab_sync, tab_commit, tab_live = st.tabs(["🔄 Sync", "✅ Commit & Push", "🚀 Publish Live"])

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

        if st.button(f"⬇️ Pull Data ({pull_branch})", use_container_width=True, disabled=not SERVER_MODE):
            cmd = [str(SCRIPT_PULL), pull_branch] if SCRIPT_PULL.exists() else []
            if not cmd:
                st.error("data_pull.sh nicht gefunden.")
            else:
                code, out = _run(cmd)
                if code == 0:
                    st.success("Pull OK")
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

        if st.button("⬆️ Commit & Push DEV", use_container_width=True, disabled=not SERVER_MODE):
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
    # Publish Live (promote dev commit -> main)
    # -------------------------
    with tab_live:
        st.markdown("### Publish Live (DEV → MAIN)")
        st.caption("Du wählst einen DEV-Commit (MDxx) und setzt MAIN exakt auf diesen Stand (Release-Pointer).")

        md_rows = list_dev_md_commits(limit=80) if SERVER_MODE else []
        if not md_rows:
            st.warning("Keine DEV-Commits mit MDxx gefunden (oder nicht auf Raspberry).", icon="⚠️")
        else:
            options = [f"{r['md']} · {r['hash']} · {r['subject']}" for r in md_rows]
            sel = st.selectbox("Release auswählen", options=options, index=0)
            chosen = md_rows[options.index(sel)]

            st.markdown(f"**Auswahl:** `{chosen['md']}` → `{chosen['hash']}`")

            confirm = st.checkbox("Ja, ich will MAIN genau auf diesen Stand setzen.", value=False)

            if st.button("🚀 Publish Live (setzt Data main)", use_container_width=True, disabled=(not SERVER_MODE or not confirm)):
                # Prefer script if exists, else inline git commands
                if SCRIPT_PUBLISH.exists():
                    code, out = _run([str(SCRIPT_PUBLISH), chosen["hash"]])
                else:
                    # Inline: checkout main, hard reset to chosen commit (from dev history), push
                    code, out = _run_in(["git", "fetch", "origin"], DATA_REPO_PATH)
                    if code == 0:
                        code, out2 = _run_in(["git", "checkout", "main"], DATA_REPO_PATH)
                        out = (out + "\n" + out2).strip()
                    if code == 0:
                        code, out2 = _run_in(["git", "reset", "--hard", chosen["hash"]], DATA_REPO_PATH)
                        out = (out + "\n" + out2).strip()
                    if code == 0:
                        code, out2 = _run_in(["git", "push", "origin", "main", "--force-with-lease"], DATA_REPO_PATH)
                        out = (out + "\n" + out2).strip()

                if code == 0:
                    st.success(f"Live publish OK → main = {chosen['hash']}")
                    st.cache_data.clear()
                else:
                    st.error("Live publish FAIL")
                if out:
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

    if "sel_gameday" not in st.session_state:
        st.session_state.sel_gameday = (gds[-1] if gds else 1)

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

    @st.cache_data(show_spinner=False)
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

    if "po_round" not in st.session_state:
        st.session_state.po_round = (rounds[-1] if rounds else 1)

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
                index=(rounds.index(st.session_state.po_round) if st.session_state.po_round in rounds else len(rounds)-1),
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
