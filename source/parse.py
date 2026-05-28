#!/usr/bin/env python3
"""Parser v2: stricter detection — only count headers where BOTH sides normalize to canonical chars."""
from __future__ import annotations
import re, json, glob, html
from pathlib import Path
from difflib import SequenceMatcher

# Canonical character names (sender/recipient labels as they should appear normalized)
CANONICAL = [
    "SPINLOVE", "BRASH", "LADY BRASH", "GRIGBLAY", "POTCH", "RASPER",
    "SMITH", "TINGE", "REAKER", "WYCHETE", "BLOGGS", "CLERK", "RIDDOPPO",
    "NIBNOSE", "SNITCH", "RUSPIDGE", "PINTLE", "HOOK", "HOOKHAM",
    "TAMBLIN", "BUCKSHORN", "MARLPIT", "MOON", "WALKER", "BLOATER",
    "PORLOCK", "POYSER", "DODD", "DAVIS", "HOOCHKOFT", "MILES",
    "BLUEPRINT", "BURTON", "GREENE", "TOWN COUNCIL", "MASTER",
]

# Normalize: strip whitespace, uppercase, remove dots
def canon_form(s: str) -> str:
    return re.sub(r'[\s.]+', '', s.upper())

CANONICAL_FORMS = {canon_form(c): c for c in CANONICAL}

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def normalize_name(raw: str) -> str | None:
    """Return canonical name if recognized, else None."""
    c = canon_form(raw)
    if not c or len(c) < 3:
        return None
    # Exact
    if c in CANONICAL_FORMS:
        return CANONICAL_FORMS[c]
    # Fuzzy: find canonical with high similarity
    best = max(CANONICAL_FORMS.keys(), key=lambda k: similarity(c, k))
    if similarity(c, best) >= 0.78:
        return CANONICAL_FORMS[best]
    return None

# Load text
full = Path('honeywood_full.txt').read_text(encoding='utf-8')

# Page offset map
page_offsets = [(m.start(), int(m.group(1))) for m in re.finditer(r'<<<PAGE (\d+)>>>', full)]
def char_to_page(pos):
    p = 0
    for off, num in page_offsets:
        if off > pos: break
        p = num
    return p

# Header regex: more permissive on sender/recipient sides to catch multi-word names
# We'll validate via normalize_name
HEADER_RE = re.compile(
    r'(?:^|[\s.,;:"!?])'
    r'([A-Z][A-Z .]{1,40}?)'       # sender (may have spaces, dots)
    r'\s+TO\s+'
    r'([A-Z][A-Z .]{1,40}?)'       # recipient
    r'(?=\s+(?:Dear|Sir|Madam|Re|Telegram|Memo|\d|My|[A-Z][a-z]))'  # followed by salutation/body marker
)

# Stricter: also accept if followed by another all-caps word that's NOT another "TO"
# We'll do post-filter using normalize_name

headers = []
seen_pos = set()
for m in HEADER_RE.finditer(full):
    sender_raw = m.group(1).strip(' .,;:"')
    recipient_raw = m.group(2).strip(' .,;:"')
    sender = normalize_name(sender_raw)
    recipient = normalize_name(recipient_raw)
    if not sender or not recipient:
        continue
    pos = m.start(1)  # actual sender start
    if pos in seen_pos:
        continue
    seen_pos.add(pos)
    headers.append({
        'pos': pos,
        'end': m.end(2),
        'sender_raw': sender_raw,
        'recipient_raw': recipient_raw,
        'sender': sender,
        'recipient': recipient,
        'page': char_to_page(pos),
    })

print(f"Strict-matched headers: {len(headers)}")

# Split into letter chunks
# Date regex variants:
#  - 6.2.24. / 6.2.24
#  - 6-2-24 / 6/2/24
#  - 24 3-24 (space)
#  - OCR corruption: I=1, l=1, O=0, o=0, S=5
# Allow digits OR these letter substitutions
DIGIT = r'[\dIlOoSs]'
SEP = r'[.\-/,•·]'
DATE_RE = re.compile(rf'\b({DIGIT}{{1,2}})\s*{SEP}?\s*({DIGIT}{{1,2}})\s*{SEP}\s*({DIGIT}{{2}})\.?')

def ocr_int(s: str) -> int:
    s = s.replace('I', '1').replace('l', '1').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5')
    try: return int(s)
    except: return -1

letters = []
for i, h in enumerate(headers):
    body_start = h['end']
    body_end = headers[i+1]['pos'] if i+1 < len(headers) else len(full)
    chunk = full[body_start:body_end]
    chunk_clean = re.sub(r'<<<PAGE \d+>>>', ' ', chunk)
    chunk_clean = re.sub(r'\s+', ' ', chunk_clean).strip()
    # Look for date in first 800 chars
    date = None
    date_raw = None
    for dm in DATE_RE.finditer(chunk_clean[:800]):
        d = ocr_int(dm.group(1))
        mn = ocr_int(dm.group(2))
        y = ocr_int(dm.group(3))
        if 1 <= d <= 31 and 1 <= mn <= 12 and 24 <= y <= 26:
            date = f"19{y:02d}-{mn:02d}-{d:02d}"
            date_raw = dm.group(0)
            break
    letters.append({
        'idx': i,
        'page': h['page'],
        'sender_raw': h['sender_raw'],
        'recipient_raw': h['recipient_raw'],
        'sender': h['sender'],
        'recipient': h['recipient'],
        'date': date,
        'date_raw': date_raw,
        'body_preview': chunk_clean[:300],
        'body_chars': len(chunk_clean),
    })

# Stats
print(f"Total letters: {len(letters)}")
print(f"With date:     {sum(1 for l in letters if l['date'])}")
print(f"Without date:  {sum(1 for l in letters if not l['date'])}")

from collections import Counter
pairs = Counter((l['sender'], l['recipient']) for l in letters)
print("\nAll normalized pairs (count):")
for (s, r), n in pairs.most_common():
    print(f"  {n:3d}  {s} → {r}")

# Letters without date: show first 5
print("\nFirst 10 letters without date (preview):")
no_date = [l for l in letters if not l['date']]
for l in no_date[:10]:
    print(f"  p{l['page']:3d}  {l['sender']} → {l['recipient']}")
    print(f"        body: {l['body_preview'][:150]}...")

# Date range
dated = [l['date'] for l in letters if l['date']]
print(f"\nDate range: {min(dated)} → {max(dated)}")

# Dates after today (2026-05-27 with year mapping 1924→2026)
# We need: book date converted to send date, then compare to today
from datetime import date as D
TODAY = D(2026, 5, 27)
def book_to_send(book_iso):
    y, m, d = map(int, book_iso.split('-'))
    send_y = y + (2026 - 1924)  # 1924→2026, 1925→2027, 1926→2028
    return D(send_y, m, d)

future = [l for l in letters if l['date'] and book_to_send(l['date']) >= TODAY]
past = [l for l in letters if l['date'] and book_to_send(l['date']) < TODAY]
print(f"\nDated letters in PAST (won't send): {len(past)}")
print(f"Dated letters in FUTURE (will send): {len(future)}")
if future:
    first = min(future, key=lambda l: l['date'])
    print(f"First future letter: {first['sender']} → {first['recipient']}, book {first['date']}, send {book_to_send(first['date'])}")

Path('letters_index.json').write_text(json.dumps(letters, indent=2, ensure_ascii=False))
print(f"\nWrote letters_index.json with {len(letters)} entries.")
