#!/usr/bin/env python3
"""Merge letters.json + cleaned.json, group future letters by send date, render day emails."""
from __future__ import annotations
import json
from collections import OrderedDict
from datetime import date
from pathlib import Path

SRC = Path(__file__).parent
DATA = SRC.parent / 'data'

def load_merged():
    recs = json.load(open(DATA / 'letters.json'))
    cleaned = json.load(open(DATA / 'cleaned.json'))
    for r in recs:
        c = cleaned.get(r['id'])
        if c:
            r['body'] = c.get('body', r['body'])
            r['commentary'] = c.get('commentary', r.get('commentary'))
            if c.get('subject'): r['subject'] = c['subject']
            if c.get('attachments'): r['attachments'] = c['attachments']
            r['cleaned'] = True
        else:
            r['cleaned'] = False
    return recs

def group_by_send_date(recs, future_only=True, today=None):
    if today is None: today = date.today()
    days = OrderedDict()
    for r in sorted(recs, key=lambda r:(r['send_date'] or '9999', r['seq'])):
        if not r['send_date']: continue
        if future_only and date.fromisoformat(r['send_date']) < today: continue
        days.setdefault(r['send_date'], []).append(r)
    return days

if __name__ == '__main__':
    import sys
    from render import render_day
    recs = load_merged()
    days = group_by_send_date(recs)
    target = sys.argv[1] if len(sys.argv) > 1 else next(iter(days))
    out = render_day(days[target])
    Path(f'/tmp/email_{target}.html').write_text(out, encoding='utf-8')
    print(f"/tmp/email_{target}.html  ({len(days[target])} letters)")
