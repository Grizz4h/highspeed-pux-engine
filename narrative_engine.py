"""
narrative_engine.py

Advanced deterministic narrative generation with anti-repeat memory.
- Uses token pools and template families for high variety
- Implements phrase memory to avoid recent repeats
- Generates one-liner narratives (≤78 chars) for match graphics
"""

import json
import hashlib
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


# ============================================================
# TOKEN POOLS
# ============================================================
VERBS_WIN = ["setzt sich durch", "holt den Sieg", "nimmt die Punkte", "zieht das Spiel", "entscheidet die Partie", "macht den Unterschied", "bringt's ins Ziel", "dreht das Ding"]
VERBS_DRAMA = ["entscheidet es", "macht Schluss", "setzt den Stich", "zieht's auf seine Seite", "behält die Nerven", "packt es"]
ADJ_TIGHT = ["knapp", "hauchdünn", "mit Minimalvorsprung", "auf Messers Schneide", "in einer engen Kiste"]
ADJ_CLEAR = ["souverän", "deutlich", "ohne Wackler", "kontrolliert", "mit Ansage", "klar"]
ADJ_DOM = ["dominant", "überlegen", "nach Belieben", "gnadenlos", "eine Klasse zu groß"]
NOUN_DUEL = ["Duell", "Partie", "Match", "Spiel", "Abend", "Aufeinandertreffen"]
ENDINGS = ["— Punkt.", "— fertig.", "— ohne Diskussion.", "— und zwar jetzt.", "— sauber."]
STYLE_BITS = ["spät", "früh", "konsequent", "abgezockt", "eiskalt", "cool", "ruhig", "präzise"]

# Capitalized versions
ADJ_TIGHT_CAP = [w.capitalize() for w in ADJ_TIGHT]
ADJ_CLEAR_CAP = [w.capitalize() for w in ADJ_CLEAR]
ADJ_DOM_CAP = [w.capitalize() for w in ADJ_DOM]


