#!/usr/bin/env python3
"""Generate the static archive site into ./site.

Only letters whose mapped send_date is <= today are revealed (future ones are not even
written to disk, so they can't be read ahead in the page source). Calendar years are shown
from 1924 up to the current frontier year. Run daily by the workflow; output deploys to Pages.
"""
import sys, calendar, shutil, html as H
from collections import OrderedDict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'source'))
from build import load_merged
from render_email import split_salutation_closing, fmt_date_en, esc
import money

calendar.setfirstweekday(0)
SITE = ROOT / 'site'
ASSETS = ROOT / 'assets'
TODAY = date.today()

# ---------- revealed data (send_date <= today) ----------
recs = load_merged()
revealed = [r for r in recs if r.get('send_date') and r['send_date'] <= TODAY.isoformat()]
bydate = OrderedDict()
for r in sorted(revealed, key=lambda r: r['seq']):
    bydate.setdefault(r['book_date'], []).append(r)
isos = sorted(bydate)
idx = {v: i for i, v in enumerate(isos)}
letterdays = {tuple(map(int, i.split('-'))) for i in isos}           # active (revealed)
all_letterdays = {tuple(map(int, r['book_date'].split('-'))) for r in recs if r.get('book_date')}
years = [1924, 1925, 1926]   # full calendar; not-yet-sent days show as pending (ring only)

# ---------- web letter card ----------
def card_html(rec):
    sal, para, closing = split_salutation_closing(rec['body'])
    def ph(p): return esc(p.strip()).replace('\n', '<br>')
    import re
    paras = [p for p in re.split(r'\n{2,}', para) if p.strip()]
    body_html = ''.join('<p class="body">%s</p>' % ph(p) for p in paras)
    role = rec.get('from_role'); to_role = rec.get('to_role')
    role_html = '<div class="role">%s</div>' % esc(role) if role else ''
    to_line = esc(rec['to']) + (', %s' % esc(to_role) if to_role else '')
    subj = '<div class="subject">%s</div>' % esc(rec['subject']) if rec.get('subject') else ''
    sal_html = '<div class="sal">%s</div>' % esc(sal) if sal else ''
    clo_html = '<div class="closing">%s</div>' % esc(closing) if closing else ''
    note_html = ''
    if rec.get('commentary'):
        note_html = '<div class="note"><div class="note-h">Editor’s note</div><div class="note-b">%s</div></div>' % esc(rec['commentary'].strip())
    money_html = ''
    mrows = money.rows(rec['body'] + '\n' + (rec.get('commentary') or ''), int(rec['book_date'][:4]))
    if mrows:
        rr = ''.join('<div class="money-row"><span class="l">%s</span><span class="r">%s</span></div>' % (esc(l), e) for l, e in mrows)
        money_html = '<div class="money"><div class="money-h">In today’s money</div>%s</div>' % rr
    chap = ''
    if rec.get('chapter_start') and rec.get('chapter'):
        chap = '<div class="chapter"><span class="dash"></span>%s</div>' % esc(rec['chapter'])
    return (chap + '<div class="card"><div class="from">%s</div>%s<div class="to">to %s</div>'
            '<div class="crule"></div>%s%s%s%s%s%s</div>'
            % (esc(rec['from']), role_html, to_line, subj, sal_html, body_html, clo_html, note_html, money_html))

# ---------- chrome ----------
MOON = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M14 2a10 10 0 1 0 8 16A8 8 0 0 1 14 2z" fill="currentColor"/></svg>'
SUN = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3M4.4 4.4l2.1 2.1M17.5 17.5l2.1 2.1M19.6 4.4l-2.1 2.1M6.5 17.5l-2.1 2.1"/></svg>'
TOGGLE = '<button class="toggle" type="button" aria-label="Light/dark"><span class="ic moon">' + MOON + '</span><span class="ic sun">' + SUN + '</span></button>'
HEADJS = '<script>document.documentElement.setAttribute("data-theme",localStorage.getItem("hw-theme")||"light")</script>'
JS = ('<script>document.addEventListener("click",function(e){if(!e.target.closest(".toggle"))return;'
      'var d=document.documentElement,n=d.getAttribute("data-theme")==="dark"?"light":"dark";'
      'localStorage.setItem("hw-theme",n);d.setAttribute("data-theme",n);});'
      # Auto-hide the floating toggle on scroll-down, reveal on scroll-up, with a 120px
      # hysteresis so it doesn\'t flicker; always shown near the top.
      '(function(){var t=document.querySelector(".toggle");if(!t)return;'
      'var last=window.scrollY,acc=0,hid=false,TH=120;'
      'window.addEventListener("scroll",function(){var y=window.scrollY,dy=y-last;last=y;'
      'if(y<80){if(hid){t.classList.remove("toggle--hidden");hid=false;}acc=0;return;}'
      'if((dy>0)!==(acc>0))acc=0;acc+=dy;'
      'if(!hid&&acc>TH){t.classList.add("toggle--hidden");hid=true;acc=0;}'
      'else if(hid&&acc<-TH){t.classList.remove("toggle--hidden");hid=false;acc=0;}'
      '},{passive:true});})();</script>')
