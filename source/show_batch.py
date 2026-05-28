#!/usr/bin/env python3
"""Dump raw body+commentary for the next UNCLEANED future letters (send-date order).
Skips letters already present in data/cleaned.json so the cleanup can resume cleanly."""
import json, sys
from datetime import date
from pathlib import Path

DATA = Path(__file__).parent.parent / 'data'
recs = json.load(open(DATA / 'letters.json'))
cleaned = json.load(open(DATA / 'cleaned.json'))
TODAY = date(2026, 5, 28)

future = [r for r in recs if r['send_date'] and date.fromisoformat(r['send_date']) >= TODAY]
future.sort(key=lambda r: (r['send_date'], r['seq']))
uncleaned = [r for r in future if r['id'] not in cleaned]

count = int(sys.argv[1]) if len(sys.argv) > 1 else 12
print(f"PROGRESS: {len(future)-len(uncleaned)}/{len(future)} future letters cleaned; {len(uncleaned)} remaining\n")
for r in uncleaned[:count]:
    k = f" ({r['kind']})" if r['kind'] != 'letter' else ""
    print(f"\n===== {r['id']} | {r['book_date']} | {r['from']} -> {r['to']}{k} | p{r['page']} =====")
    print("[BODY]")
    print(r['body'])
    if r['commentary']:
        print("[COMMENTARY]")
        print(r['commentary'])
