// Build docs/Clipp-Project-Overview.pdf from docs/index.html (+ style.css, assets/).
// Usage: node docs/build.js [--png]   (--png also writes page images to docs/build-png/, git-ignored)
const { chromium } = require('playwright');
const path = require('path'); const fs = require('fs');
(async () => {
  const dir = __dirname; const out = path.join(dir, 'Clipp-Project-Overview.pdf');
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + path.join(dir, 'index.html')); await p.evaluate(() => document.fonts.ready);
  const bad = await p.evaluate(() => [...document.querySelectorAll('.page')].map((el, i) => {
    let over = el.scrollHeight - el.clientHeight; // content taller than the page
    const r = el.getBoundingClientRect(); let maxB = 0;
    el.querySelectorAll('*').forEach(c => { if (c.closest('.foot')) return; const cr = c.getBoundingClientRect(); if (cr.height) maxB = Math.max(maxB, cr.bottom - r.top); });
    const limit = r.height - 8 * 3.78; // keep clear of the footer line
    return { page: i + 1, scrollOver: over, bottomPx: Math.round(maxB), limitPx: Math.round(limit), tooLow: maxB > limit };
  }).filter(x => x.scrollOver > 0 || x.tooLow));
  await p.pdf({ path: out, width: '297mm', height: '210mm', printBackground: true, preferCSSPageSize: true });
  if (process.argv.includes('--png')) {
    const pd = path.join(dir, 'build-png'); fs.mkdirSync(pd, { recursive: true });
    const n = await p.locator('.page').count();
    for (let i = 0; i < n; i++) await p.locator('.page').nth(i).screenshot({ path: path.join(pd, `p${String(i + 1).padStart(2, '0')}.png`) });
  }
  await b.close();
  console.log('wrote', out); console.log(bad.length ? 'OVERFLOW: ' + JSON.stringify(bad) : 'no overflow');
})();
