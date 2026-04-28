## #!/usr/bin/env python3
“””
Vevery Dictionary

A simple CLI tool to manage an English <-> Vevery dictionary using SQLite.

Usage:
python vevery.py
“””

import sqlite3
import sys
import re

# Vevery 2.0 Grammar Constants
TENSE_MAP = {
    "am": "ha", "is": "ha", "are": "ha", "doing": "ha",
    "was": "va", "were": "va", "did": "va",
    "will": "se", "going": "se",
}

TONE_MAP = {
    ".": "—", # Fact/Assertion
    "!": "ˋ", # Warning/Command
    "?": "ˊ", # Question/Inquiry
}

def apply_elision(text: str) -> str:
    """Smoothes out vowel clusters and simplifies Germanic-style merges."""
    # Rule: If two vowels meet at a merge point, the first one is 'eaten'
    # Example: 'numa' + 'ha' -> 'numha'
    text = re.sub(r'([aeiou])([aeiou])', r'\2', text)
    
    # Rule: Simplify hard consonant clusters (e.g., rsn -> nn)
    text = text.replace("rsn", "nn").replace("np", "mp")
    return text

def fuse_mega_word(tokens: list, tone: str = "—") -> str:
    """
    Takes a list of Vevery words and fuses them into one Germanic Mega-word.
    Order: [Object][Tense][Verb][Subject]
    """
    if not tokens: return ""
    
    # In a true logical system, we'd use NLP to tag these. 
    # For now, we'll fuse them in order of appearance but apply elision.
    fused = "".join(tokens)
    fused = apply_elision(fused)
    
    return fused + tone


DB_FILE = “vevery.db”

# ── Database ────────────────────────────────────────────────────────────────

def init_db(conn: sqlite3.Connection):
conn.execute(”””
CREATE TABLE IF NOT EXISTS dictionary (
id              INTEGER PRIMARY KEY AUTOINCREMENT,
english         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
vevery          TEXT    NOT NULL UNIQUE COLLATE NOCASE,
pronunciation   TEXT,
notes           TEXT,
created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)
“””)
# Add pronunciation column if upgrading from older DB
try:
conn.execute(“ALTER TABLE dictionary ADD COLUMN pronunciation TEXT”)
conn.commit()
except sqlite3.OperationalError:
pass  # Column already exists

```
conn.execute("""
    CREATE TABLE IF NOT EXISTS redirects (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        alias       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        english     TEXT    NOT NULL COLLATE NOCASE,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (english) REFERENCES dictionary(english) ON UPDATE CASCADE ON DELETE CASCADE
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS concepts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        cluster     TEXT    DEFAULT '',
        opposites   TEXT    DEFAULT '',
        category    TEXT    DEFAULT '',
        expression  TEXT    DEFAULT '',
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

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
```

# ── Lookup ───────────────────────────────────────────────────────────────────

def lookup_english(conn: sqlite3.Connection, word: str):
return conn.execute(
“SELECT english, vevery, pronunciation, notes FROM dictionary WHERE english = ?”,
(word,)
).fetchone()

def lookup_vevery(conn: sqlite3.Connection, word: str):
return conn.execute(
“SELECT english, vevery, pronunciation, notes FROM dictionary WHERE vevery = ?”,
(word,)
).fetchone()

# ── Add / Update ─────────────────────────────────────────────────────────────

def add_word(conn: sqlite3.Connection, english: str, vevery: str,
pronunciation: str = “”, notes: str = “”):
try:
conn.execute(
“INSERT INTO dictionary (english, vevery, pronunciation, notes) VALUES (?, ?, ?, ?)”,
(english, vevery, pronunciation or None, notes or None)
)
conn.commit()
return True, None
except sqlite3.IntegrityError as e:
return False, str(e)

def update_word(conn: sqlite3.Connection, english: str, new_vevery: str,
new_pronunciation: str = “”, new_notes: str = “”):
conn.execute(
“UPDATE dictionary SET vevery = ?, pronunciation = ?, notes = ? WHERE english = ?”,
(new_vevery, new_pronunciation or None, new_notes or None, english)
)
conn.commit()