# ============================================================
# TEMPLATE FAMILIES
# ============================================================
TEMPLATE_FAMILIES: Dict[str, List[str]] = {
    "SO_DRAMA": [
        "{Winner} {VERB_DRAMA} im Shootout.",
        "{Winner} entscheidet das Penaltyschießen {ADJ_TIGHT}.",
        "Shootout-Drama: {Winner} {VERB_DRAMA}.",
        "{Winner} trifft im SO — {ADJ_TIGHT}.",
        "Penalty-Show: {Winner} {VERB_DRAMA} {ADJ_TIGHT}.",
        "{ADJ_TIGHT_cap} Entscheidung: {Winner} im Shootout.",
        "{Winner} behält {STYLE_BITS} die Nerven im SO.",
        "{Winner} {VERB_DRAMA} — Shootout-Sieg.",
        "Spannung pur: {Winner} im Penaltyschießen.",
        "{Winner} setzt den Schlusspunkt im SO.",
    ],
    "OT_DRAMA": [
        "{Winner} {VERB_DRAMA} in der Verlängerung.",
        "Overtime-Thriller: {Winner} {VERB_WIN}.",
        "{Winner} treffsicher in der OT {ADJ_TIGHT}.",
        "Verlängerung bringt Entscheidung: {Winner}.",
        "{Winner} {VERB_DRAMA} — OT-Sieg.",
        "{ADJ_TIGHT_cap} OT: {Winner} {VERB_WIN}.",
        "{Winner} packt es in der Verlängerung.",
        "Drama in der OT: {Winner} {VERB_DRAMA}.",
        "{Winner} behält Nerven in der Verlängerung.",
        "{Winner} setzt Stich in der OT.",
    ],
    "SHUTOUT": [
        "{Winner} shutout {Loser} {ADJ_CLEAR}.",
        "{Winner} lässt {Loser} ohne Tor stehen.",
        "Defensive Meisterleistung: {Winner} shutout.",
        "{Winner} hält {Loser} {STYLE_BITS} aus dem Spiel.",
        "Torhüter-Show: {Winner} shutout gegen {Loser}.",
        "{ADJ_CLEAR_cap} Shutout: {Winner} gegen {Loser}.",
        "{Winner} {VERB_WIN} ohne Gegentor.",
        "{Winner} verteidigt {ADJ_CLEAR} — Shutout.",
        "{Loser} findet kein Mittel gegen {Winner}.",
        "{Winner} {VERB_WIN} — sauberer Shutout.",
    ],
    "DOMINATION": [
        "{Winner} ist {ADJ_DOM} und {VERB_WIN}.",
        "Einseitiges {NOUN_DUEL}: {Winner} {VERB_WIN} {ADJ_CLEAR}.",
        "{Winner} {VERB_WIN} — {ADJ_DOM}.",
        "{ADJ_DOM_cap} Leistung: {Winner} {VERB_WIN}.",
        "{Winner} dominiert {NOUN_DUEL} {ADJ_CLEAR}.",
        "{Loser} hat keine Chance gegen {Winner}.",
        "{Winner} {VERB_WIN} {ADJ_DOM}.",
        "Überlegenheit pur: {Winner} gegen {Loser}.",
        "{Winner} zeigt {ADJ_DOM} Spiel.",
        "{Winner} {VERB_WIN} — gnadenlos.",
    ],
    "STATEMENT_WIN": [
        "{Winner} {VERB_WIN} {ADJ_CLEAR}.",
        "{Winner} setzt Ausrufezeichen — {ADJ_CLEAR}.",
        "Statement-Sieg: {Winner} {VERB_WIN}.",
        "{Winner} {VERB_WIN} {ADJ_CLEAR} — {ADJ_CLEAR_2}.",
        "{ADJ_CLEAR_cap} Sieg: {Winner} gegen {Loser}.",
        "{Winner} beeindruckt {ADJ_CLEAR}.",
        "{Winner} {VERB_WIN} ohne Wenn und Aber.",
        "{Winner} gibt {ADJ_CLEAR} Antwort.",
        "{Winner} {VERB_WIN} — kontrolliert.",
        "{Winner} setzt Zeichen {ADJ_CLEAR}.",
    ],
    "UPSET": [
        "{Winner} überrascht {Loser} {ADJ_TIGHT}.",
        "Sensation: {Winner} {VERB_WIN} gegen {Loser}.",
        "{Winner} stoppt Formhoch von {Loser}.",
        "Upset pur: {Winner} {VERB_DRAMA}.",
        "{Winner} zieht Überraschung — {ADJ_TIGHT}.",
        "{ADJ_TIGHT_cap} Upset: {Winner} gegen {Loser}.",
        "{Winner} {VERB_WIN} — unerwartet.",
        "{Loser} stolpert über {Winner}.",
        "{Winner} nutzt Schwäche von {Loser}.",
        "{Winner} {VERB_DRAMA} — Upset.",
    ],
    "GRIND_WIN": [
        "{Winner} {VERB_WIN} {ADJ_TIGHT}.",
        "{ADJ_TIGHT_cap} {NOUN_DUEL}: {Winner} {VERB_WIN}.",
        "{Winner} bleibt stabil und {VERB_WIN} {ADJ_TIGHT}.",
        "{Winner} {VERB_DRAMA} — knapp.",
        "Harter Kampf: {Winner} {VERB_WIN} {ADJ_TIGHT}.",
        "{Winner} setzt sich {ADJ_TIGHT} durch.",
        "{ADJ_TIGHT_cap} Entscheidung: {Winner} {VERB_WIN}.",
        "{Winner} behält Nerven {ADJ_TIGHT}.",
        "{Winner} {VERB_WIN} — hauchdünn.",
        "{Winner} packt es {ADJ_TIGHT}.",
    ],
    "TRACK_MEET": [
        "{Winner} und {Loser} liefern Tor-Feuerwerk.",
        "Offensive Schlacht: {Winner} {VERB_WIN}.",
        "{Winner} gewinnt Tor-Schlacht {ADJ_CLEAR}.",
        "Spektakel pur: {Winner} gegen {Loser}.",
        "{Winner} {VERB_WIN} in hohem Score.",
        "Tor-Rekord: {Winner} {VERB_WIN}.",
        "{Winner} und {Loser} sorgen für Spektakel.",
        "{Winner} {VERB_WIN} — torreich.",
        "Offensive Show: {Winner} triumphiert.",
        "{Winner} {VERB_WIN} in Tor-Orgie.",
    ],
    "LOW_SCORING": [
        "{Winner} {VERB_WIN} in zähem {NOUN_DUEL}.",
        "Defensive Schlacht: {Winner} {VERB_DRAMA}.",
        "{Winner} behält Nervenkostüm {ADJ_TIGHT}.",
        "Zähes Spiel: {Winner} {VERB_WIN}.",
        "{Winner} {VERB_WIN} — defensiv stark.",
        "{ADJ_TIGHT_cap} Duell: {Winner} {VERB_WIN}.",
        "{Winner} setzt sich in defensivem {NOUN_DUEL} durch.",
        "{Winner} {VERB_DRAMA} — zäh.",
        "Nervenkrieg: {Winner} {VERB_WIN}.",
        "{Winner} {VERB_WIN} — kontrolliert defensiv.",
    ],
    "FALLBACK": [
        "{Winner} {VERB_WIN} gegen {Loser}.",
        "{Winner} schlägt {Loser} {ADJ_CLEAR}.",
        "{Winner} {VERB_WIN} — solide.",
        "{ADJ_CLEAR_cap} Sieg: {Winner}.",
        "{Winner} triumphiert über {Loser}.",
        "{Winner} {VERB_WIN} — verdient.",
        "{Winner} setzt sich gegen {Loser} durch.",
        "{Winner} {VERB_WIN} — überzeugend.",
        "{Winner} bezwingt {Loser} {ADJ_CLEAR}.",
        "{Winner} {VERB_WIN} — stark.",
    ],
}


