"""
narrative_engine.py

Advanced compositional narrative generation with strong anti-repeat memory.
- Uses compositional sentence structure (PART A + B + C)
- Large token pools for combinatorial variety
- Strong anti-repeat system with narrative_memory.json
- Deterministic output (same input → same text)
- Generates longer, more varied narratives (70–110 chars)
"""

import json
import os
import hashlib
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field


# ============================================================
# TOKEN POOLS - MASSIVELY EXPANDED
# ============================================================

# OPENERS (Context setters)
OPENERS_NEUTRAL = [
    "In einem intensiven Duell",
    "Nach einem umkämpften Spiel",
    "In einer Partie mit klaren Phasen",
    "Nach 60 umkämpften Minuten",
    "In einem Spiel mit wechselnden Momenten",
    "In einer taktisch geprägten Begegnung",
    "Nach einem phasenweise offenen Schlagabtausch",
    "In einem ausgeglichenen Kräftemessen",
    "Nach intensiven 60 Minuten",
    "In einer Partie mit beiden Seiten",
    "Nach einem konzentrierten Auftritt",
    "In einem disziplinierten Spiel",
]

OPENERS_TIGHT = [
    "In einer engen Angelegenheit",
    "In einem Spiel auf Messers Schneide",
    "Nach einem Duell mit minimalen Abständen",
    "In einer Partie, die lange offen blieb",
    "Nach einem nervenaufreibenden Verlauf",
    "In einem Spiel mit knappen Entscheidungen",
    "Nach einem ständigen Hin und Her",
    "In einer ausgeglichenen Partie",
]

OPENERS_DOM = [
    "Von Beginn an",
    "Über weite Strecken",
    "Mit klarer Kontrolle",
    "Mit frühem Zugriff auf das Spiel",
    "Nach souveränem Start",
    "Mit durchgängiger Spielkontrolle",
    "Von der ersten Minute an",
]

OPENERS_DRAMA = [
    "Nach dramatischem Verlauf",
    "In einer spannungsgeladenen Partie",
    "Nach nervenaufreibenden Phasen",
    "In einem packenden Duell",
]

OPENERS_UPSET = [
    "Gegen die Erwartung",
    "Überraschend",
    "In einer unerwarteten Wendung",
    "Gegen den Trend",
]

# VERBS (Core action)
VERBS_WIN = [
    "setzt sich durch",
    "holt sich den Sieg",
    "nimmt die Punkte mit",
    "entscheidet die Partie für sich",
    "bringt das Spiel auf seine Seite",
    "zieht das Match an sich",
    "macht am Ende den Unterschied",
    "sichert sich die Punkte",
    "holt den Erfolg",
    "gewinnt das Duell",
    "triumphiert",
    "setzt sich am Ende durch",
]

VERBS_DRAMA = [
    "entscheidet es",
    "macht Schluss",
    "setzt den entscheidenden Stich",
    "zieht es auf seine Seite",
    "behält die Nerven",
    "packt es",
    "beendet das Drama",
    "setzt das Ausrufezeichen",
]

# ADJECTIVES (Manner/Style)
ADJ_TIGHT = [
    "knapp",
    "hauchdünn",
    "mit Minimalvorsprung",
    "ohne großen Spielraum",
    "in einer engen Entscheidung",
    "mit minimalem Abstand",
    "nach hartem Kampf",
    "in einem engen Finish",
]

ADJ_CLEAR = [
    "souverän",
    "deutlich",
    "kontrolliert",
    "ohne größere Probleme",
    "mit klarer Linie",
    "überzeugend",
    "sicher",
    "solide",
    "routiniert",
]

ADJ_DOM = [
    "dominant",
    "überlegen",
    "eine Klasse zu groß",
    "über weite Strecken spielbestimmend",
    "mit klarer Überlegenheit",
    "nach Belieben",
    "ohne Gegenwehr",
    "mit eindrucksvoller Kontrolle",
]

