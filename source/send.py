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
  python3 send.py --catchup                # send every due day not yet sent (the daily cron)
  python3 send.py --check                  # verify the gist is reachable; do not send
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

def mask_email(addr):
    """Mask a recipient address for logs. CI logs on a public repo are public, and
    recipient addresses (loaded from the gist at runtime) are not secrets, so they
    would not be masked automatically — keep them out of failure output."""
    local, _, domain = addr.partition('@')
    return f"{(local[:1] or '')}***@{domain}" if domain else "***"

START_SEND = '2026-06-14'  # nothing is EVER emailed before this; earlier dates are archive-only

def _send_day(s, letters, subject, user, recipients, unsub_base):
    """Send one day's letters to every recipient over an open SMTP session."""
    sent, failed = 0, []
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
            s.sendmail(user, [email_addr], msg.as_string()); sent += 1
        except Exception as e:
            failed.append((email_addr, str(e)))
    return sent, failed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true', help='send even if already in sent_log')
    ap.add_argument('--catchup', action='store_true',
                    help='send every due day not yet in sent_log (resilience against missed runs)')
    ap.add_argument('--check', action='store_true',
                    help='load recipients from the gist and report; do not send')
    args = ap.parse_args()

    load_env()
    user = os.environ.get('GMAIL_USER')
    pw = (os.environ.get('GMAIL_APP_PASSWORD') or '').replace(' ', '')
    unsub_base = os.environ.get('HONEYWOOD_UNSUB_BASE', '').strip().rstrip('/')

    # Connectivity probe: confirm the gist path works (used by a manual CI run).
    if args.check:
        try:
            rcpts = load_active()
        except Exception as e:
            print(f"ERROR: gist check failed: {e}", file=sys.stderr); return 1
        print(f"gist OK: {len(rcpts)} active recipient(s); unsub_base={'set' if unsub_base else 'MISSING'}")
        return 0

    recs = load_merged()
    days = group_by_send_date(recs, future_only=False)
    today = date.today().isoformat()

    # Which day(s) to send: a single --date, or every due day not yet sent (--catchup).
    if args.catchup:
        sent_log = load_sent()
        targets = [d for d in sorted(days) if START_SEND <= d <= today and (args.force or d not in sent_log)]
        if not targets:
            print("Catch-up: nothing due."); return 0
        print(f"Catch-up: {len(targets)} due day(s): {', '.join(targets)}")
    else:
        targets = [args.date]

    # Dry-run: render previews only (no SMTP, no gist).
    if args.dry_run:
        for d in targets:
            letters = days.get(d)
            if not letters:
                print(f"No letters for {d}."); continue
            sample = f"{unsub_base}/u?t=SAMPLE_TOKEN" if unsub_base else None
            out = Path(f'/tmp/mail_{d}.html'); out.write_text(email_day(letters, unsub_url=sample), encoding='utf-8')
            print(f"[dry-run] {d}: wrote {out}")
        return 0

    if not user or not pw:
        print("ERROR: set GMAIL_USER and GMAIL_APP_PASSWORD (env or repo-root .env).", file=sys.stderr)
        return 1

    # Recipients: the private gist (fail-closed — see recipients.py). Loaded once for the run.
    try:
        recipients = load_active()
    except Exception as e:
        print(f"ERROR: could not load recipients from gist: {e}", file=sys.stderr); return 1
    if not recipients:
        print("No active recipients. Nothing to send."); return 0

    rc = 0
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx) as s:
        s.login(user, pw)
        for d in targets:
            letters = days.get(d)
            if not letters:
                print(f"No letters for {d}. Nothing to send."); continue
            if not args.force and d in load_sent():
                print(f"{d} already sent (in sent_log). Skipping."); continue
            if d < START_SEND and not args.force:
                print(f"{d} precedes the project start ({START_SEND}); archive-only, not emailing."); continue
            raw = [l['id'] for l in letters if not l.get('cleaned')]
            if raw:
                print(f"ERROR: {d} has uncleaned letters {raw}; refusing to send.", file=sys.stderr); rc = 2; continue
            subject = subject_line(letters)
            sent, failed = _send_day(s, letters, subject, user, recipients, unsub_base)
            record_sent(d)
            print(f"{d}: {len(letters)} letter(s) -> sent to {sent} recipient(s); {len(failed)} failed.")
            for addr, err in failed:
                print(f"  FAILED {mask_email(addr)}: {err}", file=sys.stderr)
            if failed: rc = rc or 3
    return rc

if __name__ == '__main__':
    sys.exit(main())