def delete_word(conn: sqlite3.Connection, english: str):
conn.execute(“DELETE FROM dictionary WHERE english = ?”, (english,))
conn.commit()

# ── Redirects ─────────────────────────────────────────────────────────────────

def lookup_redirect(conn: sqlite3.Connection, alias: str):
“”“Returns the dictionary row the alias points to, or None.”””
row = conn.execute(
“SELECT english FROM redirects WHERE alias = ?”, (alias,)
).fetchone()
if not row:
return None, None
target = row[0]
entry = lookup_english(conn, target)
return target, entry

def add_redirect(conn: sqlite3.Connection, alias: str, english: str):
try:
conn.execute(
“INSERT INTO redirects (alias, english) VALUES (?, ?)”,
(alias, english)
)
conn.commit()
return True, None
except sqlite3.IntegrityError as e:
return False, str(e)

def delete_redirect(conn: sqlite3.Connection, alias: str):
conn.execute(“DELETE FROM redirects WHERE alias = ?”, (alias,))
conn.commit()

def list_redirects(conn: sqlite3.Connection):
return conn.execute(
“SELECT alias, english FROM redirects ORDER BY alias COLLATE NOCASE”
).fetchall()

# ── Concepts ──────────────────────────────────────────────────────────────────

def add_concept(conn, name, cluster=””, opposites=””, category=””, expression=””):
try:
conn.execute(
“INSERT INTO concepts (name, cluster, opposites, category, expression) VALUES (?,?,?,?,?)”,
(name, cluster, opposites, category, expression)
)
conn.commit()
return True, None
except sqlite3.IntegrityError as e:
return False, str(e)

def update_concept(conn, name, cluster, opposites, category, expression):
conn.execute(
“UPDATE concepts SET cluster=?, opposites=?, category=?, expression=? WHERE name=?”,
(cluster, opposites, category, expression, name)
)
conn.commit()

def delete_concept(conn, name):
conn.execute(“DELETE FROM concepts WHERE name=?”, (name,))
conn.commit()

def get_concept(conn, name):
return conn.execute(
“SELECT name, cluster, opposites, category, expression FROM concepts WHERE name=?”,
(name,)
).fetchone()

def list_concepts(conn):
return conn.execute(
“SELECT name, cluster, opposites, category, expression FROM concepts ORDER BY name COLLATE NOCASE”
).fetchall()

def resolve_via_concept(conn, token: str):
“””
Try to resolve an unknown token through the concept graph.
Returns (vevery_expression, concept_name, method) or (None, None, None).

```
method is one of:
  'direct'   — token matched a concept name directly
  'cluster'  — token found in a concept's cluster
  'opposite' — token found in a concept's opposites (expression negated)
"""
token_l = token.lower()

# 1. Direct concept name match
row = get_concept(conn, token_l)
if row:
    expr = _concept_to_expression(conn, row)
    if expr:
        return expr, row[0], "direct"

# 2. Scan all concepts — check cluster and opposites fields
for row in list_concepts(conn):
    name, cluster, opposites, category, expression = row
    cluster_words  = [w.strip().lower() for w in cluster.split(",")  if w.strip()]
    opposite_words = [w.strip().lower() for w in opposites.split(",") if w.strip()]

    if token_l in cluster_words:
        expr = _concept_to_expression(conn, row)
        if expr:
            return expr, name, "cluster"

    if token_l in opposite_words:
        expr = _concept_to_expression(conn, row)
        if expr:
            # Negate the expression using mavesone (not)
            neg = _get_vevery(conn, "not") or "mavesone"
            return f"{neg} {expr}", name, "opposite"

return None, None, None
```

def _get_vevery(conn, english: str):
“”“Quick helper — get Vevery word for an English word.”””
row = lookup_english(conn, english)
return row[1] if row else None