# ============================================================
# MEMORY MANAGEMENT
# ============================================================
@dataclass
class NarrativeMemory:
    global_recent: List[str] = None
    by_pairing: Dict[str, List[str]] = None
    by_type: Dict[str, List[str]] = None

    def __post_init__(self):
        if self.global_recent is None:
            self.global_recent = []
        if self.by_pairing is None:
            self.by_pairing = {}
        if self.by_type is None:
            self.by_type = {}

    @classmethod
    def load(cls, path: Path) -> 'NarrativeMemory':
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    def save(self, path: Path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'global_recent': self.global_recent,
                'by_pairing': self.by_pairing,
                'by_type': self.by_type
            }, f, ensure_ascii=False, indent=2)

    def add_used(self, phrase_hash: str, pair_key: str, ntype: str):
        self.global_recent.append(phrase_hash)
        if len(self.global_recent) > 120:
            self.global_recent = self.global_recent[-120:]

        if pair_key not in self.by_pairing:
            self.by_pairing[pair_key] = []
        self.by_pairing[pair_key].append(phrase_hash)
        if len(self.by_pairing[pair_key]) > 20:
            self.by_pairing[pair_key] = self.by_pairing[pair_key][-20:]

        if ntype not in self.by_type:
            self.by_type[ntype] = []
        self.by_type[ntype].append(phrase_hash)
        if len(self.by_type[ntype]) > 40:
            self.by_type[ntype] = self.by_type[ntype][-40:]

    def is_used(self, phrase_hash: str, pair_key: str, ntype: str) -> bool:
        if phrase_hash in self.global_recent:
            return True
        if pair_key in self.by_pairing and phrase_hash in self.by_pairing[pair_key]:
            return True
        if ntype in self.by_type and phrase_hash in self.by_type[ntype]:
            return True
        return False


# ============================================================
# FORM SCORING
# ============================================================
def form_score(last5: List[str]) -> int:
    score = 0
    for result in last5:
        if result and len(result) > 0:
            first_char = str(result).upper()[0]
            if first_char == "W":
                score += 1
            elif first_char == "L":
                score -= 1
    return score


