#!/usr/bin/env python3
"""Stage inputs for the editorial QA workflow.

For every record it writes a small self-contained bundle that pairs OUR text
(metadata + body + commentary) with the matching SOURCE excerpt from the raw
OCR (honeywood_full.txt), aligned by content — so a reviewer agent reads one
~10 KB file instead of the whole corpus.

Outputs (under /tmp/hwqa):
  recs/<id>.md     one bundle per record
  ids.json         every record id (fed to the workflow as args)
  gaz_freq.txt     capitalised-token frequencies, to seed the gazetteer
  unmatched.json   ids whose body couldn't be located in the source (page-only)
"""
from __future__ import annotations
import json, re, sys
from collections import Counter
from pathlib import Path

SRC = Path(__file__).parent
sys.path.insert(0, str(SRC))
from build import load_merged

OUT = Path('/tmp/hwqa'); RECS = OUT / 'recs'
RECS.mkdir(parents=True, exist_ok=True)

full = (SRC / 'honeywood_full.txt').read_text(encoding='utf-8', errors='replace')
lines = full.splitlines()

# Normalised line text + cumulative offsets, so we can find a shingle in the
# whole document and map the hit back to a line range.
def norm(s): return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s.lower())).strip()
norm_lines = [norm(ln) for ln in lines]
doc, offsets, pos = [], [], 0
for nl in norm_lines:
    offsets.append(pos); doc.append(nl); pos += len(nl) + 1
doc = ' '.join(doc)
line_starts = []
p = 0
for nl in norm_lines:
    line_starts.append(p); p += len(nl) + 1

def line_of(char_pos):
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= char_pos: lo = mid
        else: hi = mid - 1
    return lo

def find_excerpt(body):
    """Locate the body in the source by a distinctive shingle; return (lo,hi) line range or None."""
    words = norm(body).split()
    if len(words) < 6:
        return None
    # try a few shingles (middle first — avoids common salutations)
    for start in (6, 0, 12, 3):
        shingle = ' '.join(words[start:start + 8])
        if len(shingle) < 20:
            continue
        idx = doc.find(shingle)
        if idx != -1:
            lo = line_of(idx)
            # extend to cover the whole letter generously
            return max(0, lo - 2), min(len(lines), lo + max(40, len(words) // 8 + 10))
    return None

def page_file(rec_id):
    m = re.match(r'L(\d+)', rec_id)
    if not m: return None
    f = SRC / 'ocr_text' / f'page_{int(m.group(1)):04d}.txt'
    return f if f.exists() else None

recs = load_merged()
ids, unmatched = [], []
for r in recs:
    rid = r['id']; ids.append(rid)
    excerpt_range = find_excerpt(r.get('body', ''))
    if excerpt_range:
        lo, hi = excerpt_range
        source = '\n'.join(lines[lo:hi])
        src_note = f'(matched in honeywood_full.txt, lines {lo + 1}-{hi})'
    else:
        unmatched.append(rid)
        pf = page_file(rid)
        source = pf.read_text(encoding='utf-8', errors='replace') if pf else '(no source excerpt found)'
        src_note = f'(NO content match — showing mapped page {pf.name if pf else "?"}; align carefully)'

    md = f"""# Record {rid}

book_date: {r.get('book_date')}   send_date: {r.get('send_date')}   seq: {r.get('seq')}

## OUR METADATA (labels our pipeline assigned — fixable freely)
- from: {r.get('from')!r}
- from_role: {r.get('from_role')!r}
- to: {r.get('to')!r}
- to_role: {r.get('to_role')!r}
- subject: {r.get('subject')!r}
- chapter: {r.get('chapter')!r}  (chapter_start: {r.get('chapter_start')})

## OUR BODY (cleaned)
{r.get('body', '').strip()}

## OUR COMMENTARY / Editor's note (cleaned)
{(r.get('commentary') or '(none)').strip()}

## SOURCE — raw OCR of the original 1929 book {src_note}
{source.strip()}
"""
    (RECS / f'{rid}.md').write_text(md, encoding='utf-8')

# Gazetteer seed: frequent capitalised tokens across the source.
caps = re.findall(r"\b[A-Z][A-Za-z&.'-]{2,}\b", full)
freq = Counter(caps)
(OUT / 'gaz_freq.txt').write_text(
    '\n'.join(f'{n:5d}  {w}' for w, n in freq.most_common(250)), encoding='utf-8')
(OUT / 'ids.json').write_text(json.dumps(ids), encoding='utf-8')
(OUT / 'unmatched.json').write_text(json.dumps(unmatched, indent=2), encoding='utf-8')

print(f'staged {len(ids)} bundles in {RECS}')
print(f'content-matched: {len(ids) - len(unmatched)} | page-only (unmatched): {len(unmatched)}')
if unmatched:
    print('unmatched ids:', ', '.join(unmatched[:20]), ('…' if len(unmatched) > 20 else ''))