def _concept_to_expression(conn, row) -> str:
“””
Turn a concept row into a Vevery expression.
Priority:
1. Manual expression field
2. Direct dictionary lookup of concept name
3. Compound from top cluster words that exist in dictionary
“””
name, cluster, opposites, category, expression = row

```
# 1. Manual override
if expression and expression.strip():
    return expression.strip()

# 2. Direct lookup
direct = _get_vevery(conn, name)
if direct:
    return direct

# 3. Compound from cluster
cluster_words = [w.strip() for w in cluster.split(",") if w.strip()]
found = []
for w in cluster_words[:3]:  # Use up to 3 cluster words
    v = _get_vevery(conn, w)
    if v:
        found.append(v)
    if len(found) == 2:
        break

if found:
    return "-".join(found)

return None
```

# ── List ─────────────────────────────────────────────────────────────────────

def list_all(conn: sqlite3.Connection):
return conn.execute(
“SELECT english, vevery, pronunciation, notes FROM dictionary ORDER BY english COLLATE NOCASE”
).fetchall()

# ── CLI helpers ──────────────────────────────────────────────────────────────

def print_entry(row):
english, vevery, pronunciation, notes = row
pron_str = f”  /{pronunciation}/” if pronunciation else “”
note_str = f”  ({notes})”         if notes         else “”
print(f”  {english:20} →  {vevery:20}{pron_str}{note_str}”)

def prompt(text: str, default: str = “”) -> str:
val = input(text).strip()
return val if val else default

# ── Number Conversion ────────────────────────────────────────────────────────

DIGIT_WORDS = {
“0”: “numane”,    “1”: “sonuma”,   “2”: “vanuma”,
“3”: “mirnuma”,   “4”: “lorenuma”, “5”: “sevinuma”,
“6”: “havenuma”,  “7”: “belanuma”, “8”: “yovenuma”,
“9”: “zavenuma”,
}

PLACE_WORDS = {
1: “sonuma”,  2: “vanuma”,   3: “mirnuma”,
4: “lorenuma”, 5: “sevinuma”, 6: “havenuma”,
7: “belanuma”, 8: “yovenuma”, 9: “zavenuma”,
}

NUM_SEPARATOR = “mirévali”

def place_to_vevery(place: int) -> str:
“”“Convert a place index (1=ones, 2=tens, …) to its Vevery je- expression.”””
digits = str(place)
if len(digits) == 1:
return f”je{PLACE_WORDS[place]}”
# Multi-digit place: use [count] unj [digits] format
count  = PLACE_WORDS[len(digits)]
parts  = [DIGIT_WORDS[d] for d in digits]
return f”je-{count} unj {’ ’.join(parts)}”

def number_to_vevery(n: str) -> str:
n = n.replace(”,”, “”).replace(”_”, “”)
if not n.isdigit():
return None
if len(n) == 1:
return DIGIT_WORDS[n]
count = PLACE_WORDS.get(len(n))
if not count:
count = number_to_vevery(str(len(n)))
digits = “ “.join(DIGIT_WORDS[d] for d in n)
return f”{count} {NUM_SEPARATOR} {digits}”

def is_number_token(word: str) -> bool:
“”“Return True if the token looks like a number (digits and commas only).”””
cleaned = word.replace(”,”, “”).replace(”_”, “”)
return cleaned.isdigit() and len(cleaned) > 0

# ── Sentence Translation ──────────────────────────────────────────────────────

def lemmatize_token(token: str) -> list:
“””
Return a list of candidate base forms for a token, in priority order.
Tries nltk lemmatizer first, then simple suffix stripping as fallback.
“””
candidates = []

```
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
```

def resolve_english_token(conn: sqlite3.Connection, token: str):
“”“Resolve a single English token to its Vevery word, checking redirects.”””
# Number check
if is_number_token(token):
result = number_to_vevery(token)
if result:
return result, None

```
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

# Concept graph fallback
expr, concept_name, method = resolve_via_concept(conn, token)
if expr:
    return expr, None

return None, token  # unknown
```

def resolve_vevery_token(conn: sqlite3.Connection, token: str):
“”“Resolve a single Vevery token to its English word.”””
row = lookup_vevery(conn, token)
if row:
return row[0], None
return None, token  # unknown

