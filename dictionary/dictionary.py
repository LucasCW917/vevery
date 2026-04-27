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
    "0": "numane",    "1": "sonuma",   "2": "vanuma",
    "3": "mirnuma",   "4": "lorenuma", "5": "sevinuma",
    "6": "havenuma",  "7": "belanuma", "8": "yovenuma",
    "9": "zavenuma",
}

PLACE_WORDS = {
    1: "sonuma",  2: "vanuma",   3: "mirnuma",
    4: "lorenuma", 5: "sevinuma", 6: "havenuma",
    7: "belanuma", 8: "yovenuma", 9: "zavenuma",
}

NUM_SEPARATOR = "mirévali"


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
    n = n.replace(",", "").replace("_", "")
    if not n.isdigit():
        return None
    if len(n) == 1:
        return DIGIT_WORDS[n]
    count = PLACE_WORDS.get(len(n))
    if not count:
        count = number_to_vevery(str(len(n)))
    digits = " ".join(DIGIT_WORDS[d] for d in n)
    return f"{count} {NUM_SEPARATOR} {digits}"


def is_number_token(word: str) -> bool:
    """Return True if the token looks like a number (digits and commas only)."""
    cleaned = word.replace(",", "").replace("_", "")
    return cleaned.isdigit() and len(cleaned) > 0


# ── Sentence Translation ──────────────────────────────────────────────────────

def lemmatize_token(token: str) -> list:
    """
    Return a list of candidate base forms for a token, in priority order.
    Tries nltk lemmatizer first, then simple suffix stripping as fallback.
    """
    candidates = []

    # nltk lemmatizer — try verb first, then noun, then adjective
    try:
        from nltk.stem import WordNetLemmatizer
        lemmatizer = WordNetLemmatizer()
        for pos in ("v", "n", "a", "r"):
            lemma = lemmatizer.lemmatize(token, pos)
            if lemma != token and lemma not in candidates:
                candidates.append(lemma)
    except Exception:
        pass

    # Simple suffix stripping fallback
    suffix_rules = [
        ("ying", "y"),   # trying -> try
        ("ying", "ie"),  # dying -> die
        ("ies",  "y"),   # tries -> try
        ("ied",  "y"),   # tried -> try
        ("ing",  "e"),   # taking -> take
        ("ing",  ""),    # running -> run
        ("ays",  "ay"),  # says -> say
        ("ed",   "e"),   # liked -> like
        ("ed",   ""),    # wanted -> want
        ("ers",  "er"),  # runners -> runner
        ("es",   "e"),   # takes -> take
        ("es",   ""),    # watches -> watch
        ("s",    ""),    # runs -> run
        ("ly",   ""),    # truly -> true (rough)
        ("er",   ""),    # bigger -> big (rough)
        ("est",  ""),    # biggest -> big (rough)
    ]
    for suffix, replacement in suffix_rules:
        if token.endswith(suffix) and len(token) - len(suffix) >= 2:
            base = token[:-len(suffix)] + replacement
            if base not in candidates:
                candidates.append(base)

    return candidates


def resolve_english_token(conn: sqlite3.Connection, token: str):
    """Resolve a single English token to its Vevery word, checking redirects."""
    # Number check
    if is_number_token(token):
        result = number_to_vevery(token)
        if result:
            return result, None

    # Direct dictionary lookup
    row = lookup_english(conn, token)
    if row:
        return row[1], None

    # Redirect lookup
    _, redirected = lookup_redirect(conn, token)
    if redirected:
        return redirected[1], None

    # Lemmatizer + suffix fallback
    for candidate in lemmatize_token(token):
        row = lookup_english(conn, candidate)
        if row:
            return row[1], None
        _, redirected = lookup_redirect(conn, candidate)
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
    """
    Split a token into (leading_punct, core_word, trailing_punct).
    Apostrophes that are part of a word (c', ul', don't) are preserved.
    Only sentence-level punctuation (.,!?;:) is stripped from edges.
    """
    SENTENCE_PUNCT = set('.,!?;:')
    lead  = ""
    trail = ""
    word  = token

    # Strip leading sentence punctuation only
    while word and word[0] in SENTENCE_PUNCT:
        lead += word[0]
        word  = word[1:]

    # Strip trailing sentence punctuation only
    while word and word[-1] in SENTENCE_PUNCT:
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

    # Capitalize after sentence boundaries (start, and after . ! ?)
    def capitalize_sentences(text: str) -> str:
        result = []
        capitalize_next = True
        inside_bracket = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "[":
                inside_bracket = True
            elif ch == "]":
                inside_bracket = False
            if capitalize_next and ch.isalpha():
                result.append(ch.upper())
                capitalize_next = False
            else:
                result.append(ch)
            if ch in ".!?" and not inside_bracket:
                capitalize_next = True
            i += 1
        return "".join(result)

    result = capitalize_sentences(result)

    print(f"\n  {lang_from}:  {sentence}")
    print(f"  {lang_to}:   {result}")

    if missing:
        print(f"\n  Missing words: {', '.join(missing)}")
        print("  (These appear as [word?] in the output.)")

    input()


# ── Command Injection ─────────────────────────────────────────────────────────

import shlex

