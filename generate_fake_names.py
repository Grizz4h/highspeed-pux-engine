import json
import re
from pathlib import Path
from collections import defaultdict

PLAYERS_FILE = Path("data") / "players_rated.json"
MAPPING_FILE = Path("data") / "mapping_player_names.json"


# -------- Hilfen: Name normalisieren --------

def normalize_name(name: str) -> str:
    """
    Macht aus
      'Barber, Riley' -> 'Riley Barber'
      'Adam McCormick' -> 'Adam McCormick'
    und räumt doppelte Spaces weg.
    """
    name = (name or "").strip()
    if not name:
        return name

    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
        norm = f"{first} {last}"
    else:
        norm = name

    # Mehrfache Spaces zu einem
    norm = re.sub(r"\s+", " ", norm)
    return norm


# -------- Fake-Name-Generator --------

def _cleanup_name_fragment(text: str) -> str:
    """Nur Buchstaben drin lassen, ß -> ss."""
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿß]", "", text)
    return cleaned.replace("ß", "ss")


def fake_last_name(last: str) -> str:
    """
    Leicht verfremdeter Nachname im Stil deiner Ingolstadt-Fakes:
    - Basis bleibt erkennbar
    - Slavic / PES-artige Endungen: -ov, -ik, -en, -sen, -lek, -inov, ...
    - gleiches Real-Surname => gleicher Fake-Surname (wird außerhalb hier erzwungen)
    """
    base = _cleanup_name_fragment(last)
    if not base:
        base = "X"

    base_lower = base.lower()

    # Einige spezielle klassische Endungen leicht umbiegen (wie bei deinen Fakes)
    special_rules = [
        ("mann", "ov"),
        ("berg", "ik"),
        ("berger", "ik"),
        ("son", ""),     # z. B. "Johnson" lassen wir als Johnson
        ("sen", ""),     # z. B. "Hansen" lassen
        ("er", "ov"),    # Ellis -> El -> Elvik, Barber -> Barvik o.ä.
        ("el", "ik"),
    ]
    for suf, repl in special_rules:
        if base_lower.endswith(suf):
            root = base[:-len(suf)]
            if not root:
                root = base
            # zufällige Auswahl eines Slavic-Endings, aber deterministisch über Hash
            suffixes = ["ov", "ik", "en", "sen", "lek", "inov", "ov", "ik", "ar", "dunov", "tli", "tto", "ven", "vik"]
            h = sum(ord(c) for c in base_lower) % len(suffixes)
            suffix = suffixes[h]
            fake = root + suffix
            # Erste Buchstabe groß, Rest wie geschrieben
            return fake[0].upper() + fake[1:]

    # Standard-Fall: Basis leicht kürzen + Suffix dran
    root = base
    if len(root) > 8:
        root = root[:-2]
    elif len(root) > 6:
        root = root[:-1]

    # letzte Vokale oft wegkappen, damit z.B. "Agostino" -> "Agostinov"
    if root and root[-1].lower() in "aeiou":
        root = root[:-1] or root

    suffixes = ["ov", "ik", "en", "sen", "lek", "inov", "ov", "ik", "an", "ar", "dunov", "tli", "tto", "ven", "vik", "in", "ovik", "ro", "nik", "ov"]
    h = sum(ord(c) for c in base_lower) % len(suffixes)
    suffix = suffixes[h]

    fake = root + suffix
    return fake[0].upper() + fake[1:]


def fake_first_name(first: str) -> str:
    """
    Vorname leicht drehen, aber lesbar lassen.
    Inspiration: deine Beispiele (Luca -> Luka, Daniel -> Dan, etc.)
    """
    base = _cleanup_name_fragment(first)
    if not base:
        base = "X"

    base_lower = base.lower()
    vowels = "aeiou"

    # Kurzformen / Kürzung wie "Daniel" -> "Dan"
    if len(base) >= 6:
        # deterministisch entscheiden, ob wir kürzen oder nicht
        h = sum(ord(c) for c in base_lower)
        if h % 2 == 0:
            # ersten 3–4 Buchstaben behalten
            cut_len = 3 if len(base) >= 7 else 4
            base = base[:cut_len]
            base_lower = base.lower()

    # Letzten Buchstaben ggf. in einen Vokal drehen (Luca -> Luka, Samir -> Samir(a)-artig)
    last = base_lower[-1]
    h2 = sum(ord(c) for c in base_lower)
    v = vowels[h2 % len(vowels)]

    if last in vowels:
        fake = base[:-1] + v
    else:
        fake = base + v

    # Erste Buchstabe groß
    return fake[0].upper() + fake[1:]



# -------- Bestehendes Mapping laden --------