def strip_punctuation(token: str):
“””
Split a token into (leading_punct, core_word, trailing_punct).
Apostrophes that are part of a word (c’, ul’, don’t) are preserved.
Only sentence-level punctuation (.,!?;:) is stripped from edges.
“””
SENTENCE_PUNCT = set(’.,!?;:’)
lead  = “”
trail = “”
word  = token

```
# Strip leading sentence punctuation only
while word and word[0] in SENTENCE_PUNCT:
    lead += word[0]
    word  = word[1:]

# Strip trailing sentence punctuation only
while word and word[-1] in SENTENCE_PUNCT:
    trail = word[-1] + trail
    word  = word[:-1]

return lead, word, trail
```

def translate_sentence(conn: sqlite3.Connection, sentence: str, direction: str):
“””
Translate a sentence word by word, preserving punctuation.
direction: ‘en’ (English→Vevery) or ‘ve’ (Vevery→English)
Returns (translated_tokens, missing_tokens).
“””
tokens = sentence.strip().split()
translated = []
missing = []

```
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
```

def menu_translate_sentence(conn: sqlite3.Connection):
print(”\n  Translate Sentence”)
print(”  [1] English → Vevery”)
print(”  [2] Vevery  → English”)
print(”  [b] Back”)
choice = prompt(”  > “).lower()

```
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
```

# ── Command Injection ─────────────────────────────────────────────────────────

import shlex

def parse_command(line: str, conn: sqlite3.Connection) -> str:
“”“Parse and execute a single !command. Returns a result string.”””
line = line.strip()
if not line or not line.startswith(”!”):
return f”  Skipped (not a command): {line}”

```
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

# ── !add concept "name" "cluster" "opposites" "category" "expression" ──
elif cmd == "add" and len(parts) >= 2 and parts[1].lower() == "concept":
    args = parts[2:]
    if len(args) < 1:
        return "  !add concept requires at least a name."
    name       = args[0]
    cluster    = args[1] if len(args) > 1 else ""
    opposites  = args[2] if len(args) > 2 else ""
    category   = args[3] if len(args) > 3 else ""
    expression = args[4] if len(args) > 4 else ""
    existing = get_concept(conn, name)
    if existing:
        update_concept(conn, name, cluster, opposites, category, expression)
        return f'  Updated concept: "{name}"'
    ok, err = add_concept(conn, name, cluster, opposites, category, expression)
    return f'  Added concept: "{name}"' if ok else f'  Error: {err}'

# ── !rm concept "name" ──
elif cmd == "rm" and len(parts) >= 2 and parts[1].lower() == "concept":
    if len(parts) < 3:
        return "  !rm concept requires a name."
    name = parts[2]
    if not get_concept(conn, name):
        return f'  Not found: "{name}"'
    delete_concept(conn, name)
    return f'  Removed concept: "{name}"'

else:
    return f"  Unknown command: {line}"
```

def menu_inject(conn: sqlite3.Connection):
print(”\n  Command Injection”)
print(”  Paste semicolon-separated commands, then press Enter twice.”)
print(”  Syntax:”)
print(’    !add entry “english” “vevery” “pronunciation” “notes”;’)
print(’    !add redirect “alias” “english”;’)
print(’    !rm entry “english”;’)
print(’    !rm redirect “alias”;’)
print(’    !edit “english” “field” “new value”;’)
print()

```
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
```

def menu_translate(conn: sqlite3.Connection):
print(”\n  Translate”)
print(”  [1] English → Vevery”)
print(”  [2] Vevery  → English”)
print(”  [b] Back”)
choice = prompt(”  > “).lower()

```
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
```

def menu_add(conn: sqlite3.Connection, prefill_english: str = “”):
print(”\n  Add new word”)
english = prompt(f”  English [{prefill_english}]: “, prefill_english).lower()
if not english:
print(”  Cancelled.”)
return

```
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
```

