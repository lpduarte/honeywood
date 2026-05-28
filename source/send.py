#!/usr/bin/env python3
"""Send a day's Honeywood email via Gmail SMTP.

Config (env vars, or a KEY=VALUE file at repo-root .env):
  GMAIL_USER          sender Gmail address
  GMAIL_APP_PASSWORD  Gmail app password (16 chars; needs 2-Step Verification)
  RECIPIENT           where to deliver (defaults to GMAIL_USER)

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
    recipient = os.environ.get('RECIPIENT', user)

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

    # Safety: never send a letter whose text hasn't been cleaned (would be raw OCR).
    raw = [l['id'] for l in letters if not l.get('cleaned')]
    if raw:
        first_send = min((r['send_date'] for r in recs if r.get('cleaned') and r['send_date']), default=None)
        if first_send and args.date < first_send:
            # Pre-start letters (book dates before the project began) are intentionally
            # never sent, so a manual run for such a date is a graceful no-op, not a failure.
            print(f"{args.date} is before the first send date ({first_send}); "
                  f"these pre-start letters are intentionally not sent. Skipping.")
            return 0
        print(f"ERROR: {args.date} has uncleaned letters {raw}; refusing to send.", file=sys.stderr)
        return 2

    html = email_day(letters)
    subject = subject_line(letters)
    print(f"{args.date}: {len(letters)} letter(s) | subject: {subject}")

    if args.dry_run:
        out = Path(f'/tmp/mail_{args.date}.html'); out.write_text(html, encoding='utf-8')
        print(f"[dry-run] wrote {out}; not sending.")
        return 0

    if not user or not pw:
        print("ERROR: set GMAIL_USER and GMAIL_APP_PASSWORD (env or repo-root .env).", file=sys.stderr)
        return 1

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = formataddr(("The Honeywood File", user))
    msg['To'] = recipient
    msg.attach(MIMEText("This message is best viewed as HTML.", 'plain'))
    msg.attach(MIMEText(html, 'html'))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx) as s:
        s.login(user, pw)
        s.sendmail(user, [recipient], msg.as_string())
    record_sent(args.date)
    print(f"Sent to {recipient}.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
