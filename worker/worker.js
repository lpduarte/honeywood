// Cloudflare Worker: one-click unsubscribe for The Honeywood File.
//
//   GET  /u?t=TOKEN  -> a confirmation page (a button that POSTs). GETs are SAFE:
//                       mail scanners / link prefetchers only render the page, they
//                       never unsubscribe anyone.
//   POST /u?t=TOKEN  -> flip that recipient's status to "unsubscribed" in the gist.
//                       Also serves RFC 8058 List-Unsubscribe one-click POSTs.
//
// The gist (private) is the single source of truth — the same file the daily
// workflow reads. We identify the recipient by an unguessable per-person token,
// never by email, so no address ever appears in a URL.
//
// The Worker is also the project's cron: Cloudflare Cron Triggers (see wrangler.toml)
// fire `scheduled` at 11:00 and 17:00 UTC, which dispatches the GitHub workflow via
// workflow_dispatch. GitHub's own `schedule` queue is best-effort (1–5 h late at busy
// hours); dispatched runs start in seconds, so the letters go out on time.
//
// Config (set on the Worker):
//   GIST_ID           (secret) the private gist id
//   GIST_TOKEN        (secret) a classic PAT with the `gist` scope (read + write)
//   GH_DISPATCH_TOKEN (secret) a fine-grained PAT, repo lpduarte/honeywood only,
//                     Actions: read & write — just enough to dispatch the workflow
//
// The pages mirror the archive site (lpduarte.github.io/honeywood): EB Garamond +
// Mea Culpa title, paper/pattern background, card, light+dark. Assets are reused
// from the Pages site by absolute URL — see worker/preview.mjs to preview locally.

const GIST_API = 'https://api.github.com/gists/';
const FILE = 'honeywood_recipients.json';
const PAGES = 'https://lpduarte.github.io/honeywood';
const DISPATCH_API =
  'https://api.github.com/repos/lpduarte/honeywood/actions/workflows/honeywood.yml/dispatches';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== '/u') return new Response('Not found', { status: 404 });
    const token = url.searchParams.get('t') || '';
    if (request.method === 'GET') return new Response(confirmHTML(token), htmlInit());
    if (request.method === 'POST') return doUnsub(token, env);
    return new Response('Method not allowed', { status: 405 });
  },

  // Cron Trigger (11:00 / 17:00 UTC): start the daily workflow. No payload beyond the
  // ref — the workflow's --catchup picks the day, so a late or repeated fire is safe.
  // A throw marks the invocation failed in the Cloudflare dashboard (the only signal
  // we get); GitHub-side failures still open an alert issue from the workflow itself.
  async scheduled(event, env) {
    const r = await fetch(DISPATCH_API, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.GH_DISPATCH_TOKEN}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'honeywood-cron',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: 'main' }),
    });
    if (r.status !== 204) throw new Error(`dispatch failed: ${r.status} ${await r.text()}`);
  },
};