FONT = '<link href="https://fonts.googleapis.com/css2?family=Mea+Culpa&family=EB+Garamond:ital,wght@0,400;0,500;0,700;1,400&display=swap" rel="stylesheet">'

CORE = """
:root{--bg:#e8e2d4;--ink:#5c4f38;--muted:#a89a78;--rule:#bfb088;
 --card:#faf6ec;--card-ink:#2b2620;--card-sub:#6b5d44;--card-rule:#ddd2b8;
 --note-ink:#6f6147;--note-label:#a8997a;--date:#5c4f38;--pat:url('pattern.png');}
[data-theme=dark]{--bg:#1d1b17;--ink:#d9cca9;--muted:#8f8266;--rule:#46402f;
 --card:#2a2620;--card-ink:#e9e2d0;--card-sub:#b8ac8e;--card-rule:#473f30;
 --note-ink:#c0b294;--note-label:#8f8266;--date:#ddd0ad;--pat:url('pattern_dark.png');}
*{box-sizing:border-box}
body{margin:0;background-color:var(--bg);background-image:var(--pat);background-size:192px;
 font-family:'EB Garamond',Georgia,serif;color:var(--ink);transition:background-color .3s,color .3s;}
.toggle{position:fixed;bottom:16px;right:16px;z-index:9;background:var(--card);border:1px solid var(--rule);
 border-radius:50%;width:38px;height:38px;cursor:pointer;color:var(--ink);display:flex;align-items:center;
 justify-content:center;box-shadow:0 1px 3px rgba(0,0,0,.12);
 transition:opacity .35s ease,transform .35s ease,background-color .3s,color .3s;}
.toggle--hidden{opacity:0;transform:translateY(150%);pointer-events:none;}
.ic{display:flex}.sun{display:none}
[data-theme=dark] .moon{display:none}[data-theme=dark] .sun{display:flex}
"""
CSS_CAL = CORE + """
.wrap{max-width:980px;margin:0 auto;padding:48px 18px 70px;}
.title{text-align:center;font-family:'Mea Culpa',cursive;font-weight:400;font-size:54px;color:var(--ink);letter-spacing:0;line-height:1.05;margin:0 0 8px;}
.sub{text-align:center;color:var(--muted);font-size:12px;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;}
.credit{text-align:center;color:var(--muted);font-size:15px;font-style:italic;margin-bottom:30px;}
.credit a{color:var(--muted);text-decoration:underline;}
.credit a:hover{color:var(--ink);}
.ysep{display:flex;align-items:center;gap:18px;margin:48px 0 26px;color:var(--ink);}
.ysep:before,.ysep:after{content:"";flex:1;border-top:1px solid var(--rule);}
.ysep span{font-size:26px;letter-spacing:10px;}
.months{display:grid;grid-template-columns:repeat(4,1fr);gap:22px;}
.mm-card{background:var(--card);border-radius:7px;padding:14px 13px 12px;box-shadow:0 1px 2px rgba(0,0,0,.06);}
.mt{text-align:center;font-size:14px;color:var(--card-sub);letter-spacing:1px;margin-bottom:15px;text-transform:uppercase;}
.wd{display:grid;grid-template-columns:repeat(7,1fr);}
.wd span{text-align:center;font-size:9px;color:var(--card-sub);opacity:.7;text-transform:uppercase;}
.grid{display:grid;grid-template-columns:repeat(7,1fr);}
.day{position:relative;aspect-ratio:1;display:flex;align-items:center;justify-content:center;}
.num{font-size:12px;color:var(--card-sub);transition:opacity .35s ease;position:relative;z-index:2;}
.num.e{opacity:.42;}
a.day.has{text-decoration:none;}a.day.has .num{color:var(--card-ink);}
.ring,.dots{position:absolute;left:1.5%;top:1.5%;width:97%;height:97%;pointer-events:none;mix-blend-mode:multiply;transition:opacity .35s ease,filter .35s ease;}
.ring{opacity:.8;}.dots{opacity:0;}
.ring-pending{position:absolute;left:1.5%;top:1.5%;width:97%;height:97%;pointer-events:none;background-color:var(--card-sub);opacity:.42;-webkit-mask:url('ring.png') center/contain no-repeat;mask:url('ring.png') center/contain no-repeat;}
a.day.has:hover .ring{opacity:1;filter:saturate(1.4) brightness(1.05);}
a.day.has:hover .dots{opacity:1;}
a.day.has:hover .num{opacity:0;}
[data-theme=dark] .ring,[data-theme=dark] .dots{mix-blend-mode:normal;filter:brightness(1.5) saturate(1.2);}
[data-theme=dark] a.day.has:hover .ring,[data-theme=dark] a.day.has:hover .dots{filter:brightness(1.7) saturate(1.3);}
@media(max-width:760px){.months{grid-template-columns:repeat(2,1fr);}}
"""
CSS_READ = CORE + """
.col{width:700px;max-width:100%;margin:0 auto;padding:40px 16px 64px;}
.nav{display:flex;align-items:center;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid var(--rule);}
.nav a.back{font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);text-decoration:none;}
.nav a.back:hover{color:var(--ink);}
.navchev{position:relative;display:inline-flex;width:44px;height:44px;align-items:center;justify-content:center;text-decoration:none;}
.navchev .chev,.navchev .navring{position:absolute;left:0;top:0;width:100%;height:100%;mix-blend-mode:multiply;transition:opacity .35s ease,filter .35s ease;}
.navchev .chev{opacity:.85;}
.navchev .navring{opacity:0;}
a.navchev:hover .navring{opacity:.85;}
a.navchev:hover .chev{opacity:1;filter:saturate(1.35) brightness(1.05);}
.chev.off{opacity:.2;}
[data-theme=dark] .chev,[data-theme=dark] .navring{mix-blend-mode:normal;filter:brightness(1.55) saturate(1.2);}
[data-theme=dark] a.navchev:hover .navring,[data-theme=dark] a.navchev:hover .chev{filter:brightness(1.85) saturate(1.3);}
.head{text-align:center;padding:30px 0 26px;}
.bookname{font-size:13px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);}
.date{font-size:32px;font-style:normal;color:var(--date);line-height:1.15;margin-top:2px;}
.chapter{text-align:center;color:var(--date);font-style:italic;font-size:22px;margin:4px 0 30px;}
.chapter .dash{display:block;width:34px;border-top:1px solid var(--rule);margin:0 auto 16px;}
.card{background:var(--card);border-radius:8px;padding:40px 48px;margin-bottom:26px;box-shadow:0 1px 3px rgba(0,0,0,.07);}
.from{font-size:25px;font-weight:700;color:var(--card-ink);line-height:1.15;}
.role{font-size:14px;font-style:italic;color:var(--card-sub);margin-top:3px;}
.to{font-size:15px;color:var(--card-sub);margin-top:8px;}
.crule{border-bottom:1px solid var(--card-rule);margin:18px 0;}
.subject{font-size:13px;letter-spacing:1px;text-transform:uppercase;font-style:italic;color:var(--card-sub);margin-bottom:14px;}
.sal{font-size:19px;color:var(--card-ink);margin-bottom:12px;}
.body{font-size:19px;line-height:1.72;color:var(--card-ink);text-align:justify;margin:0 0 16px;}
.closing{font-size:19px;font-style:italic;color:var(--card-ink);margin-top:16px;}
.note{border-top:1px dashed var(--card-rule);margin-top:30px;padding-top:18px;}
.note-h{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--note-label);margin-bottom:9px;}
.note-b{font-size:17px;line-height:1.68;font-style:italic;color:var(--note-ink);text-align:justify;}
.money{margin-top:20px;padding-top:14px;border-top:1px dashed var(--card-rule);}
.money-h{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--note-label);margin-bottom:9px;}
.money-row{display:flex;justify-content:space-between;font-size:15px;color:var(--card-sub);padding:3px 0;}
.money-row .r{font-variant-numeric:tabular-nums;}
@media(max-width:560px){.card{padding:28px 24px;}}
"""

