// Render the unsubscribe pages to local HTML files for visual review, without
// deploying. Output: ~/Desktop/honeywood-unsub-preview/. Run: node worker/preview.mjs
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { confirmHTML, doneHTML, resultHTML } from './worker.js';

const out = `${process.env.HOME}/Desktop/honeywood-unsub-preview`;
rmSync(out, { recursive: true, force: true });   // wipe stale files so the folder mirrors the flow exactly
mkdirSync(out, { recursive: true });

const forceDark = (h) => h.replace('<html lang="en">', '<html lang="en" data-theme="dark">');
const invalid = resultHTML('This link is no longer in order.');
const error = resultHTML('We are unable to attend to this just now. Pray try again later.');

const pages = {
  '1-confirm-light.html': confirmHTML('SAMPLE_TOKEN'),
  '1-confirm-dark.html': forceDark(confirmHTML('SAMPLE_TOKEN')),
  '2-done-light.html': doneHTML(),
  '2-done-dark.html': forceDark(doneHTML()),
  '3-invalid-light.html': invalid,
  '3-invalid-dark.html': forceDark(invalid),
  '4-error-light.html': error,
  '4-error-dark.html': forceDark(error),
};
for (const [name, html] of Object.entries(pages)) writeFileSync(`${out}/${name}`, html);
console.log('wrote previews to', out);