def load_existing_mapping() -> dict[str, str]:
    """
    Lädt mapping_player_names.json und normalisiert die Keys auf 'Vorname Nachname'.

    Unterstützt zwei Formate:
      A) Dict:  { "Real Name": "Fake Name", ... }
      B) Liste: [ { "real": "...", "fake": "..." }, ... ]
    """
    if not MAPPING_FILE.exists() or MAPPING_FILE.stat().st_size == 0:
        return {}

    txt = MAPPING_FILE.read_text(encoding="utf-8").strip()
    if not txt:
        return {}

    try:
        raw = json.loads(txt)
    except json.JSONDecodeError:
        print("⚠️ mapping_player_names.json ist kein gültiges JSON – starte mit leerem Mapping.")
        return {}

    mapping_norm: dict[str, str] = {}

    if isinstance(raw, dict):
        # Format A: {"Real": "Fake", ...}
        for real, fake in raw.items():
            norm_real = normalize_name(real)
            mapping_norm[norm_real] = str(fake)
    elif isinstance(raw, list):
        # Format B: [{"real": "...", "fake": "..."}, ...]
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            real = entry.get("real")
            fake = entry.get("fake")
            if not real or not fake:
                continue
            norm_real = normalize_name(str(real))
            mapping_norm[norm_real] = str(fake)
    else:
        print("⚠️ mapping_player_names.json hat ein unerwartetes Format – starte mit leerem Mapping.")
        return {}

    return mapping_norm



# -------- Fake-Namen für alle Spieler bauen --------

def build_fake_mapping_for_all_players() -> dict[str, str]:
    """
    - lädt players_rated.json
    - lädt bestehendes Mapping (Ingolsadt & evtl. weiteres)
    - ergänzt für alle restlichen Spieler Fake-Namen
    - sorgt dafür, dass gleiche Nachnamen -> gleicher Fake-Nachname
    """
    players = json.loads(PLAYERS_FILE.read_text(encoding="utf-8"))
    mapping = load_existing_mapping()

    # Nachnamen-Fake-Tabelle aus bestehenden Einträgen (z.B. Ingolstadt)
    surname_to_fake_surname: dict[str, str] = {}

    for real_norm, fake in mapping.items():
        real_parts = real_norm.split()
        fake_parts = fake.split()
        if len(real_parts) >= 2 and len(fake_parts) >= 2:
            r_last = real_parts[-1]
            f_last = fake_parts[-1]
            surname_to_fake_surname[r_last] = f_last

    # Track, welche Fakes schon vergeben sind (für Kollisionsvermeidung)
    fake_used: set[str] = set(mapping.values())

    def assign_fake_for_real(real_name_raw: str) -> str:
        real_norm = normalize_name(real_name_raw)

        # schon gemappt? -> direkt zurück
        if real_norm in mapping:
            return mapping[real_norm]

        parts = real_norm.split()
        if not parts:
            return real_norm  # gar nichts sinnvolles drin

        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""

        # 1) Nachnamen-Fake ggf. aus bestehender Gruppe holen
        if last in surname_to_fake_surname:
            fake_last = surname_to_fake_surname[last]
        else:
            fake_last = fake_last_name(last)
            surname_to_fake_surname[last] = fake_last

        # 2) Vornamen-Fake generieren
        fake_first = fake_first_name(first)
        fake_full = f"{fake_first} {fake_last}".strip()

        # 3) Sicherstellen, dass wir nicht denselben Fake für zwei verschiedene Realnamen nutzen
        i = 1
        base_fake = fake_full
        while fake_full in fake_used:
            fake_full = f"{base_fake}{i}"
            i += 1

        mapping[real_norm] = fake_full
        fake_used.add(fake_full)
        return fake_full

    # Jetzt einmal über alle Spieler aus players_rated.json iterieren
    for p in players:
        real_raw = p.get("name_real", "")
        assign_fake_for_real(real_raw)

    return mapping


def main() -> None:
    mapping = build_fake_mapping_for_all_players()

    # Bestehende player_ids laden, falls vorhanden
    existing_ids = {}
    if MAPPING_FILE.exists():
        try:
            existing_data = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
            if isinstance(existing_data, list):
                for entry in existing_data:
                    if isinstance(entry, dict) and "real" in entry and "player_id" in entry:
                        existing_ids[entry["real"]] = entry["player_id"]
        except:
            pass  # Falls Datei korrupt, ignorieren

    # sortiert nach Nachname, dann Vorname (nur für bessere Lesbarkeit)
    def sort_key(item: tuple[str, str]) -> tuple[str, str]:
        real = item[0]
        parts = real.split()
        if len(parts) >= 2:
            return (parts[-1], parts[0])
        return (real, "")

    items_sorted = sorted(mapping.items(), key=sort_key)

    # als Liste von Objekten speichern – player_ids erhalten!
    out_list = []
    for real, fake in items_sorted:
        entry = {"real": real, "fake": fake}
        # Player ID wiederherstellen, falls vorhanden
        if real in existing_ids:
            entry["player_id"] = existing_ids[real]
        out_list.append(entry)

    MAPPING_FILE.write_text(
        json.dumps(out_list, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"✅ mapping_player_names.json aktualisiert – {len(out_list)} Einträge insgesamt.")



if __name__ == "__main__":
    main()
