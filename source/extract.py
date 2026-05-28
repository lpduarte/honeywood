#!/usr/bin/env python3
"""Definitive extractor: parse clean OCR text into structured letter records.
Output: ../data/letters.json
"""
from __future__ import annotations
import re, json
from pathlib import Path
from difflib import SequenceMatcher
from datetime import date

SRC = Path(__file__).parent
FULL = (SRC / 'honeywood_full.txt').read_text(encoding='utf-8')
CORR = json.loads((SRC / 'corrections.json').read_text(encoding='utf-8'))

# ---------- Entity resolution ----------
# canonical key -> (display name, role/qualification). Roles are taken from the book's own
# header descriptors (e.g. "BEDDY & TINGE, QUANTITY SURVEYORS") or its narrative.
PEOPLE = {
    'SPINLOVE':   ('James Spinlove', 'Architect'),
    'BRASH':      ('Sir Leslie Brash', None),
    'LADY BRASH': ('Lady Brash', None),
    'GRIGBLAY':   ('Mr. Grigblay', 'Builder'),
    'POTCH':      ('Mr. Potch', 'District Surveyor'),
    'HOOCHKOFT':  ('Messrs. Hoochkoft', None),
    'PINTLE':     ('Mr. Pintle', None),
    'WYCHETE':    ('William Wychete', 'Arbitrator'),
    'TINGE':      ('Mr. Tinge', 'Quantity Surveyor'),
    'BLOGGS':     ('Bloggs', 'Foreman'),
    'BULLJOHN':   ('George Bulljohn', 'Magistrate, J.P.'),
    'WHITTLE':    ('Sir Geoffrey Whittle', 'F.R.S., M.I.C.E.'),
    'PHYLLIS BRASH': ('Miss Phyllis Brash', None),
    'DALBET':     ('Frederick Dalbet', None),
    'DISTRICT SURVEYOR': ('The District Surveyor', 'Marlord R.D.C.'),
    'CLERK':      ('The Clerk', 'Marlord R.D.C.'),
}
FIRMS = {
    'NIBNOSE & RASPER': ('Nibnose & Rasper', 'Builders'),
    'WREEK & CO':       ('Wreek & Co.', 'Sanitary Specialists'),
    'RUSS & CO':        ('Russ & Co.', 'Solicitors'),
    'REAKER & SMITH':   ('Reaker & Smith', None),
    'THUMPER & CO':     ('Thumper & Co.', None),
    'BEDDY & TINGE':    ('Beddy & Tinge', 'Quantity Surveyors'),
    'DOMO IDEALO LTD':  ('Domo Idealo Ltd.', None),
}
GROUPS = {
    'VARIOUS BUILDERS':      ('Various Builders', None),
    'UNSUCCESSFUL BUILDERS': ('Unsuccessful Builders', None),
}
# Hand aliases for OCR/format variants -> canonical key
ALIASES = {
    'JAMES SPINLOVE': 'SPINLOVE', 'SPIN LOVE': 'SPINLOVE', 'SPINLOYE': 'SPINLOVE',
    'SPIXLOVE': 'SPINLOVE', 'SPIXLOYE': 'SPINLOVE', 'SPJXLOYE': 'SPINLOVE',
    'SIR LESLIE BRASH': 'BRASH', 'BRASII': 'BRASH', 'SPIXLOVE BRASH': 'BRASH',
    'MISS BRASH': 'PHYLLIS BRASH', 'WILLIAM WYCHETE': 'WYCHETE',
    'NIBIOSE & RASPER': 'NIBNOSE & RASPER', 'WREEN & CO': 'WREEK & CO', 'WREEK': 'WREEK & CO',
    'CRIGBLAY': 'GRIGBLAY', 'GIRGBLAY': 'GRIGBLAY',
    'FREDERICK DALBET': 'DALBET', 'GEORGE BULLJOHN': 'BULLJOHN',
    'SIR GEOFFREY WHITTLE': 'WHITTLE', 'GEOFFREY WHITTLE': 'WHITTLE',
    'MISS PHYLLIS BRASH': 'PHYLLIS BRASH',
    'DISTRICT SURVEYOR': 'DISTRICT SURVEYOR', 'SURVEYOR': 'DISTRICT SURVEYOR',
    'CLERK': 'CLERK',
    'EWART HOOCHKOFT & CO': 'HOOCHKOFT', 'EWART HOOCHKOFT & CO LTD': 'HOOCHKOFT',
}
# Single common words that must never be treated as an entity (chapter-title noise)
NOISE_WORDS = {'WORK', 'GET', 'THE', 'AND', 'FILE', 'SAME', 'SAID'}
ROLE_SUFFIX = re.compile(r'\b(SOLICITORS?|SURVEYOR|CLERK|LTD|CO|BUILDERS?|SPECIALISTS?|SURVEYORS?)\b')

