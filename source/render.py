#!/usr/bin/env python3
"""Render letter records as period-styled HTML emails. One email may hold several letters (same day)."""
from __future__ import annotations
import html, re

MONTHS_EN = ['', 'January','February','March','April','May','June',
             'July','August','September','October','November','December']

def fmt_date_en(iso):
    y, m, d = map(int, iso.split('-'))
    return f"{d} {MONTHS_EN[m]} {y}"

def split_salutation_closing(body):
    b = body.strip()
    sal = ''
    m = re.match(r'^(Dear[^,\n]*,|Sirs,|Sir,|Madam,)\s*', b)
    if m:
        sal = m.group(1); b = b[m.end():]
    b = re.sub(r'^\s*\d{1,2}\s*[.\-/,•]\s*\d{1,2}\s*[.\-/,•]\s*\d{2,4}\.?\s*', '', b)
    closing = ''
    cm = re.search(r'(Yours faithfully,|Yours sincerely,|Yours truly,|Yours obediently,|Yours to oblige,|Yours respectfully,|I remain, Sir,?|I am, Sir,?|Believe me,)\s*$', b)
    if cm:
        closing = cm.group(1); b = b[:cm.start()].strip()
    return sal, b.strip(), closing

STYLES = """
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&display=swap');
body { margin:0; padding:30px 16px 40px; background:#e8e2d4;
  font-family:'EB Garamond', Georgia, serif; color:#2b2620; }
.masthead { max-width:600px; margin:0 auto 20px; text-align:center;
  font-size:11px; letter-spacing:.18em; text-transform:uppercase; color:#a89a78; }
.chapter { max-width:520px; margin:20px auto 30px; text-align:center; }
.chapter .dash { width:30px; height:1px; background:#bfb088; margin:0 auto 20px; }
.chapter .title { font-size:21px; font-style:italic; color:#5c4f38; }
.sheet { max-width:600px; margin:0 auto 20px; background:#faf6ec;
  box-shadow:0 2px 18px rgba(60,50,30,.16); padding:42px 50px 36px;
  border-radius:7px; }
.meta { border-bottom:1px solid #ddd2b8; padding-bottom:15px; margin-bottom:14px; }
.who .from { font-size:22px; font-weight:500; line-height:1.2; }
.who .role { font-size:12.5px; letter-spacing:.04em; color:#9a8c6f; font-style:italic; margin-top:2px; }
.who .to { font-size:14px; color:#6b5d44; margin-top:7px; }
.who .to span { color:#a89a78; }
.subject { font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:#8a7c5e; margin:0 0 16px; font-style:italic; }
.sal { font-size:17px; margin:14px 0 12px; }
.para { font-size:17px; line-height:1.62; margin:0 0 13px; text-align:justify; }
.closing { font-size:17px; font-style:italic; margin-top:16px; color:#3a3328; }
.note { margin-top:30px; padding-top:17px; border-top:1px solid #ddd2b8; }
.note-label { font-size:10px; letter-spacing:.26em; text-transform:uppercase; color:#b0a282; margin-bottom:8px; }
.note p { font-size:14.5px; line-height:1.6; font-style:italic; color:#766848; margin:0; text-align:justify; }
.attach { margin-top:22px; padding:0; }
.attach-label { font-size:10px; letter-spacing:.26em; text-transform:uppercase; color:#a89a78; margin-bottom:8px; }
.attach img { max-width:100%; border:1px solid #ddd2b8; background:#fff; }
.footer { max-width:600px; margin:8px auto 0; text-align:center;
  font-size:11px; letter-spacing:.18em; text-transform:uppercase; color:#a89a78; }
"""

def render_sheet(rec):
    body = rec['body']
    commentary = rec.get('commentary')
    subject = rec.get('subject')
    attachments = rec.get('attachments') or []
    sal, para, closing = split_salutation_closing(body)
    def ph(p): return html.escape(p.strip()).replace('\n', '<br>')
    paras = re.split(r'\n{2,}', para)
    body_html = ''.join(f'<p class="para">{ph(p)}</p>' for p in paras if p.strip())
    comment_html = ''
    if commentary:
        comment_html = f'<div class="note"><div class="note-label">Editor\'s note</div><p>{html.escape(commentary.strip())}</p></div>'
    attach_html = ''
    if attachments:
        imgs = ''.join(f'<img src="{html.escape(a)}" alt="enclosure">' for a in attachments)
        attach_html = f'<div class="attach"><div class="attach-label">enclosure</div>{imgs}</div>'
    from_role = rec.get('from_role')
    to_role = rec.get('to_role')
    to_line = html.escape(rec['to']) + (f", {html.escape(to_role)}" if to_role else '')
    chapter_html = ''
    if rec.get('chapter_start') and rec.get('chapter'):
        chapter_html = (f'<div class="chapter"><div class="dash"></div>'
                        f'<div class="title">{html.escape(rec["chapter"])}</div></div>')
    return chapter_html + f'''<div class="sheet">
    <div class="meta">
      <div class="who">
        <div class="from">{html.escape(rec['from'])}</div>
        {f'<div class="role">{html.escape(from_role)}</div>' if from_role else ''}
        <div class="to">to {to_line}</div>
      </div>
    </div>
    {f'<div class="subject">{html.escape(subject)}</div>' if subject else ''}
    {f'<p class="sal">{html.escape(sal)}</p>' if sal else ''}
    {body_html}
    {f'<p class="closing">{html.escape(closing)}</p>' if closing else ''}
    {attach_html}
    {comment_html}
  </div>'''

def page(inner, day_label=None):
    masthead = ''
    if day_label:
        masthead = f'<div class="masthead">The Honeywood File · {day_label}</div>'
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{STYLES}</style></head>
<body>
  {masthead}
  {inner}
  <div class="footer">An Adventure in Building · H. B. Creswell</div>
</body></html>'''

def render_day(recs):
    """recs: list of merged records sharing a send date."""
    day_label = fmt_date_en(recs[0]['book_date'])
    sheets = '\n'.join(render_sheet(r) for r in recs)
    return page(sheets, day_label)

def render(rec):
    return render_day([rec])
