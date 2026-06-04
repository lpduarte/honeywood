#!/usr/bin/env python3
"""Per record, find the book's own section header (the 'X TO Y' line) and report
the distinct raw headers + which records map to each. Read-only — produces the
basis for normalising from/to to the book's titles. Output: /tmp/hwqa/titles_raw.json
"""
from __future__ import annotations
import json, re
from pathlib import Path

SRC = Path(__file__).parent
import sys; sys.path.insert(0, str(SRC))
from build import load_merged

full = (SRC / 'honeywood_full.txt').read_text(encoding='utf-8', errors='replace')
lines = full.splitlines()
def norm(s): return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s.lower())).strip()
norm_lines = [norm(ln) for ln in lines]
doc_parts, line_starts, p = [], [], 0
for nl in norm_lines:
    line_starts.append(p); doc_parts.append(nl); p += len(nl) + 1
doc = ' '.join(doc_parts)

def line_of(pos):
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= pos: lo = mid
        else: hi = mid - 1
    return lo

def body_line(body):
    words = norm(body).split()
    if len(words) < 6: return None
    for start in (6, 0, 12, 3):
        sh = ' '.join(words[start:start + 8])
        if len(sh) < 20: continue
        i = doc.find(sh)
        if i != -1: return line_of(i)
    return None

def is_header(ln):
    s = ln.strip()
    if ' TO ' not in s.upper() or 'HONEYWOOD FILE' in s.upper(): return False
    letters = [c for c in s if c.isalpha()]
    if not letters: return False
    upper_ratio = sum(c.isupper() for c in letters) / len(letters)
    return upper_ratio >= 0.7 and len(s) < 90

def nearest_header(lo):
    for i in range(lo, max(0, lo - 16) - 1, -1):     # scan upward from the body match
        if is_header(lines[i]): return lines[i].strip()
    return None

recs = load_merged()
from collections import defaultdict, Counter
raw_by_rec, header_recs, notfound = {}, defaultdict(list), []
for r in recs:
    lo = body_line(r.get('body', ''))
    h = nearest_header(lo) if lo is not None else None
    if h:
        raw_by_rec[r['id']] = h
        header_recs[h].append(r['id'])
    else:
        notfound.append(r['id'])

out = {'raw_by_rec': raw_by_rec,
       'distinct': sorted(header_recs.items(), key=lambda kv: -len(kv[1])),
       'notfound': notfound}
json.dump(out, open('/tmp/hwqa/titles_raw.json', 'w'), ensure_ascii=False, indent=2)
print(f'records: {len(recs)} | header found: {len(raw_by_rec)} | not found: {len(notfound)}')
print(f'distinct raw headers: {len(header_recs)}\n')
print('--- top distinct headers (count) ---')
for h, ids in sorted(header_recs.items(), key=lambda kv: -len(kv[1]))[:45]:
    print(f'  {len(ids):3}  {h}')
if notfound:
    print('\nnot found (sample):', ', '.join(notfound[:15]))
