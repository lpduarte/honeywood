#!/usr/bin/env python3
"""Single source of truth for the recipient list: a private GitHub gist.

The gist holds one file, recipients.json:
  {"recipients": [
     {"email": "a@b.com", "token": "<random>", "subscribed_on": "YYYY-MM-DD", "status": "active"}
  ]}

The daily workflow reads it (read-only) to know who to email. manage_recipients.py
and the Cloudflare unsubscribe worker write to it. Plaintext addresses live ONLY
here (private) and in each per-recipient message — never in this public repo.

Config (env, or a KEY=VALUE file at repo-root .env):
  RECIPIENTS_GIST_ID     the private gist id
  RECIPIENTS_GIST_TOKEN  a classic PAT with the `gist` scope (read + write)
"""
from __future__ import annotations
import json, os, urllib.request

GIST_FILE = 'honeywood_recipients.json'
API = 'https://api.github.com/gists/'

def gist_configured() -> bool:
    return bool(os.environ.get('RECIPIENTS_GIST_ID') and os.environ.get('RECIPIENTS_GIST_TOKEN'))

def _api(method, data=None):
    gid = os.environ['RECIPIENTS_GIST_ID']
    token = os.environ['RECIPIENTS_GIST_TOKEN']
    req = urllib.request.Request(
        API + gid, method=method,
        data=json.dumps(data).encode() if data is not None else None)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'honeywood')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def fetch() -> list:
    """Return the full recipients list (all statuses) from the gist. Raises on failure."""
    g = _api('GET')
    content = g['files'][GIST_FILE]['content']
    return json.loads(content).get('recipients', [])

def save(recipients: list) -> None:
    """Write the recipients list back to the gist."""
    body = {'files': {GIST_FILE: {'content': json.dumps({'recipients': recipients}, indent=2)}}}
    _api('PATCH', body)

def load_active():
    """List of (email, token) for active recipients, read from the gist.

    Fail-closed: raises if the gist isn't configured or can't be read/parsed —
    we never send to a guessed, stale or empty list."""
    if not gist_configured():
        raise RuntimeError("recipient gist not configured "
                           "(set RECIPIENTS_GIST_ID and RECIPIENTS_GIST_TOKEN)")
    active = [r for r in fetch() if r.get('status', 'active') == 'active']
    return [(r['email'], r.get('token')) for r in active if r.get('email')]