def menu_edit(conn: sqlite3.Connection):
print(”\n  Edit word”)
word = prompt(”  English word to edit: “).lower()
row = lookup_english(conn, word)
if not row:
print(f’\n  “{word}” not found.’)
input()
return

```
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
```

def menu_redirects(conn: sqlite3.Connection):
while True:
print(”\033c”, end=’’)
print(”\n  Redirects”)
print(”  [1] Add redirect”)
print(”  [2] Delete redirect”)
print(”  [3] List redirects”)
print(”  [b] Back”)
choice = prompt(”  > “).lower()
print(”\033c”, end=’’)

```
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
```

def print_concept(row):
name, cluster, opposites, category, expression = row
print(f”\n  Name:       {name}”)
print(f”  Category:   {category or ‘—’}”)
print(f”  Cluster:    {cluster or ‘—’}”)
print(f”  Opposites:  {opposites or ‘—’}”)
print(f”  Expression: {expression or ‘(auto-generated)’}”)

def menu_concepts(conn: sqlite3.Connection):
while True:
print(”\033c”, end=’’)
print(”\n  Concept Graph”)
print(”  [1] Add concept”)
print(”  [2] Edit concept”)
print(”  [3] Delete concept”)
print(”  [4] List concepts”)
print(”  [5] Lookup concept”)
print(”  [b] Back”)
choice = prompt(”  > “).lower()
print(”\033c”, end=’’)

```
    if choice == "1":
        name = prompt("  Concept name (English): ").lower()
        if not name:
            print("  Cancelled.")
            input()
            continue
        if get_concept(conn, name):
            print(f'  "{name}" already exists. Use Edit to modify.')
            input()
            continue
        print("  Enter related words as comma-separated list.")
        cluster   = prompt("  Cluster (e.g. knowledge,belief,reality): ").lower()
        opposites = prompt("  Opposites (e.g. illusion,lie,doubt): ").lower()
        category  = prompt("  Category (e.g. abstract,emotion,action): ").lower()
        expression = prompt("  Vevery expression override (optional): ")
        ok, err = add_concept(conn, name, cluster, opposites, category, expression)
        if ok:
            print(f'\n  Added concept: "{name}"')
            # Show what expression would be generated
            row = get_concept(conn, name)
            expr = _concept_to_expression(conn, row)
            print(f'  Generated expression: {expr or "(none — add cluster words to dictionary)"}')
        else:
            print(f'  Error: {err}')
        input()

    elif choice == "2":
        name = prompt("  Concept to edit: ").lower()
        row = get_concept(conn, name)
        if not row:
            print(f'  "{name}" not found.')
            input()
            continue
        print_concept(row)
        print("\n  Leave blank to keep current value. Dash [-] to clear.\n")
        _, cluster, opposites, category, expression = row
        new_cluster    = prompt(f"  Cluster [{cluster}]: ")
        new_opposites  = prompt(f"  Opposites [{opposites}]: ")
        new_category   = prompt(f"  Category [{category}]: ")
        new_expression = prompt(f"  Expression [{expression}]: ")
        def _val(new, old): 
            if new == "-": return ""
            return new if new else old
        update_concept(conn, name,
            _val(new_cluster, cluster),
            _val(new_opposites, opposites),
            _val(new_category, category),
            _val(new_expression, expression)
        )
        print(f'  Updated concept: "{name}"')
        input()

    elif choice == "3":
        name = prompt("  Concept to delete: ").lower()
        row = get_concept(conn, name)
        if not row:
            print(f'  "{name}" not found.')
            input()
            continue
        confirm = prompt(f'  Delete concept "{name}"? (y/n): ').lower()
        if confirm == "y":
            delete_concept(conn, name)
            print("  Deleted.")
        input()

    elif choice == "4":
        rows = list_concepts(conn)
        if not rows:
            print("\n  No concepts defined.")
        else:
            print(f"\n  {'Name':<20} {'Category':<15} {'Cluster'}")
            print("  " + "─" * 65)
            for row in rows:
                name, cluster, opposites, category, expression = row
                cluster_preview = cluster[:30] + "..." if len(cluster) > 30 else cluster
                print(f"  {name:<20} {(category or '—'):<15} {cluster_preview or '—'}")
            print(f"\n  {len(rows)} concept(s) total.")
        input()

    elif choice == "5":
        name = prompt("  Concept name or word: ").lower()
        row = get_concept(conn, name)
        if row:
            print_concept(row)
            expr = _concept_to_expression(conn, row)
            print(f'\n  → Vevery expression: {expr or "(none)"}')
        else:
            # Search clusters and opposites
            expr, concept_name, method = resolve_via_concept(conn, name)
            if expr:
                print(f'\n  "{name}" found via {method} of concept "{concept_name}"')
                print(f'  → Vevery expression: {expr}')
            else:
                print(f'  "{name}" not found in concept graph.')
        input()

    elif choice == "b":
        break
```