def dayfile(i): return "day_%s.html" % i
def page(css, bodyhtml):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>The Honeywood File</title><link rel="icon" type="image/png" href="favicon.png">'
            + HEADJS + FONT + '<style>' + css + '</style></head><body>' + TOGGLE + bodyhtml + JS + '</body></html>')

# ---------- write ----------
if SITE.exists(): shutil.rmtree(SITE)
SITE.mkdir(parents=True)
for p in ASSETS.glob('*.png'): shutil.copy(p, SITE / p.name)

for iso, letters in bydate.items():
    i = idx[iso]; yr = iso[:4]
    prev = isos[i - 1] if i > 0 else None
    nxt = isos[i + 1] if i < len(isos) - 1 else None   # capped at latest revealed -> only-back
    pv = ('<a class="navchev" href="%s" aria-label="previous"><img class="chev" src="prev.png" alt="previous"><img class="navring" src="ring.png" alt=""></a>' % dayfile(prev)) if prev else '<span class="navchev"><img class="chev off" src="prev.png" alt=""></span>'
    nx = ('<a class="navchev" href="%s" aria-label="next"><img class="chev" src="next.png" alt="next"><img class="navring" src="ring.png" alt=""></a>' % dayfile(nxt)) if nxt else '<span class="navchev"><img class="chev off" src="next.png" alt=""></span>'
    nav = '<div class="nav">' + pv + '<a class="back" href="index.html#y%s">Back to calendar</a>' % yr + nx + '</div>'
    head = '<div class="head"><div class="bookname">The Honeywood File</div><div class="date">%s</div></div>' % fmt_date_en(iso)
    cards = ''.join(card_html(r) for r in letters)
    (SITE / dayfile(iso)).write_text(page(CSS_READ, '<div class="col">' + nav + head + cards + '</div>'), encoding='utf-8')