ALL_KEYS = {**{k: ('person', *v) for k, v in PEOPLE.items()},
            **{k: ('firm', *v) for k, v in FIRMS.items()},
            **{k: ('group', *v) for k, v in GROUPS.items()}}  # key -> (kind, name, role)

def extract_qualifier(raw: str):
    """Pull the professional descriptor that follows the name in THIS header (e.g.
    'BEDDY & TINGE, QUANTITY SURVEYORS' -> 'Quantity Surveyors'). Faithful to the book:
    returns None when the header carries no descriptor."""
    parts = [p.strip(' .') for p in raw.split(',')]
    if len(parts) <= 1:
        return None
    quals = []
    for q in parts[1:]:
        qu = q.upper().strip()
        if qu in ('', 'LTD', 'CO', 'ESQ', 'ESO'):
            continue
        quals.append(q)
    if not quals:
        return None
    words = []
    for w in ' '.join(quals).split():
        if w.upper().strip('.') in ('ESQ', 'ESO'):
            continue
        words.append(w.upper() if '.' in w else w.capitalize())
    return ' '.join(words) or None

def clean_entity_raw(raw: str) -> str:
    # Drop honorifics/qualifications: ESQ, A.R.I.B.A, J.P, SOLICITORS, BUILDERS suffix, etc.
    s = raw.upper().strip(' .,')
    s = re.sub(r'\s+', ' ', s)
    # cut at first comma-qualifier (e.g., "POTCH, SURVEYOR, MARLFORD" -> "POTCH")
    s = re.split(r',', s)[0].strip()
    s = re.sub(r'\b(ESQ|ESO|J\.?P|A\.?R\.?I\.?B\.?A|P\.?P\.?R\.?I\.?B\.?A|F\.?R\.?S|M\.?I\.?C\.?E)\b', '', s).strip(' .')
    return s

def resolve_entity(raw: str):
    """Return (key, kind, name, role) or None."""
    s = clean_entity_raw(raw)
    if not s or len(s) < 3:
        return None
    if s in ALIASES:
        s = ALIASES[s]
    if s in ALL_KEYS:
        kind, name, role = ALL_KEYS[s]
        return (s, kind, name, role)
    # firm forms: keep ampersand groups
    if '&' in s:
        best = max(FIRMS, key=lambda k: SequenceMatcher(None, s, k).ratio())
        if SequenceMatcher(None, s, best).ratio() >= 0.75:
            return (best, 'firm', FIRMS[best][0], FIRMS[best][1])
        return (s, 'firm', s.title(), None)
    # fuzzy against people
    best = max(PEOPLE, key=lambda k: SequenceMatcher(None, s.replace(' ', ''), k.replace(' ', '')).ratio())
    if SequenceMatcher(None, s.replace(' ', ''), best.replace(' ', '')).ratio() >= 0.8:
        return (best, 'person', PEOPLE[best][0], PEOPLE[best][1])
    return None

# ---------- Header detection (own-line) ----------
HEADER_RE = re.compile(r'(?:^|\n)[ \t]*(?:\(([A-Z]+)\)\s*)?([A-Z][A-Z&.,\'’ ]{2,50}?)\s+TO\s+([A-Z][A-Z&.,\'’ ]{2,50}?)[ \t]*(?:[\dIlOoSs][\dIlOoSs.\-/,•·]*\.?)?[ \t]*(?=\n)')