# QUALIFIERS (Emphasis/Interpretation)
QUALIFIERS_PATIENCE = [
    "und belohnt sich für einen stabilen Auftritt",
    "wobei die Entscheidung erst spät fällt",
    "nachdem das Spiel lange offen blieb",
    "und nutzt die entscheidenden Momente",
    "nach geduldiger Arbeit",
    "und bleibt in kritischen Phasen konzentriert",
]

QUALIFIERS_CONTROL = [
    "und lässt dem Gegner kaum Zugriff",
    "ohne dabei ins Wanken zu geraten",
    "und kontrolliert das Spiel über die gesamte Distanz",
    "mit durchgängiger Spielkontrolle",
    "ohne ernsthafte Gegenwehr zuzulassen",
]

QUALIFIERS_STATEMENT = [
    "und bestätigt damit die eigene Linie",
    "und setzt damit ein klares Zeichen",
    "und unterstreicht die aktuelle Form",
    "und bestätigt die Ambitionen",
    "und sendet eine deutliche Botschaft",
]

QUALIFIERS_NEUTRAL = [
    "und sichert sich wichtige Punkte",
    "und hält die eigene Serie",
    "und nimmt den Schwung mit",
    "und bleibt auf Kurs",
]

# TEMPORAL BITS
TEMPORAL_BITS = [
    "am Ende",
    "im letzten Drittel",
    "nach geduldiger Arbeit",
    "nach frühem Vorteil",
    "mit zunehmender Spielkontrolle",
    "in der Schlussphase",
    "im entscheidenden Moment",
]

# SPECIAL PURPOSE PHRASES
SO_PHRASES = [
    "entscheidet das Penaltyschießen",
    "behält die Nerven im Shootout",
    "setzt den Schlusspunkt im SO",
    "macht es im Penalty-Drama",
    "trifft im entscheidenden Moment beim SO",
]

OT_PHRASES = [
    "entscheidet es in der Verlängerung",
    "macht es in der OT",
    "setzt den Stich in der Overtime",
    "trifft in der Verlängerung",
    "beendet es in der OT",
]

SHUTOUT_PHRASES = [
    "lässt {Loser} ohne Tor stehen",
    "hält {Loser} aus dem Spiel",
    "verteidigt sauber — Shutout",
    "lässt nichts zu gegen {Loser}",
]


# ============================================================
# MEMORY MANAGEMENT (Enhanced)
# ============================================================
@dataclass
class NarrativeMemory:
    """Enhanced memory with stronger anti-repeat."""
    global_recent: List[str] = field(default_factory=list)
    by_pairing: Dict[str, List[str]] = field(default_factory=dict)
    by_type: Dict[str, List[str]] = field(default_factory=dict)
    
    @classmethod
    def load(cls, path: Path) -> 'NarrativeMemory':
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(
                global_recent=data.get('global_recent', []),
                by_pairing=data.get('by_pairing', {}),
                by_type=data.get('by_type', {})
            )
        return cls()

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'global_recent': self.global_recent,
                'by_pairing': self.by_pairing,
                'by_type': self.by_type
            }, f, ensure_ascii=False, indent=2)

    def add_used(self, phrase_hash: str, pair_key: str, ntype: str):
        """Add hash to all tracking buckets."""
        self.global_recent.append(phrase_hash)
        if len(self.global_recent) > 150:
            self.global_recent = self.global_recent[-150:]

        if pair_key not in self.by_pairing:
            self.by_pairing[pair_key] = []
        self.by_pairing[pair_key].append(phrase_hash)
        if len(self.by_pairing[pair_key]) > 25:
            self.by_pairing[pair_key] = self.by_pairing[pair_key][-25:]

        if ntype not in self.by_type:
            self.by_type[ntype] = []
        self.by_type[ntype].append(phrase_hash)
        if len(self.by_type[ntype]) > 40:
            self.by_type[ntype] = self.by_type[ntype][-40:]

    def is_recently_used(self, phrase_hash: str, pair_key: str) -> bool:
        """Check if hash was used recently in global or this pairing."""
        if phrase_hash in self.global_recent[-150:]:
            return True
        if pair_key in self.by_pairing and phrase_hash in self.by_pairing[pair_key]:
            return True
        return False

    def is_globally_recent(self, phrase_hash: str) -> bool:
        """Check if hash is in recent global memory (last 80)."""
        return phrase_hash in self.global_recent[-80:]


