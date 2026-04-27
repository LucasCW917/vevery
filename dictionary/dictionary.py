#!/usr/bin/env python3
"""
Vevery Dictionary
-----------------
A simple CLI tool to manage an English <-> Vevery dictionary using SQLite.

Usage:
    python vevery.py
"""

import sqlite3
import sys

DB_FILE = "vevery.db"


# ── Database ────────────────────────────────────────────────────────────────

def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dictionary (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            english         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            vevery          TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            pronunciation   TEXT,
            notes           TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add pronunciation column if upgrading from older DB
    try:
        conn.execute("ALTER TABLE dictionary ADD COLUMN pronunciation TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.execute("""
        CREATE TABLE IF NOT EXISTS redirects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            alias       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            english     TEXT    NOT NULL COLLATE NOCASE,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (english) REFERENCES dictionary(english) ON UPDATE CASCADE ON DELETE CASCADE
        )
    """)

    # Seed known words
    seed = [
        ("I",    "zew", "zeww",                    "first-person singular pronoun"),
        ("you",  "qew", "kweww",                   "second-person singular pronoun"),
        ("he",   "xas", "sass",                    None),
        ("she",  "cas", "cass (as in Cassidy)",    None),
        ("they", "vas", None,                      None),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO dictionary (english, vevery, pronunciation, notes) VALUES (?, ?, ?, ?)",
        seed
    )
    conn.commit()


# ── Lookup ───────────────────────────────────────────────────────────────────

def lookup_english(conn: sqlite3.Connection, word: str):
    return conn.execute(
        "SELECT english, vevery, pronunciation, notes FROM dictionary WHERE english = ?",
        (word,)
    ).fetchone()


def lookup_vevery(conn: sqlite3.Connection, word: str):
    return conn.execute(
        "SELECT english, vevery, pronunciation, notes FROM dictionary WHERE vevery = ?",
        (word,)
    ).fetchone()


# ── Add / Update ─────────────────────────────────────────────────────────────

def add_word(conn: sqlite3.Connection, english: str, vevery: str,
             pronunciation: str = "", notes: str = ""):
    try:
        conn.execute(
            "INSERT INTO dictionary (english, vevery, pronunciation, notes) VALUES (?, ?, ?, ?)",
            (english, vevery, pronunciation or None, notes or None)
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, str(e)


def update_word(conn: sqlite3.Connection, english: str, new_vevery: str,
                new_pronunciation: str = "", new_notes: str = ""):
    conn.execute(
        "UPDATE dictionary SET vevery = ?, pronunciation = ?, notes = ? WHERE english = ?",
        (new_vevery, new_pronunciation or None, new_notes or None, english)
    )
    conn.commit()


def delete_word(conn: sqlite3.Connection, english: str):
    conn.execute("DELETE FROM dictionary WHERE english = ?", (english,))
    conn.commit()


# ── Redirects ─────────────────────────────────────────────────────────────────

def lookup_redirect(conn: sqlite3.Connection, alias: str):
    """Returns the dictionary row the alias points to, or None."""
    row = conn.execute(
        "SELECT english FROM redirects WHERE alias = ?", (alias,)
    ).fetchone()
    if not row:
        return None, None
    target = row[0]
    entry = lookup_english(conn, target)
    return target, entry


def add_redirect(conn: sqlite3.Connection, alias: str, english: str):
    try:
        conn.execute(
            "INSERT INTO redirects (alias, english) VALUES (?, ?)",
            (alias, english)
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, str(e)


def delete_redirect(conn: sqlite3.Connection, alias: str):
    conn.execute("DELETE FROM redirects WHERE alias = ?", (alias,))
    conn.commit()


def list_redirects(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT alias, english FROM redirects ORDER BY alias COLLATE NOCASE"
    ).fetchall()


# ── List ─────────────────────────────────────────────────────────────────────

def list_all(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT english, vevery, pronunciation, notes FROM dictionary ORDER BY english COLLATE NOCASE"
    ).fetchall()


# ── CLI helpers ──────────────────────────────────────────────────────────────

def print_entry(row):
    english, vevery, pronunciation, notes = row
    pron_str = f"  /{pronunciation}/" if pronunciation else ""
    note_str = f"  ({notes})"         if notes         else ""
    print(f"  {english:20} →  {vevery:20}{pron_str}{note_str}")


def prompt(text: str, default: str = "") -> str:
    val = input(text).strip()
    return val if val else default


# ── Number Conversion ────────────────────────────────────────────────────────

DIGIT_WORDS = {
    "0": "cosx", "1": "sat", "2": "jeg", "3": "mep",
    "4": "poer", "5": "ill", "6": "nupturk", "7": "sevg",
    "8": "yuktemb", "9": "nein",
}

PLACE_WORDS = {
    1: "sat", 2: "jeg", 3: "mep", 4: "poer", 5: "ill",
    6: "nupturk", 7: "sevg", 8: "yuktemb", 9: "nein",
}


def place_to_vevery(place: int) -> str:
    """Convert a place index (1=ones, 2=tens, ...) to its Vevery je- expression."""
    digits = str(place)
    if len(digits) == 1:
        return f"je{PLACE_WORDS[place]}"
    # Multi-digit place: use [count] unj [digits] format
    count  = PLACE_WORDS[len(digits)]
    parts  = [DIGIT_WORDS[d] for d in digits]
    return f"je-{count} unj {' '.join(parts)}"


def number_to_vevery(n: str) -> str:
    """
    Convert a numeric string (e.g. '7893') to Vevery digit-count format:
    [digit_count] unj [digits left to right]
    Single digits are returned as their word directly.
    """
    # Strip commas
    n = n.replace(",", "").replace("_", "")
    if not n.isdigit():
        return None

    if len(n) == 1:
        return DIGIT_WORDS[n]

    count  = PLACE_WORDS.get(len(n))
    if not count:
        # For counts beyond 9 digits, express count itself recursively
        count = number_to_vevery(str(len(n)))

    digits = " ".join(DIGIT_WORDS[d] for d in n)
    return f"{count} unj {digits}"


def is_number_token(word: str) -> bool:
    """Return True if the token looks like a number (digits and commas only)."""
    cleaned = word.replace(",", "").replace("_", "")
    return cleaned.isdigit() and len(cleaned) > 0


# ── Sentence Translation ──────────────────────────────────────────────────────

def resolve_english_token(conn: sqlite3.Connection, token: str):
    """Resolve a single English token to its Vevery word, checking redirects."""
    # Check if it's a number first
    if is_number_token(token):
        result = number_to_vevery(token)
        if result:
            return result, None

    row = lookup_english(conn, token)
    if row:
        return row[1], None
    _, redirected = lookup_redirect(conn, token)
    if redirected:
        return redirected[1], None
    return None, token  # unknown


def resolve_vevery_token(conn: sqlite3.Connection, token: str):
    """Resolve a single Vevery token to its English word."""
    row = lookup_vevery(conn, token)
    if row:
        return row[0], None
    return None, token  # unknown


def strip_punctuation(token: str):
    """Split a token into (leading_punct, core_word, trailing_punct)."""
    import string
    lead  = ""
    trail = ""
    word  = token
    while word and word[0] in string.punctuation:
        lead += word[0]
        word  = word[1:]
    while word and word[-1] in string.punctuation:
        trail = word[-1] + trail
        word  = word[:-1]
    return lead, word, trail


def translate_sentence(conn: sqlite3.Connection, sentence: str, direction: str):
    """
    Translate a sentence word by word, preserving punctuation.
    direction: 'en' (English→Vevery) or 've' (Vevery→English)
    Returns (translated_tokens, missing_tokens).
    """
    tokens = sentence.strip().split()
    translated = []
    missing = []

    for token in tokens:
        lead, word, trail = strip_punctuation(token)
        clean = word.lower()

        if direction == "en":
            result, unknown = resolve_english_token(conn, clean)
        else:
            result, unknown = resolve_vevery_token(conn, clean)

        if result:
            translated.append(f"{lead}{result}{trail}")
        else:
            translated.append(f"{lead}[{word}?]{trail}")
            missing.append(word)

    return translated, missing


def menu_translate_sentence(conn: sqlite3.Connection):
    print("\n  Translate Sentence")
    print("  [1] English → Vevery")
    print("  [2] Vevery  → English")
    print("  [b] Back")
    choice = prompt("  > ").lower()

    if choice not in ("1", "2"):
        return

    direction = "en" if choice == "1" else "ve"
    lang_from = "English" if direction == "en" else "Vevery"
    lang_to   = "Vevery"  if direction == "en" else "English"

    sentence = prompt(f"\n  {lang_from} sentence: ")
    if not sentence.strip():
        print("  Cancelled.")
        input()
        return

    translated, missing = translate_sentence(conn, sentence, direction)
    result = " ".join(translated)

    print(f"\n  {lang_from}:  {sentence}")
    print(f"  {lang_to}:   {result}")

    if missing:
        print(f"\n  Missing words: {', '.join(missing)}")
        print("  (These appear as [word?] in the output.)")

    input()


# ── Menus ─────────────────────────────────────────────────────────────────────

def menu_translate(conn: sqlite3.Connection):
    print("\n  Translate")
    print("  [1] English → Vevery")
    print("  [2] Vevery  → English")
    print("  [b] Back")
    choice = prompt("  > ").lower()

    if choice == "1":
        word = prompt("  English word: ").lower()
        row = lookup_english(conn, word)
        if row:
            print()
            print_entry(row)
            input()
        else:
            # Check redirects
            target, redirected = lookup_redirect(conn, word)
            if redirected:
                print(f'\n  "{word}" → redirects to "{target}"')
                print_entry(redirected)
                input()
            else:
                print(f'\n  "{word}" not found in dictionary.')
                add = prompt("  Add it now? (y/n): ").lower()
                if add == "y":
                    menu_add(conn, prefill_english=word)

    elif choice == "2":
        word = prompt("  Vevery word: ").lower()
        row = lookup_vevery(conn, word)
        if row:
            print()
            print_entry(row)
            input()
        else:
            print(f'\n  "{word}" not found in dictionary.')


def menu_add(conn: sqlite3.Connection, prefill_english: str = ""):
    print("\n  Add new word")
    english = prompt(f"  English [{prefill_english}]: ", prefill_english).lower()
    if not english:
        print("  Cancelled.")
        return

    existing = lookup_english(conn, english)
    if existing:
        print(f'\n  "{english}" already exists → Vevery: {existing[1]}')
        overwrite = prompt("  Overwrite? (y/n): ").lower()
        if overwrite != "y":
            return
        vevery        = prompt(f"  New Vevery word [{existing[1]}]: ",     existing[1])
        pronunciation = prompt(f"  Pronunciation [{existing[2] or ''}]: ", existing[2] or "")
        notes         = prompt(f"  Notes [{existing[3] or ''}]: ",         existing[3] or "")
        update_word(conn, english, vevery, pronunciation, notes)
        print(f'  Updated: {english} → {vevery}')
        return

    vevery        = prompt("  Vevery word: ").lower()
    if not vevery:
        print("  Cancelled — Vevery word cannot be empty.")
        return
    pronunciation = prompt("  Pronunciation (optional): ")
    notes         = prompt("  Notes (optional): ")

    ok, err = add_word(conn, english, vevery, pronunciation, notes)
    if ok:
        print(f'  Added: {english} → {vevery}')
    else:
        print(f'  Error: {err}')


def menu_edit(conn: sqlite3.Connection):
    print("\n  Edit word")
    word = prompt("  English word to edit: ").lower()
    row = lookup_english(conn, word)
    if not row:
        print(f'\n  "{word}" not found.')
        input()
        return

    english, vevery, pronunciation, notes = row
    print("\n  Current entry:")
    print_entry(row)
    print("\n  Leave a field blank to keep its current value.")
    print("  Type a single dash [-] to clear a field.\n")

    fields = {
        "english":       ("  English       ", english),
        "vevery":        ("  Vevery        ", vevery),
        "pronunciation": ("  Pronunciation ", pronunciation or ""),
        "notes":         ("  Notes         ", notes or ""),
    }

    updates = {}
    for key, (label, current) in fields.items():
        val = prompt(f"{label} [{current}]: ")
        if val == "-":
            updates[key] = None
        elif val:
            updates[key] = val

    if not updates:
        print("\n  No changes made.")
        input()
        return

    # Build dynamic UPDATE query
    set_clauses = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [english]
    try:
        conn.execute(f"UPDATE dictionary SET {set_clauses} WHERE english = ?", values)
        conn.commit()
        # Re-fetch and show updated entry
        updated = lookup_english(conn, updates.get("english", english))
        print("\n  Updated entry:")
        print_entry(updated)
    except sqlite3.IntegrityError as e:
        print(f"\n  Error: {e}")
    input()


def menu_redirects(conn: sqlite3.Connection):
    while True:
        print("\033c", end='')
        print("\n  Redirects")
        print("  [1] Add redirect")
        print("  [2] Delete redirect")
        print("  [3] List redirects")
        print("  [b] Back")
        choice = prompt("  > ").lower()
        print("\033c", end='')

        if choice == "1":
            alias = prompt("  Alias (e.g. 'by'): ").lower()
            if not alias:
                print("  Cancelled.")
                input()
                continue
            english = prompt("  Points to English word (e.g. 'over'): ").lower()
            if not english:
                print("  Cancelled.")
                input()
                continue
            # Verify target exists
            if not lookup_english(conn, english):
                print(f'\n  "{english}" not found in dictionary. Add it first.')
                input()
                continue
            ok, err = add_redirect(conn, alias, english)
            if ok:
                print(f'  Added redirect: "{alias}" → "{english}"')
            else:
                print(f'  Error: {err}')
            input()

        elif choice == "2":
            alias = prompt("  Alias to delete: ").lower()
            target, _ = lookup_redirect(conn, alias)
            if not target:
                print(f'  "{alias}" not found in redirects.')
            else:
                confirm = prompt(f'  Delete "{alias}" → "{target}"? (y/n): ').lower()
                if confirm == "y":
                    delete_redirect(conn, alias)
                    print("  Deleted.")
            input()

        elif choice == "3":
            rows = list_redirects(conn)
            if not rows:
                print("\n  No redirects defined.")
            else:
                print(f"\n  {'Alias':<20}   Points to")
                print("  " + "─" * 40)
                for alias, english in rows:
                    print(f"  {alias:<20} →  {english}")
                print(f"\n  {len(rows)} redirect(s) total.")
            input()

        elif choice == "b":
            break


def menu_delete(conn: sqlite3.Connection):
    print("\n  Delete word")
    word = prompt("  English word to delete: ").lower()
    row = lookup_english(conn, word)
    if not row:
        print(f'  "{word}" not found.')
        return
    print()
    print_entry(row)
    confirm = prompt("  Delete this entry? (y/n): ").lower()
    if confirm == "y":
        delete_word(conn, word)
        print("  Deleted.")


def menu_list(conn: sqlite3.Connection):
    rows = list_all(conn)
    if not rows:
        print("\n  Dictionary is empty.")
        return
    print(f"\n  {'English':<20}   {'Vevery':<20}  Pronunciation / Notes")
    print("  " + "─" * 70)
    for row in rows:
        print_entry(row)
    print(f"\n  {len(rows)} word(s) total.")
    input()


# ── Main loop ────────────────────────────────────────────────────────────────

def main():
    conn = sqlite3.connect(DB_FILE)
    init_db(conn)

    while True:
        print("\033c", end='')
        print("\n  ╔══════════════════════════╗")
        print("  ║   Vevery Dictionary CLI  ║")
        print("  ╚══════════════════════════╝")

        print("\n  [1] Translate a word")
        print("  [2] Translate a sentence")
        print("\n  [3] Add a new word")
        print("  [4] Edit a word")
        print("  [5] Delete a word")
        print("  [6] List all words")
        print("  [7] Redirects")
        print("  [q] Quit")
        choice = prompt("\n  > ").lower()

        print("\033c", end='')

        if choice == "1":
            menu_translate(conn)
        elif choice == "2":
            menu_translate_sentence(conn)
        elif choice == "3":
            menu_add(conn)
        elif choice == "4":
            menu_edit(conn)
        elif choice == "5":
            menu_delete(conn)
        elif choice == "6":
            menu_list(conn)
        elif choice == "7":
            menu_redirects(conn)
        elif choice in ("q", "quit", "exit"):
            print("\n  Goodbye.\n")
            conn.close()
            sys.exit(0)
        else:
            print("  Unknown option.")
            input()


if __name__ == "__main__":
    main()