# ============================================================
# CLASSIFICATION
# ============================================================
def classify_narrative(match: Dict[str, Any], home_form: int, away_form: int) -> str:
    """
    Classify match narrative type based on priorities.
    
    Args:
        match: Dict with home, away, g_home, g_away, overtime, shootout
        home_form: Form score of home team
        away_form: Form score of away team
    
    Returns:
        str: Narrative type (SO_DRAMA, OT_DRAMA, SHUTOUT, etc.)
    """
    g_home = match.get("g_home", 0)
    g_away = match.get("g_away", 0)
    overtime = match.get("overtime", False)
    shootout = match.get("shootout", False)
    
    if g_home > g_away:
        winner_form = home_form
        loser_form = away_form
        winner_goals = g_home
        loser_goals = g_away
    elif g_away > g_home:
        winner_form = away_form
        loser_form = home_form
        winner_goals = g_away
        loser_goals = g_home
    else:
        if shootout:
            return "SO_DRAMA"
        if overtime:
            return "OT_DRAMA"
        return "FALLBACK"
    
    margin = winner_goals - loser_goals
    form_diff = winner_form - loser_form
    total_goals = g_home + g_away
    
    if shootout:
        return "SO_DRAMA"
    if overtime:
        return "OT_DRAMA"
    if loser_goals == 0:
        return "SHUTOUT"
    if margin >= 5:
        return "DOMINATION"
    if margin >= 3:
        if form_diff <= -3:
            return "UPSET"
        return "STATEMENT_WIN"
    if form_diff <= -3:
        return "UPSET"
    if margin == 1:
        return "GRIND_WIN"
    if total_goals >= 7:
        return "TRACK_MEET"
    if total_goals <= 3:
        return "LOW_SCORING"
    return "FALLBACK"


# ============================================================
# TEMPLATE EXPANSION
# ============================================================
def expand_template(template: str, match_ctx: Dict[str, Any]) -> str:
    """Expand template with tokens and context."""
    text = template

    # Replace context variables
    for key, value in match_ctx.items():
        text = text.replace(f"{{{key}}}", str(value))

    # Replace token pools
    replacements = {
        "{VERB_WIN}": random.choice(VERBS_WIN),
        "{VERB_DRAMA}": random.choice(VERBS_DRAMA),
        "{ADJ_TIGHT}": random.choice(ADJ_TIGHT),
        "{ADJ_TIGHT_cap}": random.choice(ADJ_TIGHT_CAP),
        "{ADJ_CLEAR}": random.choice(ADJ_CLEAR),
        "{ADJ_CLEAR_cap}": random.choice(ADJ_CLEAR_CAP),
        "{ADJ_CLEAR_2}": random.choice(ADJ_CLEAR),
        "{ADJ_DOM}": random.choice(ADJ_DOM),
        "{ADJ_DOM_cap}": random.choice(ADJ_DOM_CAP),
        "{NOUN_DUEL}": random.choice(NOUN_DUEL),
        "{STYLE_BITS}": random.choice(STYLE_BITS),
    }

    for token, replacement in replacements.items():
        text = text.replace(token, replacement)

    # Truncate to 78 chars
    if len(text) > 78:
        text = text[:75] + "…"

    return text


def generate_candidates(ntype: str, match_ctx: Dict[str, Any], count: int = 50) -> List[Tuple[str, str]]:
    """Generate candidate phrases with hashes."""
    candidates = []
    templates = TEMPLATE_FAMILIES.get(ntype, TEMPLATE_FAMILIES["FALLBACK"])

    for _ in range(count):
        template = random.choice(templates)
        text = expand_template(template, match_ctx)
        phrase_hash = hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]
        candidates.append((text, phrase_hash))

    return candidates


