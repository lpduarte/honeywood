#!/usr/bin/env python3
"""Email-safe renderer: inline styles + table layout as the baseline, so the email
renders everywhere (e.g. the Gmail app reading non-Google accounts drops <style>).
A head <style> media query is layered on top as progressive enhancement — Gmail has
supported it since 2016 — relaxing the card padding and left-aligning the justified
text on narrow screens, where a ~32-char justified column reads badly. Georgia is the
realistic font; EB Garamond is listed first for clients that happen to have it."""
from __future__ import annotations
import html, re, os
import money

FONT = "'EB Garamond', Georgia, 'Times New Roman', serif"
PAPER = '#e8e2d4'  # outer "desk" colour; always the fallback under the pattern image
# iOS WebKit "font boosting" inflates long small-type blocks PER BLOCK (the editor's
# note ended up larger than the letter itself on iPhones). This opt-out says our sizes
# are deliberate. Inherited, but Gmail rewrites <body>, so it goes on every container
# that might survive, plus a <style> rule as a second net.
TSA = '-webkit-text-size-adjust:100%;text-size-adjust:100%;'
SITE_URL = 'https://lpduarte.github.io/honeywood/'  # the archive calendar (GitHub Pages)

def _bg():
    """Outer background: solid PAPER, plus a tiling pattern image when configured.
    The image needs a public HTTPS URL to render in Gmail; PAPER shows if it's
    blocked or unset, so the email is never broken."""
    url = os.environ.get('HONEYWOOD_PATTERN_URL', '').strip()
    if not url:
        return f'background-color:{PAPER};'
    return (f"background-color:{PAPER};background-image:url('{html.escape(url, quote=True)}');"
            f"background-repeat:repeat;background-size:192px 192px;")
MONTHS_EN = ['', 'January','February','March','April','May','June',
             'July','August','September','October','November','December']

def _ordinal(d):
    suffix = 'th' if 10 <= d % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')
    return f"{d}{suffix}"

def fmt_date_en(iso):
    y, m, d = map(int, iso.split('-'))
    return f"{_ordinal(d)} {MONTHS_EN[m]}, {y}"

def esc(s): return html.escape(s)

# A tender schedule is encoded in the body as a run of lines "Builder — £amount · time"
# (the only such table in the corpus, L032-0). Render it as an aligned 3-column table,
# email-safe (a real <table>, inline styles, no <style> dependency). No invented headers.
_TROW = re.compile(r'^(.+?) — (.+?) · (.+)$')
def _email_table(p):
    lines = [l for l in p.split('\n') if l.strip()]
    if len(lines) < 2:
        return None
    rows = [_TROW.match(l) for l in lines]
    if not all(rows):
        return None
    cells = ''
    for i, m in enumerate(rows):
        bb = '' if i == len(rows) - 1 else 'border-bottom:1px solid #ddd2b8;'
        base = f'font-family:{FONT};font-size:17px;padding:7px 0;{bb}'
        cells += (
          f'<tr><td style="{base}color:#2b2620;">{esc(m.group(1))}</td>'
          f'<td align="right" style="{base}color:#2b2620;padding-left:18px;white-space:nowrap;">{esc(m.group(2))}</td>'
          f'<td align="right" style="{base}color:#8a7c5e;padding-left:18px;white-space:nowrap;">{esc(m.group(3))}</td></tr>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:4px 0 13px;{TSA}">{cells}</table>')

def split_salutation_closing(body):
    b = body.strip(); sal = ''
    m = re.match(r'^(Dear[^,\n]*,|Sirs,|Sir,|Madam,)\s*', b)
    if m: sal = m.group(1); b = b[m.end():]
    b = re.sub(r'^\s*\d{1,2}\s*[.\-/,•]\s*\d{1,2}\s*[.\-/,•]\s*\d{2,4}\.?\s*', '', b)
    closing = ''
    cm = re.search(r'(Yours faithfully,|Yours sincerely,|Yours truly,|Yours obediently,|Yours to oblige,|Yours respectfully,|I remain, Sir,?|I am, Sir,?|Believe me,)\s*$', b)
    if cm: closing = cm.group(1); b = b[:cm.start()].strip()
    return sal, b.strip(), closing

