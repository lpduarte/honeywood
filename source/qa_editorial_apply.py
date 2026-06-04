#!/usr/bin/env python3
"""Apply the confirmed editorial-QA findings to the data, safely.

Reads the confirmed findings (default /tmp/hwqa/confirmed.json), then:
  - body / commentary  -> substring replace inside data/cleaned.json[id][field]
  - to / from / *_role -> set data/letters.json record[field] (verifying the
    current value first; "None" means null)
Every change is verified before it is made; anything that doesn't match exactly
is reported and skipped (never force-overwritten). Writes an audit trail to
source/editorial_corrections.json.

  python qa_editorial_apply.py            # dry-run: report only
  python qa_editorial_apply.py --apply    # write the changes
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = Path(__file__).parent
APPLY = '--apply' in sys.argv
FINDINGS = json.load(open(sys.argv[sys.argv.index('--findings') + 1] if '--findings' in sys.argv
                          else '/tmp/hwqa/confirmed.json'))

letters = json.load(open(ROOT / 'data' / 'letters.json'))
cleaned = json.load(open(ROOT / 'data' / 'cleaned.json'))
by_id = {r['id']: r for r in letters}

META = {'to', 'from', 'to_role', 'from_role', 'subject', 'chapter'}
TEXT = {'body', 'commentary'}
def as_none(v): return None if v in (None, '', 'None') else v

applied, failed = [], []
for f in FINDINGS:
    fid, field, cur, sug = f['id'], f['field'], f['current'], f['suggested']
    if field in TEXT:
        rec = cleaned.get(fid)
        if not rec or field not in rec:
            failed.append((fid, field, 'no cleaned record/field')); continue
        body = rec[field]
        n = body.count(cur)
        if n != 1:
            failed.append((fid, field, f'snippet occurs {n}x (need exactly 1)')); continue
        if APPLY: rec[field] = body.replace(cur, sug)
        applied.append((fid, field, cur[:40], sug[:40]))
    elif field in META:
        rec = by_id.get(fid)
        if not rec:
            failed.append((fid, field, 'no letters record')); continue
        have = rec.get(field)
        if as_none(have) != as_none(cur):
            failed.append((fid, field, f'current mismatch: have {have!r}, finding says {cur!r}')); continue
        if APPLY: rec[field] = as_none(sug)
        applied.append((fid, field, repr(have), repr(as_none(sug))))
    else:
        failed.append((fid, field, 'unknown field'))

print(f"{'APPLYING' if APPLY else 'DRY-RUN'}: {len(applied)} ok, {len(failed)} skipped\n")
print('--- OK ---')
for fid, field, a, b in applied:
    print(f'  {fid:9} {field:11} {a!r} -> {b!r}')
if failed:
    print('\n--- SKIPPED (need a look) ---')
    for fid, field, why in failed:
        print(f'  {fid:9} {field:11} {why}')

if APPLY:
    json.dump(letters, open(ROOT / 'data' / 'letters.json', 'w'), ensure_ascii=False, indent=2)
    json.dump(cleaned, open(ROOT / 'data' / 'cleaned.json', 'w'), ensure_ascii=False, indent=2)
    audit = SRC / 'editorial_corrections.json'
    prior = json.load(open(audit)) if audit.exists() else []
    prior.append({'applied': [{'id': a, 'field': b, 'from': c, 'to': d} for a, b, c, d in applied],
                  'skipped': [{'id': a, 'field': b, 'why': c} for a, b, c in failed],
                  'source': 'qa_editorial_apply.py / honeywood-editorial-qa workflow'})
    json.dump(prior, open(audit, 'w'), ensure_ascii=False, indent=2)
    print(f"\nwrote letters.json, cleaned.json, and audit {audit.name}")
