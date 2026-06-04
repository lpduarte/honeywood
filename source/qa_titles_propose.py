#!/usr/bin/env python3
"""Per-record from/to proposal, faithful to each letter's book header.

Rule of fidelity: take the RAW book header for the letter. If a side is a BARE
single surname, the title stays bare (title-cased) — we do NOT expand it to a
fuller gazetteer/firm form. Only when the header itself carries the fuller form
(honorific, initials, '&', post-nominals, ', Ltd.' ...) do we keep the workflow's
normalized full form. Roles (', Quantity Surveyors' etc.) are stripped from the
NAME (they live in *_role). 'THE SAME' -> previous letter's recipient.

Read-only: writes /tmp/hwqa/titles_proposed.json and prints a review digest.
"""
from __future__ import annotations
import json, re
from pathlib import Path
SRC = Path(__file__).parent
import sys; sys.path.insert(0, str(SRC))
from build import load_merged

titlemap = json.load(open('/tmp/hwqa/titlemap.json'))
raw = json.load(open('/tmp/hwqa/titles_raw.json'))['raw_by_rec']
recs = {r['id']: r for r in load_merged()}
order = sorted(recs.values(), key=lambda r: r['seq'])

SALUT = re.compile(r'^\s*(Dear [^,]+,|Sir,|Madam,)\s*', re.I)
MARKER = re.compile(r'\([^)]*\)')
DATE = re.compile(r'\s*\d{1,2}\s*[.\s/]\s*\d{1,2}\s*[.\s/]\s*\d{2,4}\.?\s*$')
GARBLE = {'BRANBLE': 'Bramble', 'GRICBLAY': 'Grigblay', 'GRIGELAY': 'Grigblay',
          'GRIGBLAT': 'Grigblay', 'GRIGBLAI': 'Grigblay', 'BEDDI': 'Beddy', 'WREEK': 'Wreek & Co.'}
# OCR sometimes drops a firm/person's name leaving only the role, or appends a place/office.
LONE_ROLE = {'Solicitors', 'Builders', 'Quantity Surveyors', 'Sanitary Specialists', 'Surveyor'}
PERSON_QUAL = re.compile(r'^(Spinlove|Brash|Grigblay|Potch|Tinge|Pintle|Wychete|Bulljohn|Bloggs)\s*,.*$')
# Not-found records keep their value, but normalize the core cast to the bare book form.
NOTFOUND_FIX = {'Mr. Grigblay': 'Grigblay', 'James Spinlove': 'Spinlove', 'Sir Leslie Brash': 'Brash',
                'Mr. Potch': 'Potch', 'Mr. Tinge': 'Tinge', 'Mr. Pintle': 'Pintle'}

def clean_raw(h):
    h = MARKER.sub(' ', h); h = SALUT.sub('', h); h = DATE.sub('', h)
    return re.sub(r'\s+', ' ', h.replace('•', ' ')).strip().strip('-').strip()
def split_raw(h):
    parts = re.split(r'\s+TO\s+', clean_raw(h), maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip().strip(',').strip(), parts[1].strip().strip(',').strip()
    return None, None
def is_bare(side):
    return bool(side) and bool(re.fullmatch(r"[A-Za-z][A-Za-z'.-]*", side.strip().strip('.,')))
def bare_form(side):
    t = side.strip().strip(' .,-')
    return GARBLE.get(t.upper(), t.capitalize())

ROLE_SUFFIX = re.compile(r',\s*(Quantity Surveyors?|Builders?|Solicitors?|Sanitary Specialists?)\s*$', re.I)
def strip_role(name):
    return ROLE_SUFFIX.sub('', name).strip().rstrip(',').strip()

def faithful_side(raw_side, wf_value):
    """Bare header -> bare title; otherwise keep the workflow's normalized full form."""
    if raw_side is None:
        return wf_value
    if is_bare(raw_side):
        return bare_form(raw_side)
    return wf_value

prop, last_to = {}, None
stats = {'changed': 0, 'same': 0, 'notfound': 0, 'the_same': 0, 'debared': 0}
for r in order:
    rid = r['id']; h = raw.get(rid); item = titlemap.get(h) if h else None
    if not item:
        stats['notfound'] += 1
        nf2 = NOTFOUND_FIX.get(r.get('from'), r.get('from'))
        nt2 = NOTFOUND_FIX.get(r.get('to'), r.get('to'))
        prop[rid] = {'from': nf2, 'to': nt2, 'note': 'no-header:normalized'}
        last_to = nt2; continue
    rf, rt = split_raw(h)
    nf = faithful_side(rf, item['from'])
    nt = item['to']
    if (rt or '').upper() == 'THE SAME' or nt == 'THE SAME':
        nt = last_to or r.get('to'); stats['the_same'] += 1
    else:
        nt = faithful_side(rt, item['to'])
    if nf != item['from'] or (nt != item['to'] and nt != (last_to or '')): stats['debared'] += 1
    nf, nt = strip_role(nf), strip_role(nt)
    # collapse "Potch, Surveyor, Marlford" / "Brash, Penzance" -> bare surname
    if PERSON_QUAL.match(nf): nf = nf.split(',')[0].strip()
    if PERSON_QUAL.match(nt): nt = nt.split(',')[0].strip()
    # a header that lost its firm name (just a role) -> fall back to current value
    if nf in LONE_ROLE: nf = r.get('from')
    if nt in LONE_ROLE: nt = r.get('to')
    last_to = nt
    prop[rid] = {'from': nf, 'to': nt, 'note': item.get('note', '')}
    if (nf, nt) != (r.get('from'), r.get('to')): stats['changed'] += 1
    else: stats['same'] += 1

json.dump(prop, open('/tmp/hwqa/titles_proposed.json', 'w'), ensure_ascii=False, indent=2)
print('stats:', stats)
from collections import Counter
nn = Counter()
for p in prop.values(): nn[p['from']] += 1; nn[p['to']] += 1
print('\n--- distinct NEW from/to forms (count) ---')
for v, n in sorted(nn.items(), key=lambda kv: -kv[1]): print(f'  {n:3}  {v}')
print('\n--- non-bare (full/honorific/firm) forms that will appear, by record ---')
for rid in [r['id'] for r in order]:
    p = prop[rid]
    for side in ('from', 'to'):
        v = p[side]
        if v and not re.fullmatch(r"[A-Z][a-z'.-]*", v) and 'no-header' not in p['note']:
            print(f'  {rid:9} {side}: {v!r}'); break
print('\nkept (no header found):', [rid for rid, p in prop.items() if p['note'] == 'no-header:kept'])