page_offsets = [(m.start(), int(m.group(1))) for m in re.finditer(r'<<<PAGE (\d+)>>>', FULL)]
def char_to_page(pos):
    p = 0
    for off, num in page_offsets:
        if off > pos: break
        p = num
    return p

def plausible(raw, resolved):
    """A header side is plausible if it resolves, or looks like a genuine new entity."""
    if resolved is not None:
        return True
    s = re.sub(r'\s+', ' ', raw.upper().strip(' .,'))
    first = re.split(r'[ ,]', s)[0]
    if first in NOISE_WORDS or s in NOISE_WORDS:
        return False
    # genuine entity: multi-word, has '&', or carries a role suffix
    return (' ' in s) or ('&' in s) or bool(ROLE_SUFFIX.search(s))

raw_headers = []
for m in HEADER_RE.finditer(FULL):
    kind_raw, s_raw, r_raw = m.group(1), m.group(2), m.group(3)
    s = resolve_entity(s_raw)
    r_is_same = re.sub(r'[\s.]','',r_raw.upper()) in ('THESAME','SAME')
    r = ('SAME','same','The Same',None) if r_is_same else resolve_entity(r_raw)
    # Reject chapter-title / prose noise: both sides must be plausible, >=1 must resolve.
    if not r_is_same:
        if not (plausible(s_raw, s) and plausible(r_raw, r)):
            continue
        if s is None and r is None:
            continue
    else:
        if s is None:  # "THE SAME" with unresolved sender = noise
            continue
    raw_headers.append({
        'pos': m.start(), 'end': m.end(3),
        'kind': (kind_raw or '').lower(),
        's_raw': s_raw.strip(), 'r_raw': r_raw.strip(),
        's': s, 'r': r, 'r_is_same': r_is_same,
        'page': char_to_page(m.start(2)),
    })

# Resolve "THE SAME" -> previous recipient
for i, h in enumerate(raw_headers):
    if h['r_is_same'] and i > 0:
        h['r'] = raw_headers[i-1]['r']

# ---------- Date extraction ----------
DIGIT = r'[\dIlOoSs]'
SEP = r'[.\-/,•·]'
DATE_RE = re.compile(rf'\b({DIGIT}{{1,2}})\s*{SEP}?\s*({DIGIT}{{1,2}})\s*{SEP}\s*({DIGIT}{{2}})\.?')
def ocr_int(s):
    s = (s.replace('I','1').replace('l','1').replace('O','0')
           .replace('o','0').replace('S','5').replace('s','5'))
    try: return int(s)
    except: return -1

def extract_date(chunk):
    for dm in DATE_RE.finditer(chunk[:600]):
        d, m, y = ocr_int(dm.group(1)), ocr_int(dm.group(2)), ocr_int(dm.group(3))
        if 1 <= d <= 31 and 1 <= m <= 12 and 24 <= y <= 26:
            return f"19{y:02d}-{m:02d}-{d:02d}", dm.group(0)
    return None, None

# ---------- Closing salutations (mark end of body, start of commentary) ----------
CLOSINGS = [
    'Yours faithfully','Yours sincerely','Yours truly','Yours obediently',
    'Yours to oblige','Yours respectfully','I am, Sir','I remain, Sir',
    'Believe me','Best wishes from','Your obedient servant','Yours',
]
CLOSE_RE = re.compile(
    r'(?i)\b(' + '|'.join(re.escape(c) for c in CLOSINGS) + r')\b[ ,.;:]*'
)

def split_body_commentary(chunk):
    """Return (body, commentary). Commentary = italic editorial note after closing."""
    matches = list(CLOSE_RE.finditer(chunk))
    if not matches:
        return chunk.strip(), None
    last = matches[-1]
    body = chunk[:last.end()].strip()
    tail = chunk[last.end():].strip()
    # Strip a leading signature line from the tail (short name before commentary)
    # Commentary tends to be a full sentence; signature is short.
    if tail and len(tail) < 40 and '.' not in tail:
        return body, None  # tail is just a signature
    return body, (tail or None)