def menu_delete(conn: sqlite3.Connection):
print(”\n  Delete word”)
word = prompt(”  English word to delete: “).lower()
row = lookup_english(conn, word)
if not row:
print(f’  “{word}” not found.’)
return
print()
print_entry(row)
confirm = prompt(”  Delete this entry? (y/n): “).lower()
if confirm == “y”:
delete_word(conn, word)
print(”  Deleted.”)

def menu_list(conn: sqlite3.Connection):
rows = list_all(conn)
if not rows:
print(”\n  Dictionary is empty.”)
return
print(f”\n  {‘English’:<20}   {‘Vevery’:<20}  Pronunciation / Notes”)
print(”  “ + “─” * 70)
for row in rows:
print_entry(row)
print(f”\n  {len(rows)} word(s) total.”)
input()

# ── Main loop ────────────────────────────────────────────────────────────────

def ensure_nltk():
“”“Download required nltk data if not already present.”””
try:
import nltk
try:
from nltk.stem import WordNetLemmatizer
WordNetLemmatizer().lemmatize(“test”, “v”)
except LookupError:
print(”  Downloading language data (one-time setup)…”)
nltk.download(“wordnet”, quiet=True)
nltk.download(“omw-1.4”, quiet=True)
print(”  Done.\n”)
except ImportError:
print(”  Warning: nltk not installed. Run: pip install nltk”)
print(”  Lemmatizer fallback will be disabled.\n”)

def menu_export(conn: sqlite3.Connection):
import json
print(”\n  Export Dictionary”)
path = prompt(”  Output path [dictionary.json]: “, “dictionary.json”)

```
# Build dictionary entries
rows = list_all(conn)
entries = [
    {
        "english":       row[0],
        "vevery":        row[1],
        "pronunciation": row[2] or "",
        "notes":         row[3] or "",
    }
    for row in rows
]

# Build redirects
redirects = [
    {"alias": alias, "english": english}
    for alias, english in list_redirects(conn)
]

# Build concepts
concept_rows = list_concepts(conn)
concepts = [
    {
        "name":       row[0],
        "cluster":    row[1],
        "opposites":  row[2],
        "category":   row[3],
        "expression": row[4],
    }
    for row in concept_rows
]

export = {
    "language":  "Vevery",
    "version":   "1.0",
    "site":      "lucascw917.github.io/vevery/",
    "entries":   entries,
    "redirects": redirects,
    "concepts":  concepts,
}

try:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    print(f"\n  Exported {len(entries)} entries, {len(redirects)} redirects and {len(concepts)} concepts to {path}")
except Exception as e:
    print(f"\n  Error: {e}")
input()
```

def main():
ensure_nltk()
conn = sqlite3.connect(DB_FILE)
init_db(conn)

```
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
    print("  [9] Export to JSON")
    print("  [10] Concepts")
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
    elif choice == "9":
        menu_export(conn)
    elif choice == "10":
        menu_concepts(conn)
    elif choice in ("q", "quit", "exit"):
        print("\n  Goodbye.\n")
        conn.close()
        sys.exit(0)
    else:
        print("  Unknown option.")
        input()
```

if **name** == “**main**”:
main()