def sheet(rec, tail=''):
    sal, para, closing = split_salutation_closing(rec['body'])
    def ph(p): return esc(p.strip()).replace('\n', '<br>')
    paras = [p for p in re.split(r'\n{2,}', para) if p.strip()]
    body_html = ''.join(
        _email_table(p) or
        (f'<p class="para" style="font-family:{FONT};font-size:17.5px;line-height:1.62;'
         f'margin:0 0 13px;color:#2b2620;text-align:justify;">{ph(p)}</p>') for p in paras)

    from_role = rec.get('from_role'); to_role = rec.get('to_role')
    role_html = (f'<div style="font-family:{FONT};font-size:14.5px;font-style:italic;'
                 f'color:#9a8c6f;padding-top:2px;">{esc(from_role)}</div>') if from_role else ''
    to_line = esc(rec['to']) + (f", {esc(to_role)}" if to_role else '')

    subject_html = ''
    if rec.get('subject'):
        subject_html = (f'<div style="font-family:{FONT};font-size:14.5px;letter-spacing:1px;'
                        f'text-transform:uppercase;color:#8a7c5e;'
                        f'padding:0 0 14px;">{esc(rec["subject"])}</div>')

    sal_html = (f'<div class="para" style="font-family:{FONT};font-size:17.5px;color:#2b2620;'
                f'padding:6px 0 12px;">{esc(sal)}</div>') if sal else ''
    closing_html = (f'<div class="para" style="font-family:{FONT};font-size:17.5px;font-style:italic;'
                    f'color:#3a3328;padding-top:14px;">{esc(closing)}</div>') if closing else ''

    note_html = ''
    if rec.get('commentary'):
        note_html = (
          f'<div style="border-top:1px solid #ddd2b8;margin-top:28px;padding-top:16px;">'
          f'<div style="font-family:{FONT};font-size:11px;letter-spacing:2px;'
          f'text-transform:uppercase;color:#b0a282;padding-bottom:8px;">Editor\'s note</div>'
          f'<div class="note" style="font-family:{FONT};font-size:15px;line-height:1.6;font-style:italic;'
          f'color:#766848;text-align:justify;">{esc(rec["commentary"].strip())}</div></div>')

    money_html = ''
    # Scan the letter body AND the editor's commentary, so figures the editor cites
    # (e.g. "£25" in a note) are also converted. money.rows dedups by label.
    money_text = rec['body'] + '\n' + (rec.get('commentary') or '')
    mrows = money.rows(money_text, int(rec['book_date'][:4])) if rec.get('book_date') else []
    if mrows:
        rr = ''.join(
            f'<tr><td class="mny" style="font-family:{FONT};font-size:15px;font-style:italic;color:#8a7c5e;padding:2px 0;">{esc(l)}</td>'
            f'<td class="mny" align="right" style="font-family:{FONT};font-size:15px;font-style:italic;color:#8a7c5e;padding:2px 0;">{e}</td></tr>'
            for l, e in mrows)
        money_html = (
          f'<div style="border-top:1px dashed #ddd2b8;margin-top:18px;padding-top:14px;">'
          f'<div style="font-family:{FONT};font-size:11px;letter-spacing:2px;'
          f'text-transform:uppercase;color:#b0a282;padding-bottom:8px;">In today\'s money</div>'
          f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rr}</table></div>')

    # Chapter title sits INSIDE the opening card (same dark-mode reasoning as the
    # footer): centred above the sender, set off by a full-width rule.
    chapter_html = ''
    if rec.get('chapter_start') and rec.get('chapter'):
        chapter_html = (
          f'<div style="font-family:{FONT};font-size:21px;font-style:italic;color:#5c4f38;'
          f'text-align:center;">{esc(rec["chapter"])}</div>'
          f'<div style="border-bottom:1px solid #ddd2b8;font-size:0;line-height:0;margin:18px 0 22px;">&nbsp;</div>')

    return (
      f'<tr><td style="padding-bottom:20px;">'
      f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
      f'style="background-color:#faf6ec;border-radius:7px;">'
      f'<tr><td class="card" style="padding:42px 50px 36px;{TSA}">'
      f'{chapter_html}'
      f'<div style="font-family:{FONT};font-size:22px;font-weight:bold;color:#2b2620;line-height:1.2;">{esc(rec["from"])}</div>'
      f'{role_html}'
      f'<div style="font-family:{FONT};font-size:14.5px;font-weight:bold;color:#2b2620;padding-top:7px;">to {to_line}</div>'
      f'<div style="border-bottom:1px solid #ddd2b8;font-size:0;line-height:0;margin:15px 0;">&nbsp;</div>'
      f'{subject_html}{sal_html}{body_html}{closing_html}{note_html}{money_html}{tail}'
      f'</td></tr></table></td></tr>')