# ============================================================
# FORM SCORING
# ============================================================
def form_score(last5: List[str]) -> int:
    """Calculate form score from last 5 results."""
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
    
    Priority order:
    1. SO_DRAMA (shootout)
    2. OT_DRAMA (overtime)
    3. SHUTOUT (winner keeps clean sheet)
    4. DOMINATION (margin >= 5)
    5. UPSET (margin >= 3 and winner has worse form by 3+)
    6. STATEMENT_WIN (margin >= 3)
    7. GRIND_WIN (margin == 1)
    8. TRACK_MEET (total goals >= 7)
    9. LOW_SCORING (total goals <= 3)
    10. FALLBACK
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
# COMPOSITIONAL SENTENCE GENERATION
# ============================================================
def compose_sentence(parts: List[str], punctuation: str = ".") -> str:
    """Compose sentence from parts with proper punctuation."""
    # Filter empty parts
    parts = [p.strip() for p in parts if p and p.strip()]
    
    if not parts:
        return ""
    
    if len(parts) == 1:
        return parts[0] + punctuation
    
    # Multi-part composition
    # Choose structure based on number of parts
    if len(parts) == 2:
        # "{PART_A}, {PART_B}."
        return f"{parts[0]}, {parts[1]}{punctuation}"
    elif len(parts) == 3:
        # "{PART_A}, {PART_B} – {PART_C}."
        return f"{parts[0]}, {parts[1]} – {parts[2]}{punctuation}"
    else:
        # Fallback: comma-separate
        return ", ".join(parts) + punctuation


