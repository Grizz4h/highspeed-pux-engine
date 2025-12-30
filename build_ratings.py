"""
build_ratings.py

Nimmt die Baseline-Daten aus:
    data/all_players_baseline.json
und berechnet daraus Ratings für deinen Liga-Generator.

Pro Spieler/Goalie:
  - offense
  - defense
  - speed
  - chemistry
  - overall

Output:
  data/players_rated.json
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DATA_DIR = Path("data")
BASELINE_FILE = DATA_DIR / "all_players_baseline.json"
OUT_FILE = DATA_DIR / "players_rated.json"

# Logging setup
logging.basicConfig(
    filename='logs/rating_calculation.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# ----------------- Helfer -----------------


def _to_float(val: Any) -> float:
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0.0
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _to_int(val: Any) -> int:
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0
        return int(val)
    except (TypeError, ValueError):
        return 0


def _scale_minmax(values: List[float]) -> Tuple[float, float]:
    """liefert (min, max); bei leeren oder konstanten Werten dummy-min/max."""
    vals = [v for v in values if not math.isnan(v)]
    if not vals:
        return 0.0, 1.0
    vmin = min(vals)
    vmax = max(vals)
    if math.isclose(vmin, vmax):
        # alles gleich → danach bekommt jeder 0.5
        return vmin, vmin + 1.0
    return vmin, vmax
def _z_params(values: List[float]) -> Tuple[float, float]:
    """
    Liefert (Mittelwert, Standardabweichung) für eine Liste.
    Falls leer oder konstant -> sigma = 1.0, damit nichts crasht.
    """
    vals = [v for v in values if not math.isnan(v)]
    if not vals:
        return 0.0, 1.0
    mu = sum(vals) / len(vals)
    var = sum((v - mu) ** 2 for v in vals) / len(vals)
    sigma = math.sqrt(var)
    if sigma <= 0:
        sigma = 1.0
    return mu, sigma


def _norm_z(value: float, mu: float, sigma: float, clamp: float = 3.0) -> float:
    """
    Normiert einen Wert über Z-Score auf [0,1].
    clamp=3.0 bedeutet: Z in [-3,3] -> [0,1].
    """
    if sigma <= 0:
        return 0.5
    z = (value - mu) / sigma
    if clamp is not None:
        z = max(-clamp, min(clamp, z))
        return (z + clamp) / (2.0 * clamp)
    # Fallback (sollte praktisch nie passieren)
    return 0.5


def _norm(value: float, vmin: float, vmax: float, invert: bool = False) -> float:
    """normiert value auf [0,1], optional invertiert (kleiner ist besser)."""
    if vmax <= vmin:
        return 0.5
    x = (value - vmin) / (vmax - vmin)
    x = max(0.0, min(1.0, x))
    return 1.0 - x if invert else x


def _rating(x: float, lo: int = 40, hi: int = 99) -> int:
    """mappt [0,1] → [lo,hi]"""
    x = max(0.0, min(1.0, x))
    return int(round(lo + x * (hi - lo)))


def _pos_group(rec: Dict[str, Any]) -> Optional[str]:
    pg = rec.get("position_group")
    if not pg:
        pos_raw = rec.get("position_raw") or rec.get("position")
        if not pos_raw:
            return None
        p = str(pos_raw).strip().upper()
        if p in ("D", "DE", "V"):
            return "D"
        if p in ("G", "GK", "T"):
            return "G"
        return "F"
    return pg


# ----------------- Rating für Skater -----------------


def build_skater_ratings(players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Nur echte Skater (keine Goalies)
    skaters = [p for p in players if p.get("type") == "skater"]

    # Relevante Rohwerte für Normalisierung sammeln (Ligaweit)
    goals_list = []
    assists_list = []
    points_list = []
    ppg_list = []
    plusminus_list = []
    pimpg_list = []
    gp_list = []
    fopct_list = []

    for p in skaters:
        gp = _to_int(p.get("gp"))
        goals = _to_int(p.get("goals"))
        assists = _to_int(p.get("assists", 0))  # Fallback, falls nicht direkt
        points = _to_int(p.get("points"))
        ppg = _to_float(p.get("points_per_game"))

        plus_m = p.get("plus_minus")
        if plus_m is None:
            plus_m_val = 0
        else:
            plus_m_val = _to_int(plus_m)

        pim = _to_int(p.get("pim"))
        pimpg = pim / gp if gp > 0 else 0.0

        fo_pct = p.get("fo_pct")
        fo_pct_val = _to_float(fo_pct) if fo_pct is not None else 0.0

        goals_list.append(float(goals))
        assists_list.append(float(assists))
        points_list.append(float(points))
        ppg_list.append(ppg)
        plusminus_list.append(float(plus_m_val))
        pimpg_list.append(pimpg)
        gp_list.append(float(gp))
        fopct_list.append(fo_pct_val)

    # Z-Score-Parameter (Ligaweit)
    g_mu, g_sigma = _z_params(goals_list)
    a_mu, a_sigma = _z_params(assists_list)
    p_mu, p_sigma = _z_params(points_list)
    ppg_mu, ppg_sigma = _z_params(ppg_list)
    pm_mu, pm_sigma = _z_params(plusminus_list)
    pimpg_mu, pimpg_sigma = _z_params(pimpg_list)
    gp_mu, gp_sigma = _z_params(gp_list)
    fo_mu, fo_sigma = _z_params(fopct_list)

    rated: List[Dict[str, Any]] = []

    logged_forward = False
    logged_offensive_d = False
    logged_defensive_d = False

    for p in skaters:
        base = dict(p)  # Kopie

        gp = _to_int(p.get("gp"))
        goals = _to_int(p.get("goals"))
        assists = _to_int(p.get("assists", 0))
        points = _to_int(p.get("points"))
        ppg = _to_float(p.get("points_per_game"))

        plus_m = p.get("plus_minus")
        plus_m_val = _to_int(plus_m) if plus_m is not None else 0

        pim = _to_int(p.get("pim"))
        pimpg = pim / gp if gp > 0 else 0.0

        fo_pct = p.get("fo_pct")
        fo_pct_val = _to_float(fo_pct) if fo_pct is not None else 0.0

        pos_group = _pos_group(p) or "F"

        # --------- Normierte Komponenten (Z-Score → [0,1]) ---------
        # Offense: Tore, Assists, Punkte, Punkte/Spiel
        g_norm   = _norm_z(float(goals),  g_mu,   g_sigma)
        a_norm   = _norm_z(float(assists), a_mu,   a_sigma)
        p_norm   = _norm_z(float(points), p_mu,   p_sigma)
        ppg_norm = _norm_z(ppg,           ppg_mu, ppg_sigma)

        # Defense: plus/minus positiv (hoch = gut), PIM klein (hoch = schlecht)
        pm_norm     = _norm_z(float(plus_m_val), pm_mu, pm_sigma)
        pimpg_raw   = _norm_z(pimpg, pimpg_mu, pimpg_sigma)   # hoch = viel Strafen
        pimpg_norm  = 1.0 - pimpg_raw                        # invertieren: wenig Strafen = gut

        # Nutzung / Verlässlichkeit
        gp_norm = _norm_z(float(gp), gp_mu, gp_sigma)

        # "Speed": PPG + Nutzung (GP)
        speed_score = 0.6 * ppg_norm + 0.4 * gp_norm

        # Faceoff-Info nur wirklich bei FO-Werten sinnvoll
        if fo_pct is not None and fo_pct_val > 0:
            fopct_norm = _norm_z(fo_pct_val, fo_mu, fo_sigma)
        else:
            fopct_norm = 0.5  # neutral – wird aktuell noch nicht stark gewichtet

        # --------- Gewichtung nach Position ---------
        if pos_group == "D":
            # Verteidiger: Defense wichtiger, Offense etwas abgeschwächt, aber Assists belohnen
            offense_score = 0.25 * g_norm + 0.35 * a_norm + 0.4 * ppg_norm
            defense_score = 0.7 * pm_norm + 0.3 * pimpg_norm
        else:
            # Stürmer
            offense_score = 0.5 * g_norm + 0.3 * p_norm + 0.2 * ppg_norm
            defense_score = 0.5 * pm_norm + 0.5 * pimpg_norm

        # Chemistry: Kombination aus Nutzung, plus/minus und Disziplin
        # (Spieler, die viel spielen, wenig Strafen nehmen und ein gutes +/- haben)
        chem_score = 0.4 * gp_norm + 0.4 * pm_norm + 0.2 * pimpg_norm

        # Gesamtwertung (Overall) – Forwards: Offense größer, D: Defense größer
        if pos_group == "D":
            overall = 0.35 * offense_score + 0.45 * defense_score + 0.20 * speed_score
        else:
            overall = 0.45 * offense_score + 0.30 * defense_score + 0.25 * speed_score

        base["rating_offense"]    = _rating(offense_score)
        base["rating_defense"]    = _rating(defense_score)
        base["rating_speed"]      = _rating(speed_score)
        base["rating_chemistry"]  = _rating(chem_score)
        base["rating_overall"]    = _rating(overall)

        # Log Beispiele für verschiedene Spielertypen
        name = p.get('name_raw', 'Unknown')
        if pos_group == "F" and not logged_forward and points > 30:  # Beispiel Stürmer mit vielen Points
            logged_forward = True
            logging.info(f"Beispiel Stürmer: {name} (F)")
            logging.info(f"  Formel Offense: 0.5 * G_norm + 0.3 * P_norm + 0.2 * PPG_norm")
            logging.info(f"  Rohwerte: Goals={goals}, Assists={assists}, Points={points}, PPG={ppg:.2f}, +/-={plus_m_val}, PIM/G={pimpg:.2f}")
            logging.info(f"  Normiert (Z-Score 0-1): G={g_norm:.3f}, A={a_norm:.3f}, P={p_norm:.3f}, PPG={ppg_norm:.3f}, PM={pm_norm:.3f}, PIM={pimpg_norm:.3f}")
            logging.info(f"  Scores (gewichtet): Offense={offense_score:.3f}, Defense={defense_score:.3f}, Speed={speed_score:.3f}, Chem={chem_score:.3f}, Overall={overall:.3f}")
            logging.info(f"  Ratings (40-99): Off={base['rating_offense']}, Def={base['rating_defense']}, Speed={base['rating_speed']}, Chem={base['rating_chemistry']}, Overall={base['rating_overall']}")
        elif pos_group == "D" and not logged_offensive_d and assists > 20 and plus_m_val > 10:  # Offensiver D
            logged_offensive_d = True
            logging.info(f"Beispiel Offensiver Verteidiger: {name} (D)")
            logging.info(f"  Formel Offense: 0.25 * G_norm + 0.35 * A_norm + 0.4 * PPG_norm (Assists belohnen!)")
            logging.info(f"  Rohwerte: Goals={goals}, Assists={assists}, Points={points}, PPG={ppg:.2f}, +/-={plus_m_val}, PIM/G={pimpg:.2f}")
            logging.info(f"  Normiert (Z-Score 0-1): G={g_norm:.3f}, A={a_norm:.3f}, P={p_norm:.3f}, PPG={ppg_norm:.3f}, PM={pm_norm:.3f}, PIM={pimpg_norm:.3f}")
            logging.info(f"  Scores (gewichtet): Offense={offense_score:.3f}, Defense={defense_score:.3f}, Speed={speed_score:.3f}, Chem={chem_score:.3f}, Overall={overall:.3f}")
            logging.info(f"  Ratings (40-99): Off={base['rating_offense']}, Def={base['rating_defense']}, Speed={base['rating_speed']}, Chem={base['rating_chemistry']}, Overall={base['rating_overall']}")
        elif pos_group == "D" and not logged_defensive_d and plus_m_val > 15 and assists < 10:  # Defensiver D
            logged_defensive_d = True
            logging.info(f"Beispiel Defensiver Verteidiger: {name} (D)")
            logging.info(f"  Formel Defense: 0.7 * PM_norm + 0.3 * PIM_norm (Plus/Minus ist King!)")
            logging.info(f"  Rohwerte: Goals={goals}, Assists={assists}, Points={points}, PPG={ppg:.2f}, +/-={plus_m_val}, PIM/G={pimpg:.2f}")
            logging.info(f"  Normiert (Z-Score 0-1): G={g_norm:.3f}, A={a_norm:.3f}, P={p_norm:.3f}, PPG={ppg_norm:.3f}, PM={pm_norm:.3f}, PIM={pimpg_norm:.3f}")
            logging.info(f"  Scores (gewichtet): Offense={offense_score:.3f}, Defense={defense_score:.3f}, Speed={speed_score:.3f}, Chem={chem_score:.3f}, Overall={overall:.3f}")
            logging.info(f"  Ratings (40-99): Off={base['rating_offense']}, Def={base['rating_defense']}, Speed={base['rating_speed']}, Chem={base['rating_chemistry']}, Overall={base['rating_overall']}")

        rated.append(base)

    return rated



# ----------------- Rating für Goalies -----------------


def build_goalie_ratings(players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    goalies = [p for p in players if p.get("type") == "goalie"]

    gp_list = []
    min_list = []
    gaa_list = []
    svpct_list = []
    shots_list = []
    wins_list = []
    so_list = []

    for g in goalies:
        gp = _to_int(g.get("gp"))
        gp_list.append(float(gp))

        minutes = _to_float(g.get("minutes"))
        min_list.append(minutes)

        # GAA
        gaa = g.get("gaa")
        gaa_val = _to_float(gaa) if gaa is not None else 0.0
        gaa_list.append(gaa_val)

        # Save% – robust: erst sv_pct, sonst save_pct
        sv_src = g.get("sv_pct")
        if sv_src is None:
            sv_src = g.get("save_pct")
        sv_pct_val = _to_float(sv_src) if sv_src is not None else 0.0
        svpct_list.append(sv_pct_val)

        shots_against = _to_int(g.get("shots_against"))
        shots_list.append(float(shots_against))

        wins = _to_int(g.get("wins"))
        wins_list.append(float(wins))

        shutouts = _to_int(g.get("shutouts"))
        so_list.append(float(shutouts))

    gp_min, gp_max = _scale_minmax(gp_list)
    min_min, min_max = _scale_minmax(min_list)
    gaa_min, gaa_max = _scale_minmax(gaa_list)
    sv_min, sv_max = _scale_minmax(svpct_list)
    shots_min, shots_max = _scale_minmax(shots_list)
    wins_min, wins_max = _scale_minmax(wins_list)
    so_min, so_max = _scale_minmax(so_list)

    rated: List[Dict[str, Any]] = []

    goalie_rated: List[Dict[str, Any]] = []

    for g in goalies:
        base = dict(g)

        gp = _to_int(g.get("gp"))
        minutes = _to_float(g.get("minutes"))

        # GAA
        gaa = g.get("gaa")
        gaa_val = _to_float(gaa) if gaa is not None else 0.0

        # Save% – wieder robust lesen
        sv_src = g.get("sv_pct")
        if sv_src is None:
            sv_src = g.get("save_pct")
        sv_pct_val = _to_float(sv_src) if sv_src is not None else 0.0

        shots_against = _to_int(g.get("shots_against"))
        wins = _to_int(g.get("wins"))
        shutouts = _to_int(g.get("shutouts"))

        gp_norm = _norm(float(gp), gp_min, gp_max)
        min_norm = _norm(minutes, min_min, min_max)
        gaa_norm = _norm(gaa_val, gaa_min, gaa_max, invert=True)  # niedriger GAA besser
        sv_norm = _norm(sv_pct_val, sv_min, sv_max)
        shots_norm = _norm(float(shots_against), shots_min, shots_max)
        wins_norm = _norm(float(wins), wins_min, wins_max)
        so_norm = _norm(float(shutouts), so_min, so_max)

        # Offense bei Goalies: symbolisch (Puckhandling / Aktivität)
        offense_score = 0.3 * shots_norm + 0.2 * gp_norm + 0.5 * min_norm

        # Defense: Save% + GAA im Fokus
        defense_score = 0.55 * sv_norm + 0.35 * gaa_norm + 0.10 * shots_norm

        # "Speed": Reaktion / Aktivität
        speed_score = 0.5 * sv_norm + 0.3 * shots_norm + 0.2 * gp_norm

        # Chemistry: Vertrauen → Spiele, Minuten, Wins, Shutouts
        chem_score = 0.35 * gp_norm + 0.35 * min_norm + 0.2 * wins_norm + 0.1 * so_norm

        overall = 0.15 * offense_score + 0.55 * defense_score + 0.30 * speed_score

        base["rating_offense"] = _rating(offense_score)
        base["rating_defense"] = _rating(defense_score)
        base["rating_speed"] = _rating(speed_score)
        base["rating_chemistry"] = _rating(chem_score)
        base["rating_overall"] = _rating(overall)

        # Log Beispiel Goalie
        if len(goalie_rated) == 0:
            name = g.get('name_raw', 'Unknown')
            logging.info(f"Beispiel Goalie: {name} (G)")
            logging.info(f"  Formel Defense: 0.55 * SV%_norm + 0.35 * GAA_norm + 0.10 * Shots_norm (Save% ist entscheidend!)")
            logging.info(f"  Rohwerte: GP={gp}, SV%={sv_pct_val:.3f}, GAA={gaa_val:.2f}, Shots={shots_against}, Wins={wins}, SO={shutouts}")
            logging.info(f"  Normiert (Z-Score 0-1): SV%={sv_norm:.3f}, GAA={gaa_norm:.3f}, Shots={shots_norm:.3f}, GP={gp_norm:.3f}, Min={min_norm:.3f}, Wins={wins_norm:.3f}, SO={so_norm:.3f}")
            logging.info(f"  Scores (gewichtet): Offense={offense_score:.3f}, Defense={defense_score:.3f}, Speed={speed_score:.3f}, Chem={chem_score:.3f}, Overall={overall:.3f}")
            logging.info(f"  Ratings (40-99): Off={base['rating_offense']}, Def={base['rating_defense']}, Speed={base['rating_speed']}, Chem={base['rating_chemistry']}, Overall={base['rating_overall']}")

        # Wichtig: Fangquote sauber in players_rated.json hinterlegen
        base["save_pct"] = sv_pct_val

        goalie_rated.append(base)

    return goalie_rated



# ----------------- Main -----------------


def main() -> None:
    if not BASELINE_FILE.exists():
        print(f"❌ Baseline-Datei fehlt: {BASELINE_FILE}")
        return

    players = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))

    skater_rated = build_skater_ratings(players)
    goalie_rated = build_goalie_ratings(players)

    # Rest (falls irgendwas exotisches drin ist, behalten wir ohne Rating)
    rated_ids = {id(p) for p in skater_rated + goalie_rated}
    others = [p for p in players if p.get("type") not in ("skater", "goalie")]

    all_rated = skater_rated + goalie_rated + others

    OUT_FILE.write_text(json.dumps(all_rated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Ratings gespeichert → {OUT_FILE}")
    print(f"  Skater mit Rating:  {len(skater_rated)}")
    print(f"  Goalies mit Rating: {len(goalie_rated)}")
    print(f"  Andere (unverändert): {len(others)}")

    if skater_rated:
        print("\nBeispiel-Skater:")
        for p in skater_rated[:3]:
            print(
                f" - {p['league']} {p.get('name_real')} "
                f"({p.get('position_group')}) → OVR {p['rating_overall']}"
            )
    if goalie_rated:
        print("\nBeispiel-Goalies:")
        for g in goalie_rated[:3]:
            print(
                f" - {g['league']} {g.get('name_real')} (G) → OVR {g['rating_overall']}"
            )


if __name__ == "__main__":
    main()