def email_day(recs, unsub_url=None):
    day = fmt_date_en(recs[0]['book_date'])
    # The footer (masthead + colophon + links) lives INSIDE the last card: outside it,
    # Gmail's dark theme leaves this small type nearly unreadable against the pattern
    # image, which is never inverted. Inside, it gets the same dark treatment as the
    # letter text. Label colour matches the card's section labels.
    line = (f'font-family:{FONT};font-size:11px;letter-spacing:2px;'
            f'text-transform:uppercase;color:#b0a282;text-align:center;')
    # Short centred rules set the two links apart (so nobody unsubscribes reaching
    # for the archive) and close off the date/title/subtitle/author block.
    rule = ('<div style="padding-top:14px;">'
            '<table role="presentation" align="center" cellpadding="0" cellspacing="0"><tr>'
            '<td style="border-top:1px solid #ddd2b8;width:30px;font-size:0;line-height:0;height:1px;">&nbsp;</td>'
            '</tr></table></div>')
    footer = (
      f'<div style="border-top:1px solid #ddd2b8;margin-top:28px;padding-top:18px;">'
      f'<div style="{line}">{day}</div>'
      f'<div style="{line}padding-top:7px;">The Honeywood File</div>'
      f'<div style="{line}padding-top:7px;">An Adventure in Building</div>'
      f'<div style="{line}padding-top:7px;">H. B. Creswell</div>'
      f'{rule}'
      f'<div style="{line}padding-top:14px;"><a href="{SITE_URL}" '
      f'style="color:#b0a282;text-decoration:underline;">Read earlier letters</a></div>')
    if unsub_url:
        footer += rule + (
          f'<div style="{line}padding-top:14px;"><a href="{html.escape(unsub_url, quote=True)}" '
          f'style="color:#b0a282;text-decoration:underline;">Stop further correspondence</a></div>')
    footer += '</div>'
    sheets = ''.join(sheet(r, footer if i == len(recs) - 1 else '') for i, r in enumerate(recs))
    # Narrow screens: a 50px-padded justified column drops to ~32 chars/line and reads
    # badly. The media query does LAYOUT only — fluid width, lighter padding, ragged
    # right; font sizes are set once, inline, identical on every screen. table.wrap
    # must go fluid: a fixed 600px table on a ~390px phone makes the client shrink the
    # whole email and re-inflate text unevenly. Clients that drop <style> keep the
    # 600px baseline.
    mobile_css = (
      '<style>'
      f'body,table,td,p,div{{{TSA}}}'
      '@media only screen and (max-width:480px){'
      'table.wrap{width:100% !important;}'
      'td.card{padding:32px 24px 28px !important;}'
      '.para{text-align:left !important;font-size:17px !important;}'
      '.note{text-align:left !important;font-size:14.5px !important;}'
      '.mny{font-size:14.5px !important;}'  # money rows: same treatment as the note
      '}</style>')
    return (
      '<!DOCTYPE html><html><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      f'{mobile_css}</head>'
      f'<body style="margin:0;padding:0;{TSA}{_bg()}">'
      f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
      f'style="{TSA}{_bg()}"><tr><td align="center" style="padding:30px 12px 40px;">'
      '<table class="wrap" role="presentation" width="600" cellpadding="0" cellspacing="0" '
      'style="width:600px;max-width:600px;">'
      f'{sheets}'
      '</table></td></tr></table></body></html>')

def subject_line(recs):
    return f"The Honeywood File · {fmt_date_en(recs[0]['book_date'])}"

if __name__ == '__main__':
    import sys
    from build import load_merged, group_by_send_date
    recs = load_merged()
    days = group_by_send_date(recs)
    target = sys.argv[1] if len(sys.argv) > 1 else next(iter(days))
    from pathlib import Path
    Path(f'/tmp/mail_{target}.html').write_text(email_day(days[target]), encoding='utf-8')
    print(f'/tmp/mail_{target}.html')
    print('SUBJECT:', subject_line(days[target]))