# ---------- Build records ----------
def book_to_send(book_iso):
    y, m, d = map(int, book_iso.split('-'))
    return date(y + 102, m, d).isoformat()  # 1924->2026

date_fixes = CORR.get('date_fixes', [])
def apply_fix(page, body):
    bn = re.sub(r'\s+', ' ', body).strip()
    for f in date_fixes:
        if f['page'] == page and (bn.startswith(f['starts']) or f['starts'] in bn[:80]):
            return f['date']
    return None

records = []
within_page = {}
for i, h in enumerate(raw_headers):
    w = within_page.get(h['page'], 0); within_page[h['page']] = w + 1
    rid = f"L{h['page']:03d}-{w}"   # stable id: survives insertions on OTHER pages
    body_start = h['end']
    body_end = raw_headers[i+1]['pos'] if i+1 < len(raw_headers) else len(FULL)
    chunk = FULL[body_start:body_end]
    chunk = re.sub(r'<<<PAGE \d+>>>', ' ', chunk)
    # Drop running page-header lines: "THE HONEYWOOD FILE 29" / "29 THE HONEYWOOD FILE"
    chunk = re.sub(r'\b\d{0,3}\s*THE HONEYWOOD FILE\s*\d{0,3}\b', ' ', chunk)
    chunk = re.sub(r'\s+', ' ', chunk).strip()

    date_iso, date_raw = extract_date(chunk)
    body, commentary = split_body_commentary(chunk)
    fixed = apply_fix(h['page'], body)
    if fixed:
        date_iso, date_raw = fixed, 'CORRECTED'

    s = h['s']; r = h['r']
    from_key = s[0] if s else h['s_raw']
    from_disp = s[2] if s else h['s_raw'].title()
    to_key = r[0] if r else h['r_raw']
    to_disp = r[2] if r else h['r_raw'].title()
    # Roles come from THIS header's own descriptor, not a canonical map (faithful to book).
    from_role = extract_qualifier(h['s_raw'])
    to_role = None if h['r_is_same'] else extract_qualifier(h['r_raw'])
    for ef in CORR.get('entity_fixes', []):
        if ef['page'] == h['page'] and ef.get('from_raw') == h['s_raw']:
            from_key, from_disp = ef['from_key'], ef['from']
            from_role = ef.get('from_role', from_role)
        if ef['page'] == h['page'] and ef.get('to_raw') == h['r_raw']:
            to_key, to_disp = ef['to_key'], ef['to']
            to_role = ef.get('to_role', to_role)
    records.append({
        'id': rid,
        'seq': i,
        'page': h['page'],
        'kind': h['kind'] or 'letter',
        'book_date': date_iso,
        'send_date': book_to_send(date_iso) if date_iso else None,
        'from_key': from_key,
        'from': from_disp,
        'from_role': from_role,
        'to_key': to_key,
        'to': to_disp,
        'to_role': to_role,
        's_raw': h['s_raw'], 'r_raw': h['r_raw'],
        'date_raw': date_raw,
        'body': body,
        'commentary': commentary,
        'body_chars': len(body),
        'needs_date': date_iso is None,
    })

# ---------- Chapter assignment ----------
# Canonical chapter titles (cleaned). Detected by first occurrence in the body.
CHAPTERS = [
    "The File is Opened", "The Commission", "Sketches and Estimates",
    "Catastrophe of the Trial Holes", "Preparation for Tenders", "The Tenders Go Wrong",
    "Grigblay and Brash Get to Work", "The District Surveyor Intervenes",
    "The Affair of the Spring", "Trouble with Bricks", "More Difficulties",
    "Brash on Bricks", "A Box of Cigars", "Carrying On", "A Sanitary Expert Appears",
    "The Thick of the Fight", "The Last of the Spring", "Spinlove's Special Roof",
    "Mr. Potch Again Objects", "The Stairs Go Wrong", "Spinlove Applies for Fees",
    "The Water Comes In", "Lady Brash Takes Charge", "A Storm in a Paint Pot",
    "Sir Leslie Brash Takes Charge", "Spinlove Takes Charge", "The Affair of the Cottages",
    "Lady Brash Causes a Diversion", "Spinlove Uses Tact", '"Nibrasp" Asks Compensation',
    "Difficulties and Delays", "Sir Leslie Brash Moves In",
]
def norm(s): return re.sub(r'[^A-Z]', '', s.upper())
# find first body occurrence (offset) of each chapter title
chapter_at = []  # (offset, title)
for title in CHAPTERS:
    nt = norm(title)
    # scan lines of FULL for a line whose normalized form startswith/equals nt
    best = None
    for m in re.finditer(r'(?:^|\n)([^\n]+)', FULL):
        if m.start() < 0: continue
        if norm(m.group(1))[:len(nt)] == nt and len(norm(m.group(1))) <= len(nt) + 3:
            # skip the contents page (first ~ page 4)
            if char_to_page(m.start()) >= 5:
                best = m.start(); break
    if best is not None:
        chapter_at.append((best, title))
