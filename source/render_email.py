#!/usr/bin/env python3
"""Email-safe renderer: inline styles + table layout, so it survives Gmail (which strips
<style> blocks and external fonts). Georgia is the realistic font; EB Garamond is listed
first as progressive enhancement for clients that happen to have it."""
from __future__ import annotations
import html, re

FONT = "'EB Garamond', Georgia, 'Times New Roman', serif"
MONTHS_EN = ['', 'January','February','March','April','May','June',
             'July','August','September','October','November','December']

def fmt_date_en(iso):
    y, m, d = map(int, iso.split('-'))
    return f"{d} {MONTHS_EN[m]} {y}"

def esc(s): return html.escape(s)

def split_salutation_closing(body):
    b = body.strip(); sal = ''
    m = re.match(r'^(Dear[^,\n]*,|Sirs,|Sir,|Madam,)\s*', b)
    if m: sal = m.group(1); b = b[m.end():]
    b = re.sub(r'^\s*\d{1,2}\s*[.\-/,•]\s*\d{1,2}\s*[.\-/,•]\s*\d{2,4}\.?\s*', '', b)
    closing = ''
    cm = re.search(r'(Yours faithfully,|Yours sincerely,|Yours truly,|Yours obediently,|Yours to oblige,|Yours respectfully,|I remain, Sir,?|I am, Sir,?|Believe me,)\s*$', b)
    if cm: closing = cm.group(1); b = b[:cm.start()].strip()
    return sal, b.strip(), closing

def sheet(rec):
    sal, para, closing = split_salutation_closing(rec['body'])
    def ph(p): return esc(p.strip()).replace('\n', '<br>')
    paras = [p for p in re.split(r'\n{2,}', para) if p.strip()]
    body_html = ''.join(
        f'<p style="font-family:{FONT};font-size:17px;line-height:1.62;'
        f'margin:0 0 13px;color:#2b2620;text-align:justify;">{ph(p)}</p>' for p in paras)

    from_role = rec.get('from_role'); to_role = rec.get('to_role')
    role_html = (f'<div style="font-family:{FONT};font-size:13px;font-style:italic;'
                 f'color:#9a8c6f;padding-top:2px;">{esc(from_role)}</div>') if from_role else ''
    to_line = esc(rec['to']) + (f", {esc(to_role)}" if to_role else '')

    subject_html = ''
    if rec.get('subject'):
        subject_html = (f'<div style="font-family:{FONT};font-size:12px;letter-spacing:1px;'
                        f'text-transform:uppercase;color:#8a7c5e;font-style:italic;'
                        f'padding:0 0 14px;">{esc(rec["subject"])}</div>')

    sal_html = (f'<div style="font-family:{FONT};font-size:17px;color:#2b2620;'
                f'padding:6px 0 12px;">{esc(sal)}</div>') if sal else ''
    closing_html = (f'<div style="font-family:{FONT};font-size:17px;font-style:italic;'
                    f'color:#3a3328;padding-top:14px;">{esc(closing)}</div>') if closing else ''

    note_html = ''
    if rec.get('commentary'):
        note_html = (
          f'<div style="border-top:1px solid #ddd2b8;margin-top:28px;padding-top:16px;">'
          f'<div style="font-family:{FONT};font-size:10px;letter-spacing:2px;'
          f'text-transform:uppercase;color:#b0a282;padding-bottom:8px;">Editor\'s note</div>'
          f'<div style="font-family:{FONT};font-size:14.5px;line-height:1.6;font-style:italic;'
          f'color:#766848;text-align:justify;">{esc(rec["commentary"].strip())}</div></div>')

    chapter_html = ''
    if rec.get('chapter_start') and rec.get('chapter'):
        chapter_html = (
          f'<tr><td align="center" style="padding:20px 0 30px;">'
          f'<table role="presentation" align="center" cellpadding="0" cellspacing="0"><tr>'
          f'<td style="border-top:1px solid #bfb088;width:30px;font-size:0;line-height:0;height:1px;">&nbsp;</td>'
          f'</tr></table>'
          f'<div style="font-family:{FONT};font-size:21px;font-style:italic;color:#5c4f38;'
          f'padding-top:20px;">{esc(rec["chapter"])}</div></td></tr>')

    return chapter_html + (
      f'<tr><td style="padding-bottom:20px;">'
      f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
      f'style="background-color:#faf6ec;border-radius:7px;">'
      f'<tr><td style="padding:42px 50px 36px;">'
      f'<div style="font-family:{FONT};font-size:22px;font-weight:bold;color:#2b2620;line-height:1.2;">{esc(rec["from"])}</div>'
      f'{role_html}'
      f'<div style="font-family:{FONT};font-size:14px;color:#6b5d44;padding-top:7px;">to {to_line}</div>'
      f'<div style="border-bottom:1px solid #ddd2b8;font-size:0;line-height:0;margin:15px 0;">&nbsp;</div>'
      f'{subject_html}{sal_html}{body_html}{closing_html}{note_html}'
      f'</td></tr></table></td></tr>')

def email_day(recs):
    day = fmt_date_en(recs[0]['book_date'])
    sheets = ''.join(sheet(r) for r in recs)
    return (
      '<!DOCTYPE html><html><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
      '<body style="margin:0;padding:0;background-color:#e8e2d4;">'
      '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
      'style="background-color:#e8e2d4;"><tr><td align="center" style="padding:30px 12px 40px;">'
      '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
      'style="width:600px;max-width:600px;">'
      f'<tr><td align="center" style="font-family:{FONT};font-size:11px;letter-spacing:2px;'
      f'text-transform:uppercase;color:#a89a78;padding-bottom:20px;">'
      f'The Honeywood File &middot; {day}</td></tr>'
      f'{sheets}'
      f'<tr><td align="center" style="font-family:{FONT};font-size:11px;letter-spacing:2px;'
      f'text-transform:uppercase;color:#a89a78;padding-top:8px;">'
      f'An Adventure in Building &middot; H. B. Creswell</td></tr>'
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