def generate_candidates_compositional(
    ntype: str,
    winner: str,
    loser: str,
    seed: str,
    count: int = 100
) -> List[Tuple[str, str]]:
    """
    Generate candidate sentences using compositional structure.
    
    Each candidate is built from 2-3 parts:
    - PART A (optional): Context opener
    - PART B (required): Core action/result
    - PART C (optional): Qualifier/interpretation
    
    Returns:
        List of (text, hash) tuples
    """
    # Seed random for deterministic generation
    rng = random.Random(seed)
    candidates = []
    
    # Select token pools based on narrative type
    if ntype == "SO_DRAMA":
        openers = OPENERS_DRAMA + OPENERS_TIGHT + [""]
        core_templates = [f"{{Winner}} {phrase}" for phrase in SO_PHRASES]
        qualifiers = [""] + QUALIFIERS_PATIENCE + [f"{adj} Entscheidung" for adj in ADJ_TIGHT]
        
    elif ntype == "OT_DRAMA":
        openers = OPENERS_DRAMA + OPENERS_TIGHT + [""]
        core_templates = [f"{{Winner}} {phrase}" for phrase in OT_PHRASES]
        qualifiers = [""] + QUALIFIERS_PATIENCE + [f"{adj} Drama" for adj in ADJ_TIGHT]
        
    elif ntype == "SHUTOUT":
        openers = OPENERS_DOM + OPENERS_NEUTRAL + [""]
        core_templates = [f"{{Winner}} {phrase}" for phrase in SHUTOUT_PHRASES]
        qualifiers = [""] + QUALIFIERS_CONTROL + ["ohne Gegentor", "saubere Defensive"]
        
    elif ntype == "DOMINATION":
        openers = OPENERS_DOM + [""]
        core_templates = [f"{{Winner}} {verb} {adj}" for verb in VERBS_WIN for adj in ADJ_DOM]
        qualifiers = [""] + QUALIFIERS_CONTROL + QUALIFIERS_STATEMENT
        
    elif ntype == "STATEMENT_WIN":
        openers = OPENERS_DOM + OPENERS_NEUTRAL + [""]
        core_templates = [f"{{Winner}} {verb} {adj}" for verb in VERBS_WIN for adj in ADJ_CLEAR]
        qualifiers = [""] + QUALIFIERS_STATEMENT + QUALIFIERS_CONTROL
        
    elif ntype == "UPSET":
        openers = OPENERS_UPSET + OPENERS_NEUTRAL
        core_templates = [f"{{Winner}} {verb} gegen {{Loser}}" for verb in VERBS_WIN]
        qualifiers = [""] + ["und überrascht"] + QUALIFIERS_STATEMENT
        
    elif ntype == "GRIND_WIN":
        openers = OPENERS_TIGHT + OPENERS_NEUTRAL + [""]
        core_templates = [f"{{Winner}} {verb} {adj}" for verb in VERBS_WIN for adj in ADJ_TIGHT]
        qualifiers = [""] + QUALIFIERS_PATIENCE
        
    elif ntype == "TRACK_MEET":
        openers = ["Nach offenem Schlagabtausch", "In einer Torschlacht"] + OPENERS_NEUTRAL + [""]
        core_templates = [f"{{Winner}} {verb} {adj}" for verb in VERBS_WIN for adj in ADJ_CLEAR + ADJ_TIGHT]
        qualifiers = [""] + ["in einem Spektakel", "nach Torfestival"]
        
    elif ntype == "LOW_SCORING":
        openers = ["In einer zähen Partie", "Nach defensivem Kampf"] + OPENERS_TIGHT + [""]
        core_templates = [f"{{Winner}} {verb} {adj}" for verb in VERBS_WIN for adj in ADJ_TIGHT]
        qualifiers = [""] + QUALIFIERS_PATIENCE + ["defensiv stark"]
        
    else:  # FALLBACK
        openers = OPENERS_NEUTRAL + [""]
        core_templates = [f"{{Winner}} {verb} {adj}" for verb in VERBS_WIN for adj in ADJ_CLEAR]
        qualifiers = [""] + QUALIFIERS_NEUTRAL
    
    # Generate candidates
    for _ in range(count):
        parts = []
        
        # PART A (opener) - 50% chance to include (increased from 40%)
        if rng.random() < 0.5:
            opener = rng.choice(openers)
            if opener:
                parts.append(opener)
        
        # PART B (core) - always included
        core = rng.choice(core_templates)
        core = core.replace("{Winner}", winner).replace("{Loser}", loser)
        parts.append(core)
        
        # PART C (qualifier) - 60% chance to include (increased from 50%)
        if rng.random() < 0.6:
            qualifier = rng.choice(qualifiers)
            if qualifier:
                parts.append(qualifier)
        
        # Optional: add temporal bit (15% chance, reduced from 20%)
        if rng.random() < 0.15 and TEMPORAL_BITS:
            temporal = rng.choice(TEMPORAL_BITS)
            # Insert before last part if exists
            if len(parts) > 1:
                parts.insert(-1, temporal)
            else:
                parts.append(temporal)
        
        # Compose sentence
        text = compose_sentence(parts)
        
        # Truncate if too long
        if len(text) > 110:
            # Find word boundary
            text = text[:107]
            last_space = text.rfind(' ')
            if last_space > 70:
                text = text[:last_space] + "…"
            else:
                text = text + "…"
        
        # Generate hash
        phrase_hash = hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]
        candidates.append((text, phrase_hash))
    
    return candidates