def select_best_candidate(candidates: List[Tuple[str, str]], memory: NarrativeMemory, pair_key: str, ntype: str, used_openers: set, seed: str) -> Tuple[str, str]:
    """Select best candidate avoiding repeats."""
    # Filter out used
    available = [(text, h) for text, h in candidates if not memory.is_used(h, pair_key, ntype)]

    if not available:
        # Relax: allow type repeats
        available = [(text, h) for text, h in candidates if not memory.is_used(h, pair_key, "") and not memory.is_used(h, "", "")]

    if not available:
        # Relax more: allow global older than 60
        recent_hashes = set(memory.global_recent[-60:])
        available = [(text, h) for text, h in candidates if h not in recent_hashes]

    if not available:
        # Allow anything
        available = candidates

    # Score candidates
    scored = []
    for text, h in available:
        score = len(text)  # Shorter better
        if any(ending in text for ending in ENDINGS):
            score += 10  # Penalize endings
        opener = text.lower().split()[0]
        if opener in used_openers:
            score += 5  # Penalize same opener
        scored.append((score, h, text))

    # Deterministic sort
    scored.sort(key=lambda x: (x[0], x[1]))

    best_text, best_hash = scored[0][2], scored[0][1]
    return best_text, best_hash


# ============================================================
# MAIN GENERATION
# ============================================================
def generate_line1(match: Dict[str, Any], ctx: Dict[str, Any], memory: NarrativeMemory, used_openers: set) -> str:
    """Generate line1 with anti-repeat."""
    home = match['home']
    away = match['away']
    pair_key = f"{home}-{away}"

    # Classify
    home_form = form_score(ctx.get('home_last5', []))
    away_form = form_score(ctx.get('away_last5', []))
    ntype = classify_narrative(match, home_form, away_form)

    # Context
    if match['g_home'] > match['g_away']:
        winner, loser = home, away
    else:
        winner, loser = away, home

    match_ctx = {
        'Winner': winner,
        'Loser': loser,
        'Home': home,
        'Away': away,
    }

    # Candidates
    candidates = generate_candidates(ntype, match_ctx)

    # Select
    seed = f"{ctx['season']}-{ctx['spieltag']}-{home}-{away}-{match['g_home']}-{match['g_away']}"
    text, phrase_hash = select_best_candidate(candidates, memory, pair_key, ntype, used_openers, seed)

    # Update memory
    memory.add_used(phrase_hash, pair_key, ntype)

    # Update openers
    opener = text.lower().split()[0]
    used_openers.add(opener)

    return text


def build_narratives_for_matchday(
    spieltag_json: Dict[str, Any],
    latest_json: Dict[str, Any],
    season: int = 1,
    spieltag: int = 1,
    memory_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build narratives with memory."""
    if memory_path is None:
        memory_path = Path(f"replays/saison_{season:02d}/spieltag_{spieltag:02d}/narrative_memory.json")

    memory = NarrativeMemory.load(memory_path)
    used_openers = set()

    narratives = {}
    for match in spieltag_json.get('games', []):
        home = match['home']
        away = match['away']
        pair_key = f"{home}-{away}"

        # Context
        ctx = {
            'season': season,
            'spieltag': spieltag,
            'home_last5': latest_json.get('teams', {}).get(home, {}).get('last5', []),
            'away_last5': latest_json.get('teams', {}).get(away, {}).get('last5', []),
        }

        line1 = generate_line1(match, ctx, memory, used_openers)
        narratives[pair_key] = {
            'line1': line1,
            'line2': '',  # Keep empty as per schema
        }

    # Save memory
    memory.save(memory_path)

    return narratives


def write_narratives_json(narratives: Dict[str, Dict[str, Any]], output_path: Path):
    """
    Write narratives dict to JSON file.
    
    Args:
        narratives: Dict from build_narratives_for_matchday
        output_path: Path to write narratives.json
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(narratives, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Example usage
    match = {'home': 'TeamA', 'away': 'TeamB', 'g_home': 3, 'g_away': 1, 'overtime': False, 'shootout': False}
    ctx = {'season': 1, 'spieltag': 1, 'home_last5': ['W', 'W', 'L'], 'away_last5': ['L', 'L', 'W']}
    memory = NarrativeMemory()
    used_openers = set()
    line1 = generate_line1(match, ctx, memory, used_openers)
    print(line1)
