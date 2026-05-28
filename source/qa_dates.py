#!/usr/bin/env python3
"""QA v2: local-outlier detection. The book groups by topic so small overlaps are normal,
but a single letter whose date is far from BOTH its dated neighbours signals an OCR misread.
Flags outliers > THRESHOLD days from the local median (both directions)."""
import json
from datetime import date

THRESHOLD = 20  # days

letters = json.load(open('letters_index.json'))
ordered = sorted(letters, key=lambda l: (l['page'], l['idx']))
dated = [l for l in ordered if l['date']]

def parse(d):
    y, m, dd = map(int, d.split('-'))
    return date(y, m, dd)

flags = []
for i, l in enumerate(dated):
    d = parse(l['date'])
    # neighbours: up to 3 before and after
    neigh = dated[max(0,i-3):i] + dated[i+1:i+4]
    nd = sorted(parse(n['date']) for n in neigh)
    if not nd:
        continue
    median = nd[len(nd)//2]
    delta = abs((d - median).days)
    if delta > THRESHOLD:
        flags.append({**l, 'local_median': median.isoformat(), 'delta_days': delta})

print(f"Dated letters: {len(dated)}")
print(f"Large local outliers (>{THRESHOLD}d from local median): {len(flags)}\n")
for f in sorted(flags, key=lambda x: -x['delta_days']):
    print(f"p{f['page']:3d} | {f['date']} (raw {f['date_raw']!r}) {f['sender']}->{f['recipient']}")
    print(f"        {f['delta_days']}d from local median {f['local_median']}")
    print(f"        {f['body_preview'][:90]}")
json.dump(flags, open('date_outliers.json','w'), indent=2, ensure_ascii=False)