chapter_at.sort()

def chapter_for(pos):
    cur = None
    for off, title in chapter_at:
        if off <= pos: cur = title
        else: break
    return cur

# chapter per record, by its header position
header_pos = {id(records[i]): h['pos'] for i, h in enumerate(raw_headers) if i < len(records)}
for r in records:
    r['chapter'] = chapter_for(header_pos.get(id(r), 0))

# Inject hand-declared extra letters (inline-merged headers the OCR scrambled). Their
# body comes from data/cleaned.json; here we only register the record + metadata.
host_by_id = {r['id']: r for r in records}
extra_off = {}
for ex in CORR.get('extra_letters', []):
    host = host_by_id.get(ex['after_id'])
    extra_off[ex['after_id']] = extra_off.get(ex['after_id'], 0) + 1
    records.append({
        'id': ex['id'], 'seq': (host['seq'] + 0.1 * extra_off[ex['after_id']]) if host else 10**9,
        'page': ex.get('page', host['page'] if host else 0),
        'kind': ex.get('kind', 'letter'),
        'book_date': ex['book_date'],
        'send_date': book_to_send(ex['book_date']),
        'from_key': ex['from_key'], 'from': ex['from'], 'from_role': ex.get('from_role'),
        'to_key': ex['to_key'], 'to': ex['to'], 'to_role': ex.get('to_role'),
        's_raw': '', 'r_raw': '', 'date_raw': 'EXTRA',
        'body': ex.get('body', ''), 'commentary': None,
        'body_chars': 0, 'needs_date': False,
        'chapter': host['chapter'] if host else None,
        'extra': True,
    })

# global reading order + chapter-start flag
records.sort(key=lambda r: r['seq'])
for n, r in enumerate(records):
    r['seq'] = n
seen_ch = set()
for r in records:
    ch = r.get('chapter')
    r['chapter_start'] = bool(ch and ch not in seen_ch)
    if ch: seen_ch.add(ch)

# ---------- Stats ----------
print(f"Total records:        {len(records)}")
print(f"With date:            {sum(1 for r in records if r['book_date'])}")
print(f"Without date:         {sum(1 for r in records if not r['book_date'])}")
print(f"With commentary:      {sum(1 for r in records if r['commentary'])}")
unresolved = [r for r in records if r['from_key'] not in ALL_KEYS and r['from_key']!='SAME' or (r['to_key'] not in ALL_KEYS and r['to_key']!='SAME')]
print(f"Unresolved entity:    {len(unresolved)}")
dated = [r['book_date'] for r in records if r['book_date']]
print(f"Date range:           {min(dated)} -> {max(dated)}")
TODAY = date(2026,5,28)
future = [r for r in records if r['send_date'] and date.fromisoformat(r['send_date'])>=TODAY]
print(f"Future (will send):   {len(future)}")
print(f"Past (skip):          {sum(1 for r in records if r['send_date'] and date.fromisoformat(r['send_date'])<TODAY)}")

out = SRC.parent / 'data' / 'letters.json'
out.write_text(json.dumps(records, indent=2, ensure_ascii=False))
print(f"\nWrote {out} ({len(records)} records)")
