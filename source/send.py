#!/usr/bin/env python3
"""Send a day's Honeywood email via Gmail SMTP.

Config (env vars, or a KEY=VALUE file at repo-root .env):
  GMAIL_USER             sender Gmail address
  GMAIL_APP_PASSWORD     Gmail app password (16 chars; needs 2-Step Verification)
  RECIPIENTS_GIST_ID     private gist holding the recipient list (see recipients.py)
  RECIPIENTS_GIST_TOKEN  classic PAT with the `gist` scope
  HONEYWOOD_UNSUB_BASE   base URL of the unsubscribe Worker (for the one-click link)

Usage:
  python3 send.py --date 2026-06-14        # send that day's letters
  python3 send.py                          # send today's letters (if any)
  python3 send.py --date 2026-06-14 --dry-run
"""
from __future__ import annotations
import os, sys, ssl, smtplib, argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from datetime import date
from pathlib import Path

from build import load_merged, group_by_send_date
from render_email import email_day, subject_line
from recipients import load_active

ROOT = Path(__file__).parent.parent

def load_env():
    envf = ROOT / '.env'
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))

SENT_LOG = ROOT / 'data' / 'sent_log.json'

def load_sent():
    import json as _j
    return set(_j.loads(SENT_LOG.read_text())) if SENT_LOG.exists() else set()

def record_sent(d):
    import json as _j
    log = load_sent(); log.add(d)
    SENT_LOG.write_text(_j.dumps(sorted(log), indent=2))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true', help='send even if already in sent_log')
    args = ap.parse_args()

    load_env()
    user = os.environ.get('GMAIL_USER')
    pw = (os.environ.get('GMAIL_APP_PASSWORD') or '').replace(' ', '')
    unsub_base = os.environ.get('HONEYWOOD_UNSUB_BASE', '').strip().rstrip('/')

    recs = load_merged()
    days = group_by_send_date(recs, future_only=False)
    letters = days.get(args.date)
    if not letters:
        print(f"No letters for {args.date}. Nothing to send.")
        return 0

    # Idempotency: never send the same day twice (re-runs, retries, manual tests).
    if not args.dry_run and not args.force and args.date in load_sent():
        print(f"{args.date} already sent (in sent_log). Skipping.")
        return 0

    # Hard start gate: nothing is EVER emailed before the project's first send date.
    # Dates before it are backstory, shown only on the archive site. --force / --dry-run bypass.
    START_SEND = '2026-06-14'
    if args.date < START_SEND and not args.force and not args.dry_run:
        print(f"{args.date} precedes the project start ({START_SEND}); archive-only, not emailing.")
        return 0

    # Safety: never email raw (uncleaned) OCR text.
    raw = [l['id'] for l in letters if not l.get('cleaned')]
    if raw:
        print(f"ERROR: {args.date} has uncleaned letters {raw}; refusing to send.", file=sys.stderr)
        return 2

    subject = subject_line(letters)
    print(f"{args.date}: {len(letters)} letter(s) | subject: {subject}")

    if args.dry_run:
        # Preview with a sample unsubscribe link so the footer renders as recipients see it.
        sample_url = f"{unsub_base}/u?t=SAMPLE_TOKEN" if unsub_base else None
        html = email_day(letters, unsub_url=sample_url)
        out = Path(f'/tmp/mail_{args.date}.html'); out.write_text(html, encoding='utf-8')
        print(f"[dry-run] wrote {out}; not sending.")
        return 0

    if not user or not pw:
        print("ERROR: set GMAIL_USER and GMAIL_APP_PASSWORD (env or repo-root .env).", file=sys.stderr)
        return 1

    # Single source of truth for who receives: the private gist (fail-closed — see recipients.py).
    try:
        recipients = load_active()
    except Exception as e:
        print(f"ERROR: could not load recipients from gist: {e}", file=sys.stderr)
        return 1
    if not recipients:
        print("No active recipients. Nothing to send.")
        return 0

    # Per-recipient send: each message carries that person's one-click unsubscribe link
    # and headers, so the body is unique per recipient (no shared BCC envelope).
    ctx = ssl.create_default_context()
    sent = 0; failed = []
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx) as s:
        s.login(user, pw)
        for email_addr, token in recipients:
            unsub_url = f"{unsub_base}/u?t={token}" if (unsub_base and token) else None
            html = email_day(letters, unsub_url=unsub_url)
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr(("The Honeywood File", user))
            msg['To'] = email_addr
            if unsub_url:
                msg['List-Unsubscribe'] = f'<{unsub_url}>'
                msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
            msg.attach(MIMEText("This message is best viewed as HTML.", 'plain'))
            msg.attach(MIMEText(html, 'html'))
            try:
                s.sendmail(user, [email_addr], msg.as_string())
                sent += 1
            except Exception as e:
                failed.append((email_addr, str(e)))
    record_sent(args.date)
    print(f"Sent to {sent} recipient(s); {len(failed)} failed.")
    for addr, err in failed:
        print(f"  FAILED {addr}: {err}", file=sys.stderr)
    return 0

if __name__ == '__main__':
    sys.exit(main())