async function gist(env, method, body) {
  const r = await fetch(GIST_API + env.GIST_ID, {
    method,
    headers: {
      'Authorization': `Bearer ${env.GIST_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'User-Agent': 'honeywood-unsub',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`gist ${method} ${r.status}`);
  return r.json();
}

async function doUnsub(token, env) {
  if (!token) return new Response(resultHTML('This link is no longer in order.'), htmlInit(400));
  let data;
  try {
    const g = await gist(env, 'GET');
    data = JSON.parse(g.files[FILE].content);
  } catch (e) {
    return new Response(resultHTML('We are unable to attend to this just now. Pray try again later.'), htmlInit(502));
  }
  const rec = (data.recipients || []).find((r) => r.token === token);
  if (!rec) return new Response(resultHTML('This link is no longer in order.'), htmlInit(404));
  if (rec.status !== 'unsubscribed') {
    rec.status = 'unsubscribed';
    try {
      await gist(env, 'PATCH', { files: { [FILE]: { content: JSON.stringify(data, null, 2) } } });
    } catch (e) {
      return new Response(resultHTML('We are unable to attend to this just now. Pray try again later.'), htmlInit(502));
    }
  }
  return new Response(doneHTML(), htmlInit());
}

function htmlInit(status = 200) {
  return { status, headers: { 'Content-Type': 'text/html; charset=utf-8' } };
}

// --- pages, mirroring the archive site's aesthetic --------------------------

const FONTS =
  '<link rel="preconnect" href="https://fonts.googleapis.com">' +
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
  '<link href="https://fonts.googleapis.com/css2?family=Mea+Culpa&family=EB+Garamond:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet">';

const STYLE = `
:root{--bg:#e8e2d4;--ink:#5c4f38;--muted:#a89a78;--card:#faf6ec;--card-ink:#2b2620;--pat:url('${PAGES}/pattern.png');}
@media (prefers-color-scheme:dark){:root{--bg:#1d1b17;--ink:#d9cca9;--muted:#8f8266;--card:#2a2620;--card-ink:#e9e2d0;--pat:url('${PAGES}/pattern_dark.png');}}
html[data-theme=dark]{--bg:#1d1b17;--ink:#d9cca9;--muted:#8f8266;--card:#2a2620;--card-ink:#e9e2d0;--pat:url('${PAGES}/pattern_dark.png');}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background-color:var(--bg);background-image:var(--pat);background-size:192px;
 font-family:'EB Garamond',Georgia,serif;color:var(--ink);display:flex;align-items:center;justify-content:center;padding:32px 18px;}
.wrap{width:540px;max-width:100%;text-align:center;}
.title{font-family:'Mea Culpa',cursive;font-weight:400;font-size:46px;line-height:1.05;color:var(--ink);margin:0 0 6px;}
.sub{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:26px;}
.card{background:var(--card);border-radius:8px;padding:34px 36px;box-shadow:0 1px 3px rgba(0,0,0,.07);}
.msg{font-size:19px;line-height:1.6;color:var(--card-ink);margin:0;}
.signoff{margin-top:14px;}
.btn{display:inline-block;margin-top:22px;font-family:'EB Garamond',Georgia,serif;font-size:16px;color:var(--card);
 background:var(--ink);border:none;border-radius:6px;padding:12px 28px;cursor:pointer;text-decoration:none;}
.btn:hover{filter:brightness(1.08);}
.back{display:inline-block;margin-top:24px;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);text-decoration:none;}
.back:hover{color:var(--ink);}
`;

function shell(inner) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Honeywood File</title>
<link rel="icon" type="image/png" href="${PAGES}/favicon.png">
${FONTS}<style>${STYLE}</style></head>
<body><div class="wrap">
<div class="title">The Honeywood File</div>
<div class="sub">An Adventure in Building &middot; H. B. Creswell</div>
${inner}
</div></body></html>`;
}

export function confirmHTML(token) {
  const inner = token
    ? `<div class="card">
         <p class="msg">Receive no further letters from Mr Spinlove &amp; Co.?</p>
         <form method="POST" action="/u?t=${encodeURIComponent(token)}">
           <button class="btn" type="submit">Cease the correspondence</button>
         </form>
       </div>`
    : `<div class="card"><p class="msg">This link is no longer in order.</p></div>`;
  return shell(inner);
}

export function resultHTML(message, { back = false } = {}) {
  const backlink = back ? `<a class="back" href="${PAGES}/">Back to the calendar</a>` : '';
  return shell(`<div class="card"><p class="msg">${message}</p></div>${backlink}`);
}

export function doneHTML() {
  const inner = `<div class="card">
         <p class="msg">It is done. You shall receive no further letters.</p>
         <p class="msg signoff">We remain, faithfully,<br>The Honeywood File</p>
       </div>`;
  return shell(`${inner}<a class="back" href="${PAGES}/">Back to the calendar</a>`);
}