def parse_command(line: str, conn: sqlite3.Connection) -> str:
    """Parse and execute a single !command. Returns a result string."""
    line = line.strip()
    if not line or not line.startswith("!"):
        return f"  Skipped (not a command): {line}"

    try:
        parts = shlex.split(line[1:])  # Strip leading ! and tokenize
    except ValueError as e:
        return f"  Parse error: {e}"

    if not parts:
        return "  Empty command."

    cmd = parts[0].lower()

    # ── !add entry "english" "vevery" "pronunciation" "notes" ──
    if cmd == "add" and len(parts) >= 2 and parts[1].lower() == "entry":
        args = parts[2:]
        if len(args) < 2:
            return "  !add entry requires at least english and vevery."
        english       = args[0]
        vevery        = args[1]
        pronunciation = args[2] if len(args) > 2 else ""
        notes         = args[3] if len(args) > 3 else ""
        existing = lookup_english(conn, english)
        if existing:
            update_word(conn, english, vevery, pronunciation, notes)
            return f"  Updated:  {english} → {vevery}"
        ok, err = add_word(conn, english, vevery, pronunciation, notes)
        return f"  Added:    {english} → {vevery}" if ok else f"  Error:    {err}"

    # ── !add redirect "alias" "english" ──
    elif cmd == "add" and len(parts) >= 2 and parts[1].lower() == "redirect":
        args = parts[2:]
        if len(args) < 2:
            return "  !add redirect requires alias and english."
        alias, english = args[0], args[1]
        if not lookup_english(conn, english):
            return f"  Error: \"{english}\" not in dictionary."
        ok, err = add_redirect(conn, alias, english)
        return f"  Redirect: \"{alias}\" → \"{english}\"" if ok else f"  Error:    {err}"

    # ── !rm entry "english" ──
    elif cmd == "rm" and len(parts) >= 2 and parts[1].lower() == "entry":
        if len(parts) < 3:
            return "  !rm entry requires an english word."
        english = parts[2]
        if not lookup_english(conn, english):
            return f"  Not found: \"{english}\""
        delete_word(conn, english)
        return f"  Removed:  \"{english}\""

    # ── !rm redirect "alias" ──
    elif cmd == "rm" and len(parts) >= 2 and parts[1].lower() == "redirect":
        if len(parts) < 3:
            return "  !rm redirect requires an alias."
        alias = parts[2]
        target, _ = lookup_redirect(conn, alias)
        if not target:
            return f"  Not found: \"{alias}\""
        delete_redirect(conn, alias)
        return f"  Removed redirect: \"{alias}\""

    # ── !edit "english" "field" "new value" ──
    elif cmd == "edit":
        if len(parts) < 4:
            return "  !edit requires english, field, and new value."
        english, field, value = parts[1], parts[2].lower(), parts[3]
        if field not in ("english", "vevery", "pronunciation", "notes"):
            return f"  Unknown field: \"{field}\". Use: english, vevery, pronunciation, notes."
        if not lookup_english(conn, english):
            return f"  Not found: \"{english}\""
        conn.execute(f"UPDATE dictionary SET {field} = ? WHERE english = ?", (value, english))
        conn.commit()
        return f"  Edited:   {english} → {field} = \"{value}\""

    else:
        return f"  Unknown command: {line}"


def menu_inject(conn: sqlite3.Connection):
    print("\n  Command Injection")
    print("  Paste semicolon-separated commands, then press Enter twice.")
    print("  Syntax:")
    print('    !add entry "english" "vevery" "pronunciation" "notes";')
    print('    !add redirect "alias" "english";')
    print('    !rm entry "english";')
    print('    !rm redirect "alias";')
    print('    !edit "english" "field" "new value";')
    print()

    lines = []
    while True:
        line = input("  > ")
        if line.strip() == "":
            break
        lines.append(line)

    raw = " ".join(lines)
    commands = [c.strip() for c in raw.split(";") if c.strip()]

    if not commands:
        print("\n  No commands found.")
        input()
        return

    print(f"\n  Processing {len(commands)} command(s)...\n")
    ok_count  = 0
    err_count = 0
    for cmd in commands:
        result = parse_command(cmd, conn)
        print(result)
        if "Error" in result or "Unknown" in result or "not found" in result.lower():
            err_count += 1
        else:
            ok_count += 1

    print(f"\n  Done. {ok_count} succeeded, {err_count} failed.")
    input()



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

def ensure_nltk():
    """Download required nltk data if not already present."""
    try:
        import nltk
        try:
            from nltk.stem import WordNetLemmatizer
            WordNetLemmatizer().lemmatize("test", "v")
        except LookupError:
            print("  Downloading language data (one-time setup)...")
            nltk.download("wordnet", quiet=True)
            nltk.download("omw-1.4", quiet=True)
            print("  Done.\n")
    except ImportError:
        print("  Warning: nltk not installed. Run: pip install nltk")
        print("  Lemmatizer fallback will be disabled.\n")


def main():
    ensure_nltk()
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
        print("  [8] Inject commands")
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
        elif choice == "8":
            menu_inject(conn)
        elif choice in ("q", "quit", "exit"):
            print("\n  Goodbye.\n")
            conn.close()
            sys.exit(0)
        else:
            print("  Unknown option.")
            input()


if __name__ == "__main__":
    main()