def select_best_candidate(
    candidates: List[Tuple[str, str]],
    memory: NarrativeMemory,
    pair_key: str,
    ntype: str,
    used_openers: Set[str],
    used_adjectives: Set[str],
    seed: str
) -> Tuple[str, str]:
    """
    Select best candidate with strong anti-repeat and deterministic scoring.
    
    Selection strategy:
    1. Filter out recently used (global + pairing)
    2. If empty, allow type repeats
    3. If still empty, allow older global repeats (>80)
    4. Score remaining candidates
    5. Pick lowest (score, hash) deterministically
    """
    # Phase 1: Strict filtering
    available = [
        (text, h) for text, h in candidates 
        if not memory.is_recently_used(h, pair_key)
    ]
    
    # Phase 2: Relax if needed
    if not available:
        available = [
            (text, h) for text, h in candidates 
            if not memory.is_globally_recent(h)
        ]
    
    # Phase 3: Allow anything (fallback)
    if not available:
        available = candidates
    
    # Score candidates
    scored = []
    for text, h in available:
        score = 0.0
        
        # Prefer length between 70-100 chars
        length = len(text)
        if length < 70:
            score += (70 - length) * 0.5
        elif length > 100:
            score += (length - 100) * 0.5
        
        # Penalize same opening word as used in this matchday
        opener = text.lower().split()[0] if text else ""
        if opener in used_openers:
            score += 15.0
        
        # Penalize reused adjectives (simple detection)
        words = text.lower().split()
        for adj_set in [ADJ_TIGHT, ADJ_CLEAR, ADJ_DOM]:
            for adj in adj_set:
                adj_lower = adj.lower()
                if adj_lower in words and adj_lower in used_adjectives:
                    score += 10.0
        
        # Add hash for deterministic tie-breaking
        scored.append((score, h, text))
    
    # Sort deterministically
    scored.sort(key=lambda x: (x[0], x[1]))
    
    best_score, best_hash, best_text = scored[0]
    return best_text, best_hash


# ============================================================
# MAIN GENERATION
# ============================================================
def generate_line1(
    match: Dict[str, Any],
    ctx: Dict[str, Any],
    memory: NarrativeMemory,
    used_openers: Set[str],
    used_adjectives: Set[str]
) -> str:
    """
    Generate line1 with compositional structure and anti-repeat.
    
    Args:
        match: Match dict with home, away, g_home, g_away, overtime, shootout
        ctx: Context dict with season, spieltag, home_last5, away_last5
        memory: NarrativeMemory instance
        used_openers: Set of opening words used in this matchday
        used_adjectives: Set of adjectives used in this matchday
    
    Returns:
        Generated line1 text (70-110 chars)
    """
    home = match['home']
    away = match['away']
    pair_key = f"{home}-{away}"

    # Classify narrative type
    home_form = form_score(ctx.get('home_last5', []))
    away_form = form_score(ctx.get('away_last5', []))
    ntype = classify_narrative(match, home_form, away_form)

    # Determine winner/loser
    if match['g_home'] > match['g_away']:
        winner, loser = home, away
    elif match['g_away'] > match['g_home']:
        winner, loser = away, home
    else:
        # Tie - shouldn't happen in hockey but handle gracefully
        winner, loser = home, away

    # Build deterministic seed
    seed = f"{ctx['season']}-{ctx['spieltag']}-{home}-{away}-{match['g_home']}-{match['g_away']}-{ntype}"

    # Generate candidates (more for better variety)
    candidates = generate_candidates_compositional(ntype, winner, loser, seed, count=150)

    # Select best
    text, phrase_hash = select_best_candidate(
        candidates, memory, pair_key, ntype, used_openers, used_adjectives, seed
    )

    # Update memory
    memory.add_used(phrase_hash, pair_key, ntype)

    # Update matchday-level tracking
    opener = text.lower().split()[0] if text else ""
    if opener:
        used_openers.add(opener)
    
    # Track adjectives
    words = text.lower().split()
    for adj_set in [ADJ_TIGHT, ADJ_CLEAR, ADJ_DOM]:
        for adj in adj_set:
            if adj.lower() in words:
                used_adjectives.add(adj.lower())

    return text


