#!/usr/bin/env python3
"""Manage the recipient gist from the command line.

  python manage_recipients.py list                       # show everyone + status
  python manage_recipients.py add a@b.com [c@d.com ...]   # add / reactivate (mints a token)
  python manage_recipients.py unsub a@b.com               # mark unsubscribed (keeps the record)
  python manage_recipients.py mint                        # fill any missing tokens

Needs RECIPIENTS_GIST_ID + RECIPIENTS_GIST_TOKEN (env or repo-root .env).
The gist is the single source of truth; this just edits it safely (read-modify-write)."""
from __future__ import annotations
import sys, os, re, secrets
from pathlib import Path

# Basic shape check, so a stray CLI flag or typo (e.g. "--help") can never be saved
# as a recipient. Deliberately permissive — one @, no spaces, a dotted domain.
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

import recipients as R

ROOT = Path(__file__).parent.parent

def load_env():
    envf = ROOT / '.env'
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))

def new_token():
    return secrets.token_urlsafe(24)

def cmd_list(recs):
    if not recs:
        print("(empty)"); return
    for r in recs:
        tok = 'token' if r.get('token') else 'NO-TOKEN'
        print(f"  {r.get('status','active'):12} {tok:9} {r['email']}")
    active = sum(1 for r in recs if r.get('status', 'active') == 'active')
    print(f"\n  {len(recs)} total · {active} active")

def cmd_add(recs, emails):
    by_email = {r['email'].lower(): r for r in recs}
    for e in emails:
        key = e.strip().lower()
        if not key: continue
        if not EMAIL_RE.match(key):
            print(f"  skipped (not an email): {e}", file=sys.stderr); continue
        r = by_email.get(key)
        if r:
            r['status'] = 'active'
            if not r.get('token'): r['token'] = new_token()
            print(f"  reactivated {e}")
        else:
            rec = {'email': e.strip(), 'token': new_token(), 'status': 'active'}
            recs.append(rec); by_email[key] = rec
            print(f"  added {e}")
    return recs

def cmd_unsub(recs, emails):
    targets = {e.strip().lower() for e in emails}
    for r in recs:
        if r['email'].lower() in targets:
            r['status'] = 'unsubscribed'
            print(f"  unsubscribed {r['email']}")
    return recs

def cmd_mint(recs):
    n = 0
    for r in recs:
        if not r.get('token'):
            r['token'] = new_token(); n += 1
    print(f"  minted {n} token(s)")
    return recs

def main(argv):
    load_env()
    if not R.gist_configured():
        print("ERROR: set RECIPIENTS_GIST_ID and RECIPIENTS_GIST_TOKEN (env or .env).", file=sys.stderr)
        return 1
    if not argv:
        print(__doc__); return 1
    cmd, rest = argv[0], argv[1:]
    recs = R.fetch()

    if cmd == 'list':
        cmd_list(recs); return 0
    elif cmd == 'add':
        if not rest: print("usage: add a@b.com [...]", file=sys.stderr); return 1
        recs = cmd_add(recs, rest)
    elif cmd == 'unsub':
        if not rest: print("usage: unsub a@b.com [...]", file=sys.stderr); return 1
        recs = cmd_unsub(recs, rest)
    elif cmd == 'mint':
        recs = cmd_mint(recs)
    else:
        print(f"unknown command: {cmd}\n{__doc__}", file=sys.stderr); return 1

    R.save(recs)
    print("  saved to gist.")
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
