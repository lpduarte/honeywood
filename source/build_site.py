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
# Real time maps onto the book's 1924-26 (1924->2026, i.e. +102y). "Today" in book-space
# is how far the correspondence has advanced; calendar days up to it render as 'passed'.
TODAY_BOOK = '%04d-%02d-%02d' % (TODAY.year - 102, TODAY.month, TODAY.day)

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
import re
# A tender schedule is encoded in the body as a run of lines "Builder — £amount · time"
# (the only such table in the corpus, L032-0). Render it as an aligned 3-column table
# rather than a justified paragraph. No invented headers — the book has none.
_TROW = re.compile(r'^(.+?) — (.+?) · (.+)$')
def _table_html(p):
    lines = [l for l in p.split('\n') if l.strip()]
    if len(lines) < 2:
        return None
    rows = [_TROW.match(l) for l in lines]
    if not all(rows):
        return None
    cells = ''.join(
        '<tr><td class="b">%s</td><td class="a">%s</td><td class="t">%s</td></tr>'
        % (esc(m.group(1)), esc(m.group(2)), esc(m.group(3))) for m in rows)
    return '<table class="tt"><tbody>%s</tbody></table>' % cells

def card_html(rec):
    sal, para, closing = split_salutation_closing(rec['body'])
    def ph(p): return esc(p.strip()).replace('\n', '<br>')
    paras = [p for p in re.split(r'\n{2,}', para) if p.strip()]
    body_html = ''.join(_table_html(p) or '<p class="body">%s</p>' % ph(p) for p in paras)
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
.title{text-align:center;font-family:'Mea Culpa',cursive;font-weight:400;font-size:54px;color:var(--ink);letter-spacing:0;line-height:1.05;margin:0 0 8px;}
.sub{text-align:center;color:var(--muted);font-size:12px;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;}
"""
CSS_CAL = CORE + """
.wrap{max-width:980px;margin:0 auto;padding:48px 18px 70px;}
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
.num.passed{color:var(--card-ink);}
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
.nav--foot{padding-bottom:0;padding-top:16px;border-bottom:none;border-top:1px solid var(--rule);margin-top:48px;}
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
.tt{width:100%;border-collapse:collapse;font-size:18px;color:var(--card-ink);margin:0 0 16px;}
.tt td{padding:7px 0;border-bottom:1px solid var(--card-rule);vertical-align:baseline;}
.tt tr:last-child td{border-bottom:none;}
.tt .a{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;padding-left:22px;}
.tt .t{text-align:right;color:var(--card-sub);white-space:nowrap;padding-left:22px;}
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
CSS_STATUS = CORE + """
.swrap{max-width:600px;margin:0 auto;padding:48px 18px 70px;}
.swrap .sub{margin-bottom:32px;}
.scard{background:var(--card);border-radius:8px;padding:22px 24px 16px;box-shadow:0 1px 2px rgba(0,0,0,.06);}
.scard h2{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--card-sub);font-weight:400;margin:0 0 4px;}
.legend{display:flex;gap:18px;justify-content:flex-end;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--card-sub);margin-bottom:8px;}
.legend .lg{display:inline-flex;align-items:center;gap:6px;}
.legend .lg:before{content:"";width:14px;height:2px;display:inline-block;}
.legend .a:before{background:#b0763e;}
.legend .b:before{background:#6f8f6a;}
.chart{min-height:160px;color:var(--card-sub);font-size:13px;display:flex;align-items:center;justify-content:center;}
.chart svg{width:100%;height:auto;}
.chart .grid{stroke:var(--card-rule);stroke-width:1;}
.chart .yl,.chart .xl{fill:var(--card-sub);font-size:9px;}
.chart .xl{text-anchor:middle;}.chart .yl{text-anchor:end;}
.chart .ln{fill:none;stroke-width:1.6;}
.chart .ln.s11{stroke:#b0763e;}.chart .ln.s17{stroke:#6f8f6a;}
.chart .pt{pointer-events:none;}
.chart .pt.s11{fill:#b0763e;}.chart .pt.s17{fill:#6f8f6a;}
.chart .guide{stroke:var(--card-sub);stroke-width:1;stroke-dasharray:3 3;pointer-events:none;}
.chart .hit{fill:transparent;cursor:pointer;}
.chart .tip{pointer-events:none;}
.chart .tip rect{fill:rgba(43,38,32,.92);}
.chart .tip text{fill:#faf6ec;font-size:10px;}
[data-theme=dark] .chart .tip rect{fill:rgba(15,13,10,.95);}
.updated{text-align:center;color:var(--muted);font-size:12px;font-style:italic;margin-top:16px;}
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
    navinner = pv + '<a class="back" href="index.html#y%s">Back to calendar</a>' % yr + nx
    nav = '<div class="nav">' + navinner + '</div>'
    # Repeat the nav at the foot so the reader can move on without scrolling back up
    # (the page gets long on mobile); rule sits on top so it reads as a footer.
    navfoot = '<div class="nav nav--foot">' + navinner + '</div>'
    head = '<div class="head"><div class="bookname">The Honeywood File</div><div class="date">%s</div></div>' % fmt_date_en(iso)
    cards = ''.join(card_html(r) for r in letters)
    (SITE / dayfile(iso)).write_text(page(CSS_READ, '<div class="col">' + nav + head + cards + navfoot + '</div>'), encoding='utf-8')

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
            else:                                               # no letter: ink if the day has passed, faded if still to come
                iso = '%04d-%02d-%02d' % (y, m, d)
                cls = 'num passed' if iso <= TODAY_BOOK else 'num e'
                cells += '<span class="day"><span class="%s">%d</span></span>' % (cls, d)
    return '<div class="mm-card"><div class="mt">%s</div>%s<div class="grid">%s</div></div>' % (calendar.month_name[m], head, cells)

# Last month with any correspondence, per year — trailing empty months (e.g. 1926
# after February) add nothing, so we stop there rather than padding the year to 12.
last_month = {}
for (y, m, _) in all_letterdays:
    last_month[y] = max(last_month.get(y, 0), m)

body = ''
for y in years:
    body += '<div class="ysep" id="y%d"><span>%d</span></div>' % (y, y)
    body += '<div class="months">' + ''.join(mini(y, m) for m in range(1, last_month.get(y, 12) + 1)) + '</div>'
cal_body = ('<div class="wrap"><div class="title">The Honeywood File</div>'
            '<div class="sub">An Adventure in Building &middot; H. B. Creswell &middot; 1929</div>'
            '<div class="credit">Inspired by Studio Kirkland&rsquo;s '
            '<a href="https://honeywooddaily.substack.com/" target="_blank" rel="noopener">Honeywood Daily</a></div>'
            + body + '</div>')
(SITE / 'index.html').write_text(page(CSS_CAL, cal_body), encoding='utf-8')

# ---------- status page (operational dashboard; not linked from the archive) ----------
# Static shell; the chart data is fetched LIVE in the browser from the public runs API,
# so the page is always current regardless of when it was last deployed. No token needed
# (public repo) — the rate limit is the visitor's own IP. Degrades to a message on failure.
# One chart, two lines (the 11:00 and 17:00 cron slots) sharing a date X-axis, so a slot
# that started later simply begins partway across; Y is the delay vs the scheduled time.
# The cron is a Cloudflare Cron Trigger dispatching the workflow (event=workflow_dispatch);
# runs from the retired GitHub cron (event=schedule) still feed the chart's history.
STATUS_JS = """
(function(){
  var REPO='lpduarte/honeywood', DAYS=30, SLOTS=[11,17], DAYMS=864e5;
  var chart=document.getElementById('chart'), upd=document.getElementById('updated');
  fetch('https://api.github.com/repos/'+REPO+'/actions/workflows/honeywood.yml/runs?per_page=100',
        {headers:{'Accept':'application/vnd.github+json'}})
    .then(function(r){ if(!r.ok) throw 0; return r.json(); })
    .then(function(d){ render(d.workflow_runs||[]); })
    .catch(function(){ chart.textContent='Execuções indisponíveis.'; });

  // For a scheduled run, the nearest UTC slot at or before its start, and the delay (min).
  function slotOf(run){
    var t=new Date(run.created_at), h=t.getUTCHours()+t.getUTCMinutes()/60, slot=null;
    for(var i=0;i<SLOTS.length;i++){ if(SLOTS[i]<=h) slot=SLOTS[i]; }
    if(slot===null) return null;
    var sched=Date.UTC(t.getUTCFullYear(),t.getUTCMonth(),t.getUTCDate(),slot);
    return {slot:slot, day:Date.UTC(t.getUTCFullYear(),t.getUTCMonth(),t.getUTCDate()),
            mins:Math.round((t-sched)/60000)};
  }
  function render(runs){
    var now=new Date(), today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
    var minDay=today-(DAYS-1)*DAYMS, pts={11:{},17:{}};
    runs.forEach(function(run){
      // 'schedule' is the retired GitHub cron (delays of hours were normal);
      // 'workflow_dispatch' is the Cloudflare cron, which lands minutes after the
      // slot — anything later is a manual dispatch, not the cron, so it is skipped.
      if(run.event!=='schedule' && run.event!=='workflow_dispatch') return;
      var x=slotOf(run); if(!x||x.day<minDay) return;
      if(run.event==='workflow_dispatch' && x.mins>60) return;
      if(pts[x.slot][x.day]===undefined) pts[x.slot][x.day]=x.mins;  // newest-first: keep latest per day/slot
    });
    var days=[]; [11,17].forEach(function(s){ for(var k in pts[s]) days.push(+k); });
    if(!days.length){ chart.textContent='Sem execuções agendadas na janela.'; return; }
    var d0=Math.min.apply(null,days), maxMin=60;
    [11,17].forEach(function(s){ for(var k in pts[s]) if(pts[s][k]>maxMin) maxMin=pts[s][k]; });
    chart.innerHTML=svg(pts,d0,today,maxMin); wire();
    upd.textContent='Atualizado '+now.toLocaleString('pt-PT',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
  }
  function fmt(m){ m=Math.round(m); if(m<60) return m+'m'; var r=m%60; return (m/60|0)+'h'+(r<10?'0':'')+r; }
  function svg(pts,d0,d1,maxMin){
    var W=560,H=220,L=42,R=14,T=14,B=28, iw=W-L-R, ih=H-T-B, span=Math.max(d1-d0,DAYMS);
    var X=function(d){return L+(d-d0)/span*iw;}, Y=function(m){return T+ih-(m/maxMin)*ih;};
    var o='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet">';
    [0,maxMin/2,maxMin].forEach(function(m){ var y=Y(m);
      o+='<line class="grid" x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'"/>';
      o+='<text class="yl" x="'+(L-6)+'" y="'+(y+3)+'">'+fmt(m)+'</text>'; });
    var nDays=Math.round(span/DAYMS), step=Math.max(1,Math.ceil(nDays/6));
    for(var d=d0; d<=d1+1; d+=step*DAYMS){ var t=new Date(d);
      o+='<text class="xl" x="'+X(d)+'" y="'+(H-8)+'">'+t.getUTCDate()+'/'+(t.getUTCMonth()+1)+'</text>'; }
    o+='<line class="guide" x1="0" x2="0" y1="'+T+'" y2="'+(T+ih)+'" opacity="0"/>';
    var hits='';
    [11,17].forEach(function(s){
      var ds=Object.keys(pts[s]).map(Number).sort(function(a,b){return a-b;});
      if(ds.length>1) o+='<polyline class="ln s'+s+'" points="'+ds.map(function(d){return X(d)+','+Y(pts[s][d]);}).join(' ')+'"/>';
      ds.forEach(function(d){ var cx=X(d), cy=Y(pts[s][d]), t=new Date(d);
        o+='<circle class="pt s'+s+'" cx="'+cx+'" cy="'+cy+'" r="2.6"/>';
        var lab=t.getUTCDate()+'/'+(t.getUTCMonth()+1)+' · '+s+':00 · +'+fmt(pts[s][d]);
        hits+='<circle class="hit" cx="'+cx+'" cy="'+cy+'" r="11" data-x="'+cx.toFixed(1)+'" data-y="'+cy.toFixed(1)+'" data-l="'+lab+'"/>';
      });
    });
    o+='<g class="tip" opacity="0"><rect rx="3" height="17"></rect><text></text></g>';
    return o+hits+'</svg>';
  }
  function wire(){
    var s=chart.querySelector('svg'); if(!s) return;
    var guide=s.querySelector('.guide'), tip=s.querySelector('.tip'),
        rect=tip.querySelector('rect'), txt=tip.querySelector('text');
    s.querySelectorAll('.hit').forEach(function(h){
      h.addEventListener('mouseenter',function(){
        var x=+h.getAttribute('data-x'), y=+h.getAttribute('data-y'), up=y>110;
        guide.setAttribute('x1',x); guide.setAttribute('x2',x); guide.style.opacity=1;
        txt.textContent=h.getAttribute('data-l');
        var w=txt.getComputedTextLength()+14, tx=Math.min(Math.max(x-w/2,2),558-w);
        tip.setAttribute('transform','translate('+tx+','+(y+(up?-9:9))+')');
        rect.setAttribute('width',w); rect.setAttribute('y',up?-17:0);
        txt.setAttribute('x',7); txt.setAttribute('y',up?-4.5:12.5);
        tip.style.opacity=1;
      });
      h.addEventListener('mouseleave',function(){ guide.style.opacity=0; tip.style.opacity=0; });
    });
  }
})();
"""
status_body = (
    '<div class="swrap">'
    '<div class="title">The Honeywood File</div><div class="sub">Status</div>'
    '<div class="scard">'
    '<h2>Atraso do cron</h2>'
    '<div class="legend"><span class="lg a">11:00</span><span class="lg b">17:00</span></div>'
    '<div id="chart" class="chart">a carregar&hellip;</div>'
    '<div class="updated" id="updated"></div>'
    '</div></div>'
    '<script>' + STATUS_JS + '</script>'
)
(SITE / 'status.html').write_text(page(CSS_STATUS, status_body), encoding='utf-8')

print("site built: %d day pages, years %s, revealed up to %s (+ status.html)" % (len(isos), years, TODAY.isoformat()))
