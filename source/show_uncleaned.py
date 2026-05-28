#!/usr/bin/env python3
"""Dump raw body+commentary for records not yet in cleaned.json (reading order)."""
import json, sys
from pathlib import Path
DATA = Path(__file__).parent.parent / 'data'
recs = json.load(open(DATA / 'letters.json'))
cleaned = json.load(open(DATA / 'cleaned.json'))
un = sorted([r for r in recs if r['id'] not in cleaned], key=lambda r: r['seq'])
count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
print(f"UNCLEANED remaining: {len(un)}\n")
for r in un[:count]:
    k = f" ({r['kind']})" if r['kind'] != 'letter' else ""
    print(f"\n===== {r['id']} | {r['book_date']} | {r['from']} -> {r['to']}{k} | p{r['page']} =====")
    print("[BODY]", r['body'])
    if r['commentary']:
        print("[COMMENTARY]", r['commentary'])
