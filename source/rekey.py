#!/usr/bin/env python3
"""Safety net: re-align data/cleaned.json keys to the current record ids after any parser
change, by matching each cleaned body to the record whose RAW body it best resembles.
Run after extract.py if record boundaries/ids may have shifted."""
import json, re
from difflib import SequenceMatcher
from pathlib import Path

DATA = Path(__file__).parent.parent / 'data'
cleaned = json.load(open(DATA / 'cleaned.json'))
recs = json.load(open(DATA / 'letters.json'))
by_id = {r['id']: r for r in recs}

def sig(s):
    s = re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower())
    return re.sub(r'\s+', ' ', s).strip()[:160]

extra_ids = {r['id'] for r in recs if r.get('extra')}
candidates = [r for r in recs if not r.get('extra')]
new_cleaned, used, low = {}, set(), []
for old_id, payload in cleaned.items():
    if old_id in extra_ids:        # hand-declared extra letter: keep its key as-is
        new_cleaned[old_id] = payload
        continue
    csig = sig(payload['body'])
    best_id, best = None, 0.0
    for r in candidates:
        if r['id'] in used: continue
        ratio = SequenceMatcher(None, csig, sig(r['body'])).ratio()
        if ratio > best: best, best_id = ratio, r['id']
    used.add(best_id)
    new_cleaned[best_id] = payload
    if best < 0.7:
        low.append((old_id, best_id, round(best, 2)))

assert len(new_cleaned) == len(cleaned), "duplicate mapping!"
json.dump(new_cleaned, open(DATA / 'cleaned.json', 'w'), indent=2, ensure_ascii=False)
print(f"re-keyed {len(new_cleaned)} entries.")
if low:
    print("LOW-CONFIDENCE (verify):")
    for o, n, r in low: print(f"  {o} -> {n} ({r})")