def build_narratives_for_matchday(
    spieltag_json: Dict[str, Any],
    latest_json: Dict[str, Any],
    season: int = 1,
    spieltag: int = 1,
    memory_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build narratives for all matches in a matchday.
    
    Args:
        spieltag_json: JSON with 'games' list
        latest_json: JSON with team data. Supports two formats:
            - New format: {'teams': {'TeamName': {'last5': [...]}}}
            - Old format: {'tabelle_nord': [...], 'tabelle_sued': [...]}
        season: Season number
        spieltag: Matchday number
        memory_path: Optional path to narrative_memory.json
    
    Returns:
        Dict[pair_key, {'line1': str, 'line2': str}]
    """
    # Determine effective spieltag (prefer value from spieltag_json if present)
    try:
        effective_spieltag = int(spieltag_json.get('spieltag', spieltag))
    except Exception:
        effective_spieltag = spieltag

    # Default memory path: under HIGHSPEED_DATA_ROOT if available, else local replays/
    if memory_path is None:
        data_root_env = os.environ.get('HIGHSPEED_DATA_ROOT')
        if data_root_env:
            base_replays = Path(data_root_env).resolve() / "replays"
        else:
            # Prefer system data repo if available
            sys_data_root = Path("/opt/highspeed/data")
            if sys_data_root.exists():
                base_replays = sys_data_root / "replays"
            else:
                # Fallback to local repo if nothing else is available
                base_replays = Path("replays")
        memory_path = base_replays / f"saison_{season:02d}" / f"spieltag_{effective_spieltag:02d}" / "narrative_memory.json"

    memory = NarrativeMemory.load(memory_path)
    used_openers: Set[str] = set()
    used_adjectives: Set[str] = set()

    # Convert old format to new format if needed
    teams_dict = latest_json.get('teams', {})
    if isinstance(teams_dict, list):
        # If 'teams' is a list, convert to dict
        temp_dict = {}
        for item in teams_dict:
            if isinstance(item, dict):
                team_name = item.get('Team', '')
                if team_name:
                    temp_dict[team_name] = {'last5': item.get('last5', [])}
        teams_dict = temp_dict
    if not teams_dict and ('tabelle_nord' in latest_json or 'tabelle_sued' in latest_json):
        # Old format - convert
        teams_dict = {}
        for table in [latest_json.get('tabelle_nord', []), latest_json.get('tabelle_sued', [])]:
            for team_entry in table:
                team_name = team_entry.get('Team', '')
                if team_name:
                    teams_dict[team_name] = {'last5': team_entry.get('last5', [])}
    # If still not found, try from spieltag_json
    if not teams_dict:
        for table in [spieltag_json.get('tabelle_nord', []), spieltag_json.get('tabelle_sued', [])]:
            for team_entry in table:
                team_name = team_entry.get('Team', '')
                if team_name:
                    teams_dict[team_name] = {'last5': team_entry.get('last5', [])}
    # Support both structures: 'games' (new) and 'results' (legacy)
    matches_list = spieltag_json.get('games', [])
    if not matches_list:
        matches_list = spieltag_json.get('results', [])

    narratives = {}
    for match in matches_list:
        home = match['home']
        away = match['away']
        pair_key = f"{home}-{away}"

        # Build context
        ctx = {
            'season': season,
            'spieltag': effective_spieltag,
            'home_last5': (teams_dict.get(home, {}) if isinstance(teams_dict, dict) else {}).get('last5', []),
            'away_last5': (teams_dict.get(away, {}) if isinstance(teams_dict, dict) else {}).get('last5', []),
        }

        line1 = generate_line1(match, ctx, memory, used_openers, used_adjectives)
        narratives[pair_key] = {
            'line1': line1,
            'line2': '',  # Keep empty per schema
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(narratives, f, ensure_ascii=False, indent=2)


# ============================================================
# VALIDATION & DEBUG
# ============================================================
def validate_diversity(sample_count: int = 300, verbose: bool = True) -> Dict[str, Any]:
    """
    Validation mode: Generate many samples and check duplicate rate.
    
    Args:
        sample_count: Number of samples to generate
        verbose: Print detailed output
    
    Returns:
        Dict with statistics
    """
    # Create mock data
    teams = ["Team A", "Team B", "Team C", "Team D"]
    narrative_types = [
        "SO_DRAMA", "OT_DRAMA", "SHUTOUT", "DOMINATION", 
        "STATEMENT_WIN", "UPSET", "GRIND_WIN", "TRACK_MEET", 
        "LOW_SCORING", "FALLBACK"
    ]
    
    memory = NarrativeMemory()
    all_texts = []
    all_hashes = []
    type_counts = {nt: 0 for nt in narrative_types}
    
    if verbose:
        print(f"🔬 Generating {sample_count} sample narratives...")
        print("=" * 60)
    
    for i in range(sample_count):
        # Random matchup
        winner = teams[i % len(teams)]
        loser = teams[(i + 1) % len(teams)]
        ntype = narrative_types[i % len(narrative_types)]
        seed = f"validation-{i}-{ntype}"
        
        # Generate
        candidates = generate_candidates_compositional(ntype, winner, loser, seed, count=50)
        text, phrase_hash = candidates[0] if candidates else ("", "")
        
        all_texts.append(text)
        all_hashes.append(phrase_hash)
        type_counts[ntype] += 1
        
        if verbose and i < 20:
            print(f"{i+1:3d}. [{ntype:14s}] {text}")
    
    # Calculate statistics
    unique_texts = len(set(all_texts))
    unique_hashes = len(set(all_hashes))
    duplicate_rate = (1 - unique_texts / sample_count) * 100 if sample_count > 0 else 0
    
    avg_length = sum(len(t) for t in all_texts) / len(all_texts) if all_texts else 0
    min_length = min(len(t) for t in all_texts) if all_texts else 0
    max_length = max(len(t) for t in all_texts) if all_texts else 0
    
    stats = {
        'total_samples': sample_count,
        'unique_texts': unique_texts,
        'unique_hashes': unique_hashes,
        'duplicate_rate': duplicate_rate,
        'avg_length': avg_length,
        'min_length': min_length,
        'max_length': max_length,
        'type_distribution': type_counts,
    }
    
    if verbose:
        print("=" * 60)
        print(f"\n📊 VALIDATION RESULTS:")
        print(f"   Total samples: {sample_count}")
        print(f"   Unique texts:  {unique_texts}")
        print(f"   Duplicate rate: {duplicate_rate:.2f}%")
        print(f"   Target: <2%")
        print(f"\n📏 LENGTH STATISTICS:")
        print(f"   Average: {avg_length:.1f} chars")
        print(f"   Min:     {min_length} chars")
        print(f"   Max:     {max_length} chars")
        print(f"   Target:  70-110 chars")
        
        if duplicate_rate < 2.0:
            print(f"\n✅ PASS: Duplicate rate under 2%")
        else:
            print(f"\n⚠️  WARNING: Duplicate rate above 2%")
    
    return stats


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--validate":
        # Run validation
        validate_diversity(sample_count=300, verbose=True)
    else:
        # Quick test
        print("🎯 Testing compositional narrative generation...\n")
        
        match = {
            'home': 'Eisbären Berlin',
            'away': 'Adler Mannheim',
            'g_home': 4,
            'g_away': 2,
            'overtime': False,
            'shootout': False
        }
        
        ctx = {
            'season': 1,
            'spieltag': 1,
            'home_last5': ['W', 'W', 'L', 'W'],
            'away_last5': ['L', 'L', 'W', 'L']
        }
        
        memory = NarrativeMemory()
        used_openers = set()
        used_adjectives = set()
        
        print("Generating 10 sample narratives:")
        print("=" * 60)
        
        for i in range(10):
            line1 = generate_line1(match, ctx, memory, used_openers, used_adjectives)
            print(f"{i+1:2d}. {line1}")
        
        print("\n✅ Test completed successfully!")