WD = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
def mini(y, m):
    head = '<div class="wd">' + ''.join('<span>%s</span>' % w for w in WD) + '</div>'
    cells = ''
    for wk in calendar.monthcalendar(y, m):
        for d in wk:
            if d == 0: cells += '<span class="day"></span>'
            elif (y, m, d) in letterdays:                       # sent -> active, clickable
                iso = '%04d-%02d-%02d' % (y, m, d)
                cells += '<a class="day has" href="%s" title="%s"><img class="ring" src="ring.png" alt=""><span class="num">%d</span><img class="dots" src="dots.png" alt=""></a>' % (dayfile(iso), H.escape(bydate[iso][0]["from"]), d)
            elif (y, m, d) in all_letterdays:                   # not yet sent -> pending (faint ring only)
                cells += '<span class="day pending"><span class="ring-pending"></span><span class="num e">%d</span></span>' % d
            else: cells += '<span class="day"><span class="num e">%d</span></span>' % d
    return '<div class="mm-card"><div class="mt">%s</div>%s<div class="grid">%s</div></div>' % (calendar.month_name[m], head, cells)

body = ''
for y in years:
    body += '<div class="ysep" id="y%d"><span>%d</span></div>' % (y, y)
    body += '<div class="months">' + ''.join(mini(y, m) for m in range(1, 13)) + '</div>'
cal_body = ('<div class="wrap"><div class="title">The Honeywood File</div>'
            '<div class="sub">An Adventure in Building &middot; H. B. Creswell &middot; 1929</div>'
            '<div class="credit">Inspired by Studio Kirkland&rsquo;s '
            '<a href="https://honeywooddaily.substack.com/" target="_blank" rel="noopener">Honeywood Daily</a></div>'
            + body + '</div>')
(SITE / 'index.html').write_text(page(CSS_CAL, cal_body), encoding='utf-8')
print("site built: %d day pages, years %s, revealed up to %s" % (len(isos), years, TODAY.isoformat()))
