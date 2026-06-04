#!/usr/bin/env python3
"""Lightweight data guard — run in CI on every push so a future edit can't
silently break the corpus. No deps; exits non-zero on any failure.

  python3 source/test_data.py
"""
from __future__ import annotations
import sys, json
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from build import load_merged, group_by_send_date
from render_email import email_day, subject_line
import money

START = '2026-06-14'
errors = []
def check(cond, msg):
    if not cond: errors.append(msg)

recs = load_merged()
check(len(recs) > 300, f"suspiciously few records: {len(recs)}")

# Every record has the fields the email needs.
for r in recs:
    rid = r.get('id', '?')
    check((r.get('from') or '').strip(), f"{rid}: empty 'from'")
    check((r.get('to') or '').strip(), f"{rid}: empty 'to'")
    check((r.get('body') or '').strip(), f"{rid}: empty 'body'")

# Every send-day renders without raising, and nothing uncleaned is ever emailed.
days = group_by_send_date(recs, future_only=False)
for d, letters in days.items():
    try:
        email_day(letters, unsub_url='https://x.example/u?t=T'); subject_line(letters)
        for l in letters:
            if l.get('book_date'):
                money.rows(l['body'], int(l['book_date'][:4]))
    except Exception as e:
        errors.append(f"{d}: render/money failed: {e!r}")
    if d >= START:
        raw = [l['id'] for l in letters if not l.get('cleaned')]
        check(not raw, f"{d}: uncleaned letters would be emailed: {raw}")

# Title convention guard: the book never titles Grigblay 'Mr. Grigblay' in headers.
for r in recs:
    for f in ('from', 'to'):
        check((r.get(f) or '') != 'Mr. Grigblay', f"{r['id']}.{f}: forbidden honorific 'Mr. Grigblay'")

# Locked-in editorial fixes (regression guards).
cleaned = json.load(open(HERE.parent / 'data' / 'cleaned.json'))
def body(i): return cleaned.get(i, {}).get('body', '')
check('Marlford' in body('L029-0') and 'Marlord' not in body('L029-0'), "L029-0: Marlford regression")
check('infinitum (sic)' in body('L162-1') and 'ad infinitum' not in body('L162-1'), "L162-1: (sic) malapropism regression")
check('½ in. joints' in body('L077-2'), "L077-2: '½ in.' regression")
check('½ in.' in body('L079-0'), "L079-0: '½ in.' regression")

# 'In today's money' must also scan the editor's commentary (L026-2 cites £25 in its note).
def comm(i): return cleaned.get(i, {}).get('commentary', '')
check(any(lbl == '£25' for lbl, _ in money.rows(body('L026-2') + '\n' + comm('L026-2'), 1924)),
      "L026-2: editor-note £25 missing from money rows (commentary not scanned)")

if errors:
    print(f"FAIL ({len(errors)}):")
    for e in errors: print('  -', e)
    sys.exit(1)
print(f"OK: {len(recs)} records, {len(days)} send-days validated.")
